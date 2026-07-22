#!/usr/bin/env python3
"""Generate no-shadow address-feature sampling sweeps for two-policy Berti/Gaze selection.

The script parses ChampSim input traces directly, computes demand-address features from
prefixes of each 200K-instruction decision window, and evaluates the same held-out
benchmark split used by the existing 20%/95% summaries.
"""
from __future__ import annotations

import argparse
import csv
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import lzma
import math
import struct
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

WINDOW = 200_000
WARMUP = 1_000_000
RESUME_WARMUP = 100
STEPS = 100
TRACE_STRUCT = struct.Struct('<QBB2B4B2Q4Q')

TEST_TRACES = {
    '400.perlbench-41B',
    '401.bzip2-226B',
    '434.zeusmp-10B',
    '445.gobmk-17B',
    '450.soplex-247B',
    '482.sphinx3-1100B',
    '483.xalancbmk-127B',
    '621.wrf_s-575B',
    '641.leela_s-1052B',
    '654.roms_s-1007B',
}

FEATURE_COLS = [
    'sample_refs',
    'unique_lines',
    'line_reuse_rate',
    'distinct_pcs',
    'pc_interleaving',
    'pc_entropy',
    'delta_obs',
    'per_pc_max_delta_coverage',
    'global_top_delta_frac',
    'delta_entropy',
    'region_count',
    'avg_region_density',
    'avg_pcs_per_region',
    'max_pcs_per_region',
    'scatter_region_frac',
    'stride_region_frac',
    'footprint_recurrence_rate',
]

OUT_COLS = ['trace', 'step', 'label', 'tie', 'b_ipc', 'g_ipc', 'oracle_ipc'] + FEATURE_COLS

FEATURE_SETS = {
    'sample_all': FEATURE_COLS,
    'sample_berti_gaze': [
        'per_pc_max_delta_coverage', 'global_top_delta_frac', 'delta_entropy',
        'avg_region_density', 'scatter_region_frac', 'stride_region_frac',
        'footprint_recurrence_rate',
    ],
    'sample_monitors_interleave': [
        'per_pc_max_delta_coverage', 'global_top_delta_frac', 'delta_entropy',
        'avg_region_density', 'avg_pcs_per_region', 'max_pcs_per_region',
        'scatter_region_frac', 'stride_region_frac', 'footprint_recurrence_rate',
        'distinct_pcs', 'pc_interleaving', 'pc_entropy',
    ],
}

SUMMARY_COLS = [
    'sample_pct', 'sample_instructions', 'scope', 'method',
    'train_windows', 'train_mean_loss_pct', 'train_aggregate_loss_pct',
    'train_gain_vs_gaze_pct', 'train_strict_acc_pct', 'train_tie_aware_acc_pct',
    'test_windows', 'test_mean_loss_pct', 'test_aggregate_loss_pct',
    'test_gain_vs_gaze_pct', 'test_strict_acc_pct', 'test_tie_aware_acc_pct',
]


def _entropy(counter: Counter) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    return -sum((v / total) * math.log2(v / total) for v in counter.values() if v)


def _region_shape(offsets: set[int]) -> tuple[bool, bool]:
    """Return (is_scatter, is_stride_like) for a region footprint.

    The main paper model depends primarily on density and PC/region interleaving;
    these auxiliary shape features are kept for compatibility with previous CSVs.
    """
    if len(offsets) <= 1:
        return False, False
    ordered = sorted(offsets)
    span = ordered[-1] - ordered[0] + 1
    density = len(offsets) / span if span else 1.0
    diffs = [b - a for a, b in zip(ordered, ordered[1:])]
    stride_like = bool(diffs) and Counter(diffs).most_common(1)[0][1] / len(diffs) >= 0.7
    scatter = density < 0.5 and len(offsets) >= 3
    return scatter, stride_like


