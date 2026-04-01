#!/usr/bin/env python3
from __future__ import annotations

import csv
import statistics
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs"

HASH_ALL = DOCS_DIR / "hash_table_l1d_coverage_accuracy_all_baselines.csv"
HASH_BEST = DOCS_DIR / "hash_table_l1d_coverage_accuracy_best.csv"
NATIVE_ALL = DOCS_DIR / "native_fulltrace_l1d_coverage_accuracy_all_baselines.csv"
NATIVE_BEST = DOCS_DIR / "native_fulltrace_l1d_coverage_accuracy_best.csv"

PAIRWISE_CSV = DOCS_DIR / "native_vs_checkpoint_l1d_pairwise.csv"
BEST_COMPARE_CSV = DOCS_DIR / "native_vs_checkpoint_l1d_best_policy.csv"
POLICY_SUMMARY_CSV = DOCS_DIR / "native_vs_checkpoint_l1d_policy_summary.csv"
MARKDOWN_PATH = DOCS_DIR / "native_vs_checkpoint_l1d_comparison.md"


def fmt(value: float) -> str:
  return f"{value:.12f}"


def load_csv(path: Path) -> list[dict[str, str]]:
  with path.open("r", encoding="utf-8") as handle:
    return list(csv.DictReader(handle))


def write_pairwise_csv(rows: list[dict[str, object]]) -> None:
  with PAIRWISE_CSV.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(
        [
            "trace",
            "policy",
            "checkpoint_l1d_coverage",
            "native_l1d_coverage",
            "delta_l1d_coverage",
            "abs_delta_l1d_coverage",
            "checkpoint_l1d_accuracy",
            "native_l1d_accuracy",
            "delta_l1d_accuracy",
            "abs_delta_l1d_accuracy",
            "checkpoint_is_best_policy",
            "native_is_best_policy",
        ]
    )
    for row in sorted(rows, key=lambda item: (str(item["trace"]), str(item["policy"]))):
      writer.writerow(
          [
              row["trace"],
              row["policy"],
              fmt(float(row["checkpoint_l1d_coverage"])),
              fmt(float(row["native_l1d_coverage"])),
              fmt(float(row["delta_l1d_coverage"])),
              fmt(float(row["abs_delta_l1d_coverage"])),
              fmt(float(row["checkpoint_l1d_accuracy"])),
              fmt(float(row["native_l1d_accuracy"])),
              fmt(float(row["delta_l1d_accuracy"])),
              fmt(float(row["abs_delta_l1d_accuracy"])),
              int(bool(row["checkpoint_is_best_policy"])),
              int(bool(row["native_is_best_policy"])),
          ]
      )


def write_best_csv(rows: list[dict[str, object]]) -> None:
  with BEST_COMPARE_CSV.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(
        [
            "trace",
            "checkpoint_best_policy",
            "native_best_policy",
            "same_best_policy",
            "checkpoint_best_l1d_coverage",
            "native_best_l1d_coverage",
            "delta_best_l1d_coverage",
            "checkpoint_best_l1d_accuracy",
            "native_best_l1d_accuracy",
            "delta_best_l1d_accuracy",
        ]
    )
    for row in sorted(rows, key=lambda item: str(item["trace"])):
      writer.writerow(
          [
              row["trace"],
              row["checkpoint_best_policy"],
              row["native_best_policy"],
              int(bool(row["same_best_policy"])),
              fmt(float(row["checkpoint_best_l1d_coverage"])),
              fmt(float(row["native_best_l1d_coverage"])),
              fmt(float(row["delta_best_l1d_coverage"])),
              fmt(float(row["checkpoint_best_l1d_accuracy"])),
              fmt(float(row["native_best_l1d_accuracy"])),
              fmt(float(row["delta_best_l1d_accuracy"])),
          ]
      )


