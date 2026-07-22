#!/usr/bin/env python3
"""Offline sensitivity sweeps for the two-policy selector paper."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier


TEST_TRACES = {
    "400.perlbench-41B", "401.bzip2-226B", "434.zeusmp-10B",
    "445.gobmk-17B", "450.soplex-247B", "482.sphinx3-1100B",
    "483.xalancbmk-127B", "621.wrf_s-575B", "641.leela_s-1052B",
    "654.roms_s-1007B",
}

FEATURE_SETS = {
    "mechanism_only": [
        "per_pc_max_delta_coverage", "global_top_delta_frac", "delta_entropy",
        "avg_region_density", "scatter_region_frac", "stride_region_frac",
        "footprint_recurrence_rate",
    ],
    "mechanism_interleave": [
        "per_pc_max_delta_coverage", "global_top_delta_frac", "delta_entropy",
        "avg_region_density", "avg_pcs_per_region", "max_pcs_per_region",
        "scatter_region_frac", "stride_region_frac", "footprint_recurrence_rate",
        "distinct_pcs", "pc_interleaving", "pc_entropy",
    ],
    "all_features": [
        "sample_refs", "unique_lines", "line_reuse_rate", "distinct_pcs",
        "pc_interleaving", "pc_entropy", "delta_obs",
        "per_pc_max_delta_coverage", "global_top_delta_frac", "delta_entropy",
        "region_count", "avg_region_density", "avg_pcs_per_region",
        "max_pcs_per_region", "scatter_region_frac", "stride_region_frac",
        "footprint_recurrence_rate",
    ],
}


def metrics(df: pd.DataFrame, pred: np.ndarray) -> dict[str, float]:
    pred = np.asarray(pred, dtype=int)
    chosen = np.where(pred == 1, df["b_ipc"], df["g_ipc"]).astype(float)
    oracle = df["oracle_ipc"].to_numpy(float)
    labels = (df["label"] == "Berti").to_numpy(int)
    ties = df["tie"].astype(bool).to_numpy()
    loss = (oracle - chosen) / oracle * 100.0
    return {
        "mean_loss_pct": float(loss.mean()),
        "aggregate_loss_pct": float((oracle.sum() - chosen.sum()) / oracle.sum() * 100.0),
        "exact_accuracy_pct": float(((pred == labels) & ~ties).mean() * 100.0),
        "tie_aware_accuracy_pct": float(((pred == labels) | ties).mean() * 100.0),
    }


def count_switches(df: pd.DataFrame, pred: np.ndarray) -> int:
    total = 0
    work = df.assign(_pred=np.asarray(pred)).sort_values(["trace", "step"])
    for _, group in work.groupby("trace", sort=False):
        values = group["_pred"].to_numpy()
        total += int((values[1:] != values[:-1]).sum())
    return total


def apply_min_hold(df: pd.DataFrame, proposed: np.ndarray, hold: int) -> np.ndarray:
    work = df.assign(_row=np.arange(len(df)), _proposed=np.asarray(proposed)).sort_values(["trace", "step"])
    out = np.zeros(len(df), dtype=int)
    for _, group in work.groupby("trace", sort=False):
        rows = group["_row"].to_numpy(int)
        values = group["_proposed"].to_numpy(int)
        active = int(values[0])
        age = 1
        out[rows[0]] = active
        for row, value in zip(rows[1:], values[1:]):
            if value != active and age >= hold:
                active = int(value)
                age = 1
            else:
                age += 1
            out[row] = active
    return out


def latent_labels(group: pd.DataFrame) -> np.ndarray:
    labels = []
    last = 0
    for b_ipc, g_ipc in zip(group["b_ipc"], group["g_ipc"]):
        if b_ipc > g_ipc + 1e-12:
            last = 1
        elif g_ipc > b_ipc + 1e-12:
            last = 0
        labels.append(last)
    return np.asarray(labels, dtype=int)


def ipu_predictions(df: pd.DataFrame, delay: int = 1, sample_period: int = 1,
                    error_rate: float = 0.0, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    work = df.assign(_row=np.arange(len(df))).sort_values(["trace", "step"])
    out = np.zeros(len(df), dtype=int)
    for _, group in work.groupby("trace", sort=False):
        rows = group["_row"].to_numpy(int)
        truth = latent_labels(group)
        observed = truth.copy()
        if error_rate:
            observed ^= (rng.random(len(observed)) < error_rate).astype(int)
        latest = 0
        observed_at: list[tuple[int, int]] = []
        for i, row in enumerate(rows):
            eligible = i - delay
            if eligible >= 0 and eligible % sample_period == 0:
                observed_at.append((eligible, int(observed[eligible])))
            if observed_at:
                latest = observed_at[-1][1]
            out[row] = latest
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path,
                        default=Path("rl_real_two_policy/49_traces/address_sampling20_experiment/sample40k_features.csv"))
    parser.add_argument("--output", type=Path,
                        default=Path("rl_real_two_policy/49_traces/selector_sensitivity"))
    parser.add_argument("--noise-trials", type=int, default=100)
    args = parser.parse_args()

    df = pd.read_csv(args.features)
    train = df[~df["trace"].isin(TEST_TRACES)].copy()
    test = df[df["trace"].isin(TEST_TRACES)].copy().reset_index(drop=True)
    y_train = (train["label"] == "Berti").astype(int)
    args.output.mkdir(parents=True, exist_ok=True)

    model_rows = []
    proposed = None
    for set_name, cols in FEATURE_SETS.items():
        for depth in (1, 3, 5):
            tree = DecisionTreeClassifier(max_depth=depth, random_state=0)
            tree.fit(train[cols], y_train)
            pred = tree.predict(test[cols])
            row = {"feature_set": set_name, "tree_depth": depth, **metrics(test, pred)}
            row["switches"] = count_switches(test, pred)
            row["switches_per_trace"] = row["switches"] / len(TEST_TRACES)
            model_rows.append(row)
            if set_name == "all_features" and depth == 3:
                proposed = pred
    pd.DataFrame(model_rows).to_csv(args.output / "address_tree_model_sensitivity.csv", index=False)

    assert proposed is not None
    hold_rows = []
    for hold in (1, 2, 3, 5, 10, 20):
        pred = apply_min_hold(test, proposed, hold)
        row = {"minimum_hold_windows": hold, **metrics(test, pred)}
        row["switches"] = count_switches(test, pred)
        row["switches_per_trace"] = row["switches"] / len(TEST_TRACES)
        hold_rows.append(row)
    pd.DataFrame(hold_rows).to_csv(args.output / "address_tree_hold_sensitivity.csv", index=False)

    ipu_rows = []
    for delay in (1, 2, 3, 5, 10):
        pred = ipu_predictions(test, delay=delay)
        ipu_rows.append({"sweep": "delay", "parameter": delay, "trials": 1,
                         **metrics(test, pred), "switches": count_switches(test, pred)})
    for period in (1, 2, 5, 10, 20):
        pred = ipu_predictions(test, sample_period=period)
        ipu_rows.append({"sweep": "sample_period", "parameter": period, "trials": 1,
                         **metrics(test, pred), "switches": count_switches(test, pred)})
    for error in (0.0, 0.05, 0.10, 0.20, 0.30, 0.40):
        trial_rows = []
        for seed in range(args.noise_trials):
            pred = ipu_predictions(test, error_rate=error, seed=seed)
            trial_rows.append({**metrics(test, pred), "switches": count_switches(test, pred)})
        row = {"sweep": "observation_error", "parameter": error,
               "trials": args.noise_trials}
        for key in trial_rows[0]:
            values = np.asarray([trial[key] for trial in trial_rows], dtype=float)
            row[key] = float(values.mean())
            row[f"{key}_std"] = float(values.std())
        ipu_rows.append(row)
    pd.DataFrame(ipu_rows).to_csv(args.output / "ipu_observation_sensitivity.csv", index=False)

    print(pd.DataFrame(model_rows).to_string(index=False))
    print(pd.DataFrame(hold_rows).to_string(index=False))
    print(pd.DataFrame(ipu_rows).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