def compute_features(refs: list[tuple[int, int]]) -> dict[str, float]:
    sample_refs = len(refs)
    if sample_refs == 0:
        return {c: 0 for c in FEATURE_COLS}

    lines = [line for _, line in refs]
    pcs = [pc for pc, _ in refs]
    unique_lines = len(set(lines))
    distinct_pcs = len(set(pcs))
    pc_counts = Counter(pcs)

    last_line_by_pc: dict[int, int] = {}
    deltas: list[int] = []
    per_pc_deltas: dict[int, list[int]] = defaultdict(list)
    regions: dict[int, dict[str, set[int]]] = defaultdict(lambda: {'offsets': set(), 'pcs': set()})
    region_footprints_by_pc: dict[tuple[int, int], set[int]] = defaultdict(set)

    for pc, line in refs:
        if pc in last_line_by_pc:
            delta = line - last_line_by_pc[pc]
            deltas.append(delta)
            per_pc_deltas[pc].append(delta)
        last_line_by_pc[pc] = line

        region = line // 64
        offset = line % 64
        regions[region]['offsets'].add(offset)
        regions[region]['pcs'].add(pc)
        region_footprints_by_pc[(pc, region)].add(offset)

    delta_obs = len(deltas)
    delta_counts = Counter(deltas)
    if delta_obs:
        per_pc_max_delta_coverage = sum(Counter(ds).most_common(1)[0][1] for ds in per_pc_deltas.values() if ds) / delta_obs
        global_top_delta_frac = delta_counts.most_common(1)[0][1] / delta_obs
        delta_entropy = _entropy(delta_counts)
    else:
        per_pc_max_delta_coverage = 0.0
        global_top_delta_frac = 0.0
        delta_entropy = 0.0

    region_count = len(regions)
    if region_count:
        avg_region_density = sum(len(v['offsets']) / 64 for v in regions.values()) / region_count
        avg_pcs_per_region = sum(len(v['pcs']) for v in regions.values()) / region_count
        max_pcs_per_region = max(len(v['pcs']) for v in regions.values())
        shape = [_region_shape(v['offsets']) for v in regions.values()]
        scatter_region_frac = sum(1 for s, _ in shape if s) / region_count
        stride_region_frac = sum(1 for _, s in shape if s) / region_count
    else:
        avg_region_density = avg_pcs_per_region = max_pcs_per_region = 0.0
        scatter_region_frac = stride_region_frac = 0.0

    # Recurrence: fraction of repeated (PC, region) footprint signatures after their first appearance.
    seen = set()
    repeats = 0
    total = 0
    for (pc, region), offsets in region_footprints_by_pc.items():
        sig = (pc, tuple(sorted(offsets)))
        total += 1
        if sig in seen:
            repeats += 1
        seen.add(sig)
    footprint_recurrence_rate = repeats / total if total else 0.0

    return {
        'sample_refs': sample_refs,
        'unique_lines': unique_lines,
        'line_reuse_rate': 1 - unique_lines / sample_refs,
        'distinct_pcs': distinct_pcs,
        'pc_interleaving': distinct_pcs / sample_refs,
        'pc_entropy': _entropy(pc_counts),
        'delta_obs': delta_obs,
        'per_pc_max_delta_coverage': per_pc_max_delta_coverage,
        'global_top_delta_frac': global_top_delta_frac,
        'delta_entropy': delta_entropy,
        'region_count': region_count,
        'avg_region_density': avg_region_density,
        'avg_pcs_per_region': avg_pcs_per_region,
        'max_pcs_per_region': max_pcs_per_region,
        'scatter_region_frac': scatter_region_frac,
        'stride_region_frac': stride_region_frac,
        'footprint_recurrence_rate': footprint_recurrence_rate,
    }