def write_policy_summary_csv(rows: list[dict[str, object]]) -> None:
  with POLICY_SUMMARY_CSV.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(
        [
            "policy",
            "rows",
            "checkpoint_avg_l1d_coverage",
            "native_avg_l1d_coverage",
            "delta_avg_l1d_coverage",
            "checkpoint_avg_l1d_accuracy",
            "native_avg_l1d_accuracy",
            "delta_avg_l1d_accuracy",
            "checkpoint_best_wins",
            "native_best_wins",
            "delta_best_wins",
        ]
    )
    for row in sorted(rows, key=lambda item: str(item["policy"])):
      writer.writerow(
          [
              row["policy"],
              row["rows"],
              fmt(float(row["checkpoint_avg_l1d_coverage"])),
              fmt(float(row["native_avg_l1d_coverage"])),
              fmt(float(row["delta_avg_l1d_coverage"])),
              fmt(float(row["checkpoint_avg_l1d_accuracy"])),
              fmt(float(row["native_avg_l1d_accuracy"])),
              fmt(float(row["delta_avg_l1d_accuracy"])),
              row["checkpoint_best_wins"],
              row["native_best_wins"],
              row["delta_best_wins"],
          ]
      )


def main() -> int:
  hash_all = load_csv(HASH_ALL)
  native_all = load_csv(NATIVE_ALL)
  hash_best = load_csv(HASH_BEST)
  native_best = load_csv(NATIVE_BEST)

  hash_map = {(row["trace"], row["policy"]): row for row in hash_all}
  native_map = {(row["source_trace"], row["policy"]): row for row in native_all}
  shared_keys = sorted(set(hash_map) & set(native_map))

  pairwise_rows: list[dict[str, object]] = []
  abs_cov_deltas: list[float] = []
  abs_acc_deltas: list[float] = []
  trace_abs_cov: defaultdict[str, list[float]] = defaultdict(list)
  trace_abs_acc: defaultdict[str, list[float]] = defaultdict(list)
  policy_rows: defaultdict[str, list[dict[str, object]]] = defaultdict(list)

  for key in shared_keys:
    hash_row = hash_map[key]
    native_row = native_map[key]
    cov_checkpoint = float(hash_row["avg_l1d_coverage"])
    cov_native = float(native_row["l1d_coverage"])
    acc_checkpoint = float(hash_row["avg_l1d_accuracy"])
    acc_native = float(native_row["l1d_accuracy"])
    pair = {
        "trace": key[0],
        "policy": key[1],
        "checkpoint_l1d_coverage": cov_checkpoint,
        "native_l1d_coverage": cov_native,
        "delta_l1d_coverage": cov_native - cov_checkpoint,
        "abs_delta_l1d_coverage": abs(cov_native - cov_checkpoint),
        "checkpoint_l1d_accuracy": acc_checkpoint,
        "native_l1d_accuracy": acc_native,
        "delta_l1d_accuracy": acc_native - acc_checkpoint,
        "abs_delta_l1d_accuracy": abs(acc_native - acc_checkpoint),
        "checkpoint_is_best_policy": hash_row["is_best_fixed_policy"].lower() in {"1", "true", "yes"},
        "native_is_best_policy": native_row["is_best_fixed_policy"] in {"1", "true", "yes"},
    }
    pairwise_rows.append(pair)
    abs_cov_deltas.append(float(pair["abs_delta_l1d_coverage"]))
    abs_acc_deltas.append(float(pair["abs_delta_l1d_accuracy"]))
    trace_abs_cov[key[0]].append(float(pair["abs_delta_l1d_coverage"]))
    trace_abs_acc[key[0]].append(float(pair["abs_delta_l1d_accuracy"]))
    policy_rows[key[1]].append(pair)

  write_pairwise_csv(pairwise_rows)

  hash_best_map = {row["trace"]: row for row in hash_best}
  native_best_map = {row["source_trace"]: row for row in native_best}
  shared_traces = sorted(set(hash_best_map) & set(native_best_map))

  best_rows: list[dict[str, object]] = []
  changed_count = 0
  checkpoint_win_counter: Counter[str] = Counter()
  native_win_counter: Counter[str] = Counter()
  for trace in shared_traces:
    hrow = hash_best_map[trace]
    nrow = native_best_map[trace]
    checkpoint_win_counter[hrow["best_policy"]] += 1
    native_win_counter[nrow["best_policy"]] += 1
    same = hrow["best_policy"] == nrow["best_policy"]
    if not same:
      changed_count += 1
    best_rows.append(
        {
            "trace": trace,
            "checkpoint_best_policy": hrow["best_policy"],
            "native_best_policy": nrow["best_policy"],
            "same_best_policy": same,
            "checkpoint_best_l1d_coverage": float(hrow["best_avg_l1d_coverage"]),
            "native_best_l1d_coverage": float(nrow["best_l1d_coverage"]),
            "delta_best_l1d_coverage": float(nrow["best_l1d_coverage"]) - float(hrow["best_avg_l1d_coverage"]),
            "checkpoint_best_l1d_accuracy": float(hrow["best_avg_l1d_accuracy"]),
            "native_best_l1d_accuracy": float(nrow["best_l1d_accuracy"]),
            "delta_best_l1d_accuracy": float(nrow["best_l1d_accuracy"]) - float(hrow["best_avg_l1d_accuracy"]),
        }
    )
  write_best_csv(best_rows)

  policy_summary_rows: list[dict[str, object]] = []
  for policy, items in sorted(policy_rows.items()):
    policy_summary_rows.append(
        {
            "policy": policy,
            "rows": len(items),
            "checkpoint_avg_l1d_coverage": statistics.fmean(float(item["checkpoint_l1d_coverage"]) for item in items),
            "native_avg_l1d_coverage": statistics.fmean(float(item["native_l1d_coverage"]) for item in items),
            "delta_avg_l1d_coverage": statistics.fmean(float(item["delta_l1d_coverage"]) for item in items),
            "checkpoint_avg_l1d_accuracy": statistics.fmean(float(item["checkpoint_l1d_accuracy"]) for item in items),
            "native_avg_l1d_accuracy": statistics.fmean(float(item["native_l1d_accuracy"]) for item in items),
            "delta_avg_l1d_accuracy": statistics.fmean(float(item["delta_l1d_accuracy"]) for item in items),
            "checkpoint_best_wins": checkpoint_win_counter[policy],
            "native_best_wins": native_win_counter[policy],
            "delta_best_wins": native_win_counter[policy] - checkpoint_win_counter[policy],
        }
    )
  write_policy_summary_csv(policy_summary_rows)

  top_cov_traces = sorted(
      ((statistics.fmean(values), trace) for trace, values in trace_abs_cov.items()),
      reverse=True,
  )[:8]
  top_acc_traces = sorted(
      ((statistics.fmean(values), trace) for trace, values in trace_abs_acc.items()),
      reverse=True,
  )[:8]

  lines: list[str] = []
  lines.append("# Native Full-Trace vs Checkpoint L1D Comparison")
  lines.append("")
  lines.append("This report compares:")
  lines.append("")
  lines.append("- checkpoint-based `python3 -m rl_controller.experiments` results from `docs/hash_table_l1d_coverage_accuracy_*.csv`")
  lines.append("- native no-checkpoint full-trace results from `docs/native_fulltrace_l1d_coverage_accuracy_*.csv`")
  lines.append("")
  lines.append("Important note: raw `total_ipc` is not directly comparable between the two pipelines.")
  lines.append("The checkpoint experiment summary aggregates 100 windows, while native full-trace records a single run IPC.")
  lines.append("This comparison therefore focuses on:")
  lines.append("")
  lines.append("- same `trace + policy` coverage deltas")
  lines.append("- same `trace + policy` accuracy deltas")
  lines.append("- whether the best fixed policy identity changes per trace")
  lines.append("")
  lines.append("Generated files:")
  lines.append("")
  lines.append(f"- `docs/{PAIRWISE_CSV.name}`")
  lines.append(f"- `docs/{BEST_COMPARE_CSV.name}`")
  lines.append(f"- `docs/{POLICY_SUMMARY_CSV.name}`")
  lines.append("")
  lines.append(f"Shared baseline rows: {len(pairwise_rows)}")
  lines.append(f"Shared traces: {len(shared_traces)}")
  lines.append("")
  lines.append("## Headline Numbers")
  lines.append("")
  lines.append(f"- Mean absolute `L1D coverage` delta across all 392 baseline rows: `{statistics.fmean(abs_cov_deltas):.12f}`")
  lines.append(f"- Median absolute `L1D coverage` delta across all 392 baseline rows: `{statistics.median(abs_cov_deltas):.12f}`")
  lines.append(f"- Mean absolute `L1D accuracy` delta across all 392 baseline rows: `{statistics.fmean(abs_acc_deltas):.12f}`")
  lines.append(f"- Median absolute `L1D accuracy` delta across all 392 baseline rows: `{statistics.median(abs_acc_deltas):.12f}`")
  lines.append(f"- Rows with `|coverage delta| > 0.01`: `{sum(x > 0.01 for x in abs_cov_deltas)}/{len(abs_cov_deltas)}`")
  lines.append(f"- Rows with `|coverage delta| > 0.05`: `{sum(x > 0.05 for x in abs_cov_deltas)}/{len(abs_cov_deltas)}`")
  lines.append(f"- Rows with `|accuracy delta| > 0.05`: `{sum(x > 0.05 for x in abs_acc_deltas)}/{len(abs_acc_deltas)}`")
  lines.append(f"- Rows with `|accuracy delta| > 0.10`: `{sum(x > 0.10 for x in abs_acc_deltas)}/{len(abs_acc_deltas)}`")
  lines.append(f"- Traces where the `best fixed policy` changes: `{changed_count}/{len(shared_traces)}`")
  lines.append(
      f"- Mean absolute delta on the chosen best-policy row: coverage `{statistics.fmean(abs(float(r['delta_best_l1d_coverage'])) for r in best_rows):.12f}`, "
      f"accuracy `{statistics.fmean(abs(float(r['delta_best_l1d_accuracy'])) for r in best_rows):.12f}`"
  )
  lines.append("")
  lines.append("## Policy-Level Aggregate Delta")
  lines.append("")
  lines.append("| Policy | Rows | Checkpoint Avg Cov | Native Avg Cov | Delta Cov | Checkpoint Avg Acc | Native Avg Acc | Delta Acc | Checkpoint Wins | Native Wins | Delta Wins |")
  lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
  for row in sorted(policy_summary_rows, key=lambda item: abs(float(item["delta_avg_l1d_accuracy"])), reverse=True):
    lines.append(
        "| `{policy}` | {rows} | {hcov:.12f} | {ncov:.12f} | {dcov:.12f} | {hacc:.12f} | {nacc:.12f} | {dacc:.12f} | {hw} | {nw} | {dw} |".format(
            policy=row["policy"],
            rows=row["rows"],
            hcov=float(row["checkpoint_avg_l1d_coverage"]),
            ncov=float(row["native_avg_l1d_coverage"]),
            dcov=float(row["delta_avg_l1d_coverage"]),
            hacc=float(row["checkpoint_avg_l1d_accuracy"]),
            nacc=float(row["native_avg_l1d_accuracy"]),
            dacc=float(row["delta_avg_l1d_accuracy"]),
            hw=row["checkpoint_best_wins"],
            nw=row["native_best_wins"],
            dw=row["delta_best_wins"],
        )
    )
  lines.append("")
  lines.append("## Traces With Largest Average Coverage Delta")
  lines.append("")
  lines.append("| Trace | Mean Abs Coverage Delta Across 8 Policies |")
  lines.append("| --- | ---: |")
  for value, trace in top_cov_traces:
    lines.append(f"| {trace} | {value:.12f} |")
  lines.append("")
  lines.append("## Traces With Largest Average Accuracy Delta")
  lines.append("")
  lines.append("| Trace | Mean Abs Accuracy Delta Across 8 Policies |")
  lines.append("| --- | ---: |")
  for value, trace in top_acc_traces:
    lines.append(f"| {trace} | {value:.12f} |")
  lines.append("")
  lines.append("## Interpretation")
  lines.append("")
  lines.append("- `Coverage` differences are not tiny. The mean absolute delta is about `0.0266`, and more than half of all baseline rows exceed `0.01`.")
  lines.append("- `Accuracy` differences are larger. The mean absolute delta is about `0.0548`, and `68/392` rows exceed `0.10`.")
  lines.append("- The best-policy identity changes on `41/49` traces, which is a large shift, not noise-level drift.")
  lines.append("- Native full-trace tends to raise `L1D coverage` slightly for every policy family, but the increase is much larger for `berti` (`+~0.015`) than for `gaze` (`+~0.004 to +0.005`).")
  lines.append("- Native full-trace also raises `L1D accuracy` for all policy families, especially `gaze` (`+~0.022 to +0.025` absolute).")
  lines.append("- So if the question is whether the checkpoint pipeline materially changes the conclusions, the answer is `yes`: the difference is large enough to alter which fixed policy wins on most traces.")
  lines.append("")

  MARKDOWN_PATH.write_text("\n".join(lines), encoding="utf-8")

  print(f"[written] {PAIRWISE_CSV}")
  print(f"[written] {BEST_COMPARE_CSV}")
  print(f"[written] {POLICY_SUMMARY_CSV}")
  print(f"[written] {MARKDOWN_PATH}")
  print(f"[summary] shared_rows={len(pairwise_rows)} changed_best_policy={changed_count}/{len(shared_traces)}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