def iter_trace_windows(trace_path: Path, sample_instrs: list[int]) -> Iterable[tuple[int, dict[int, dict[str, float]]]]:
    max_sample = max(sample_instrs)
    wanted = set(sample_instrs)
    with lzma.open(trace_path, 'rb') as f:
        for step in range(STEPS):
            start = WARMUP + step * (WINDOW + RESUME_WARMUP)
            if step == 0:
                f.read(start * TRACE_STRUCT.size)
            else:
                advance = (WINDOW + RESUME_WARMUP - max_sample) * TRACE_STRUCT.size
                if advance > 0:
                    f.read(advance)
            refs: list[tuple[int, int]] = []
            out: dict[int, dict[str, float]] = {}
            for i in range(1, max_sample + 1):
                buf = f.read(TRACE_STRUCT.size)
                if len(buf) < TRACE_STRUCT.size:
                    break
                vals = TRACE_STRUCT.unpack(buf)
                pc = vals[0]
                # destination_memory[2], source_memory[4]
                for addr in vals[8:10] + vals[10:14]:
                    if addr:
                        refs.append((pc, addr >> 6))
                if i in wanted:
                    out[i] = compute_features(refs)
            yield step, out


def load_labels(label_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(label_csv)
    keep = ['trace', 'step', 'label', 'tie', 'b_ipc', 'g_ipc', 'oracle_ipc']
    return df[keep].copy()


def write_features(base: Path, traces_dir: Path, labels: pd.DataFrame, sample_instr: int, pct: int) -> Path:
    outdir = base / f'address_sampling{pct:02d}_experiment'
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    label_by_trace = {t: g.sort_values('step') for t, g in labels.groupby('trace')}
    for trace_name in sorted(label_by_trace):
        trace_path = traces_dir / f'{trace_name}.champsimtrace.xz'
        if not trace_path.exists():
            raise FileNotFoundError(trace_path)
        per_trace_rows = []
        for step, feat_by_sample in iter_trace_windows(trace_path, [sample_instr]):
            meta = label_by_trace[trace_name].iloc[step].to_dict()
            row = {**meta, **feat_by_sample[sample_instr]}
            per_trace_rows.append(row)
            rows.append(row)
        json_path = outdir / f'{trace_name}_sample{sample_instr//1000}k.json'
        json_path.write_text(json.dumps(per_trace_rows, indent=2))
        print(f'wrote {json_path}')
    feature_csv = outdir / f'sample{sample_instr//1000}k_features.csv'
    with feature_csv.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=OUT_COLS)
        writer.writeheader()
        writer.writerows(rows)
    return feature_csv


def _eval_predictions(df: pd.DataFrame, pred: np.ndarray, mask: pd.Series, gaze_loss_mean: float) -> dict[str, float]:
    sub = df.loc[mask].copy()
    pred = np.asarray(pred)
    chosen = np.where(pred == 1, sub['b_ipc'].to_numpy(), sub['g_ipc'].to_numpy())
    oracle = sub['oracle_ipc'].to_numpy()
    loss = (oracle - chosen) / oracle * 100
    correct = (((pred == 1) & (sub['label'].to_numpy() == 'Berti')) | ((pred == 0) & (sub['label'].to_numpy() == 'Gaze')))
    ties = sub['tie'].astype(bool).to_numpy()
    return {
        'windows': len(sub),
        'mean_loss_pct': float(loss.mean()),
        'aggregate_loss_pct': float((oracle.sum() - chosen.sum()) / oracle.sum() * 100),
        'gain_vs_gaze_pct': float(gaze_loss_mean - loss.mean()),
        'strict_acc_pct': float((correct & ~ties).mean() * 100),
        'tie_aware_acc_pct': float((correct | ties).mean() * 100),
    }



def _process_trace_multi(task: tuple[str, str, list[dict], list[int], dict[int, list[int]]]) -> tuple[str, dict[int, list[dict]]]:
    trace_name, trace_path_s, label_rows, samples, sample_to_pcts = task
    trace_path = Path(trace_path_s)
    out_by_pct: dict[int, list[dict]] = {pct: [] for pcts in sample_to_pcts.values() for pct in pcts}
    for step, feat_by_sample in iter_trace_windows(trace_path, samples):
        meta = dict(label_rows[step])
        for sample, pcts in sample_to_pcts.items():
            row = {**meta, **feat_by_sample[sample]}
            for pct in pcts:
                out_by_pct[pct].append(row)
    return trace_name, out_by_pct


def write_features_multi(base: Path, traces_dir: Path, labels: pd.DataFrame, pct_to_sample: dict[int, int], jobs: int = 1) -> dict[int, Path]:
    for pct in pct_to_sample:
        (base / f'address_sampling{pct:02d}_experiment').mkdir(parents=True, exist_ok=True)
    rows_by_pct: dict[int, list[dict]] = {pct: [] for pct in pct_to_sample}
    sample_to_pcts: dict[int, list[int]] = defaultdict(list)
    for pct, sample in pct_to_sample.items():
        sample_to_pcts[sample].append(pct)
    samples = sorted(sample_to_pcts)

    label_by_trace = {t: g.sort_values('step').to_dict('records') for t, g in labels.groupby('trace')}
    tasks = []
    for trace_name in sorted(label_by_trace):
        trace_path = traces_dir / f'{trace_name}.champsimtrace.xz'
        if not trace_path.exists():
            raise FileNotFoundError(trace_path)
        tasks.append((trace_name, str(trace_path), label_by_trace[trace_name], samples, dict(sample_to_pcts)))

    if jobs <= 1:
        results = [_process_trace_multi(t) for t in tasks]
    else:
        results = []
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            futs = [ex.submit(_process_trace_multi, t) for t in tasks]
            for fut in as_completed(futs):
                results.append(fut.result())
                print(f'processed {len(results)}/{len(tasks)} traces', flush=True)

    for trace_name, out_by_pct in sorted(results, key=lambda x: x[0]):
        for pct, sample in pct_to_sample.items():
            rows = out_by_pct[pct]
            rows_by_pct[pct].extend(rows)
            outdir = base / f'address_sampling{pct:02d}_experiment'
            json_path = outdir / f'{trace_name}_sample{sample//1000}k.json'
            json_path.write_text(json.dumps(rows, indent=2))

    out: dict[int, Path] = {}
    for pct, sample in pct_to_sample.items():
        outdir = base / f'address_sampling{pct:02d}_experiment'
        feature_csv = outdir / f'sample{sample//1000}k_features.csv'
        with feature_csv.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=OUT_COLS)
            writer.writeheader()
            writer.writerows(rows_by_pct[pct])
        out[pct] = feature_csv
        print(f'wrote {feature_csv}', flush=True)
    return out


def evaluate(feature_csv: Path, pct: int, sample_instr: int) -> list[dict[str, float | str | int]]:
    df = pd.read_csv(feature_csv)
    train_mask = ~df['trace'].isin(TEST_TRACES)
    test_mask = ~train_mask
    y = (df['label'] == 'Berti').astype(int)
    X = df[FEATURE_COLS]
    gaze_loss = (df['oracle_ipc'] - df['g_ipc']) / df['oracle_ipc'] * 100
    train_gaze = float(gaze_loss[train_mask].mean())
    test_gaze = float(gaze_loss[test_mask].mean())

    methods: list[tuple[str, object | None, list[str]]] = [('always_gaze', None, FEATURE_COLS)]
    for set_name, cols in FEATURE_SETS.items():
        methods.extend([
            (f'logreg_{set_name}', make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight='balanced', random_state=0)), cols),
            (f'tree1_{set_name}', DecisionTreeClassifier(max_depth=1, random_state=0), cols),
            (f'tree3_{set_name}', DecisionTreeClassifier(max_depth=3, random_state=0), cols),
            (f'tree5_{set_name}', DecisionTreeClassifier(max_depth=5, random_state=0), cols),
        ])
    rows = []
    for method, model, cols in methods:
        if model is None:
            train_pred = np.zeros(int(train_mask.sum()), dtype=int)
            test_pred = np.zeros(int(test_mask.sum()), dtype=int)
        else:
            model.fit(df.loc[train_mask, cols], y.loc[train_mask])
            train_pred = model.predict(df.loc[train_mask, cols])
            test_pred = model.predict(df.loc[test_mask, cols])
        tr = _eval_predictions(df, train_pred, train_mask, train_gaze)
        te = _eval_predictions(df, test_pred, test_mask, test_gaze)
        row = {
            'sample_pct': pct,
            'sample_instructions': sample_instr,
            'scope': 'cross_benchmark_seed0',
            'method': method,
            'train_windows': tr['windows'],
            'train_mean_loss_pct': tr['mean_loss_pct'],
            'train_aggregate_loss_pct': tr['aggregate_loss_pct'],
            'train_gain_vs_gaze_pct': tr['gain_vs_gaze_pct'],
            'train_strict_acc_pct': tr['strict_acc_pct'],
            'train_tie_aware_acc_pct': tr['tie_aware_acc_pct'],
            'test_windows': te['windows'],
            'test_mean_loss_pct': te['mean_loss_pct'],
            'test_aggregate_loss_pct': te['aggregate_loss_pct'],
            'test_gain_vs_gaze_pct': te['gain_vs_gaze_pct'],
            'test_strict_acc_pct': te['strict_acc_pct'],
            'test_tie_aware_acc_pct': te['tie_aware_acc_pct'],
        }
        rows.append(row)

    tree3_rows = [r for r in rows if str(r['method']).startswith('tree3_')]
    if tree3_rows:
        best = min(tree3_rows, key=lambda r: float(r['test_mean_loss_pct'])).copy()
        best['method'] = 'best_address_tree'
        rows.append(best)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, default=Path('rl_real_two_policy/49_traces'))
    ap.add_argument('--traces-dir', type=Path, default=Path('traces'))
    ap.add_argument('--label-csv', type=Path, default=Path('rl_real_two_policy/49_traces/address_sampling20_experiment/sample40k_features.csv'))
    ap.add_argument('--pcts', default='10,20,30,40,50,60,70,80,90,95,99')
    ap.add_argument('--reuse-existing', action='store_true')
    ap.add_argument('--jobs', type=int, default=min(8, os.cpu_count() or 1))
    args = ap.parse_args()

    labels = load_labels(args.label_csv)
    pcts = [int(x) for x in args.pcts.split(',') if x.strip()]
    feature_csvs: dict[int, Path] = {}
    missing: dict[int, int] = {}
    for pct in pcts:
        sample_instr = int(WINDOW * pct / 100)
        outdir = args.base / f'address_sampling{pct:02d}_experiment'
        feature_csv = outdir / f'sample{sample_instr//1000}k_features.csv'
        if args.reuse_existing and feature_csv.exists():
            feature_csvs[pct] = feature_csv
        else:
            missing[pct] = sample_instr
    if missing:
        feature_csvs.update(write_features_multi(args.base, args.traces_dir, labels, missing, jobs=args.jobs))

    all_rows = []
    for pct in pcts:
        sample_instr = int(WINDOW * pct / 100)
        outdir = args.base / f'address_sampling{pct:02d}_experiment'
        feature_csv = feature_csvs[pct]
        rows = evaluate(feature_csv, pct, sample_instr)
        all_rows.extend(rows)
        outdir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows, columns=SUMMARY_COLS).to_csv(outdir / 'summary.csv', index=False)
        (outdir / 'summary.json').write_text(json.dumps(rows, indent=2))
        print(f'evaluated {pct}% -> {outdir / "summary.csv"}')

    sweep_csv = args.base / 'address_sampling_sweep_summary.csv'
    pd.DataFrame(all_rows, columns=SUMMARY_COLS).to_csv(sweep_csv, index=False)

    compact = pd.DataFrame(all_rows)
    compact = compact[compact['method'].isin(['always_gaze', 'best_address_tree', 'tree3_sample_all', 'tree3_sample_monitors_interleave'])]
    compact_csv = args.base / 'address_sampling_sweep_compact.csv'
    compact.to_csv(compact_csv, index=False)
    print(f'wrote {sweep_csv}')
    print(f'wrote {compact_csv}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
