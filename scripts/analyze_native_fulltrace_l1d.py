#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
  sys.path.insert(0, str(REPO_ROOT))

from rl_controller.state import parse_stats_json


RESULT_ROOT = REPO_ROOT / "rl_results_native_no_ckpt_20M"
MANIFEST_PATH = REPO_ROOT / "dist" / "emulab_native_fulltrace_dispatch" / "nativeft49" / "manifest.tsv"
DOCS_DIR = REPO_ROOT / "docs"
ALL_BASELINES_CSV = DOCS_DIR / "native_fulltrace_l1d_coverage_accuracy_all_baselines.csv"
BEST_CSV = DOCS_DIR / "native_fulltrace_l1d_coverage_accuracy_best.csv"
POLICY_SUMMARY_CSV = DOCS_DIR / "native_fulltrace_l1d_coverage_accuracy_policy_summary.csv"
MARKDOWN_PATH = DOCS_DIR / "native_fulltrace_l1d_coverage_accuracy.md"


@dataclass(frozen=True)
class BaselineRow:
  trace: str
  source_trace: str
  policy: str
  l1d_coverage: float
  l1d_accuracy: float
  total_ipc: float
  is_best_fixed_policy: bool


def load_expected_traces() -> list[str]:
  if not MANIFEST_PATH.is_file():
    return sorted(path.name for path in RESULT_ROOT.iterdir() if path.is_dir())

  traces: list[str] = []
  lines = MANIFEST_PATH.read_text(encoding="utf-8").strip().splitlines()[1:]
  for line in lines:
    parts = line.split("\t")
    for trace in parts[5].split(","):
      traces.append(f"{trace}_combo")
  return sorted(traces)


def fmt(value: float) -> str:
  return f"{value:.12f}"


def load_rows() -> tuple[list[BaselineRow], list[dict[str, object]], list[str], list[str]]:
  rows: list[BaselineRow] = []
  best_rows: list[dict[str, object]] = []

  expected = load_expected_traces()
  available_dirs = sorted(path for path in RESULT_ROOT.iterdir() if path.is_dir())
  available_names = {path.name for path in available_dirs}
  pending = sorted(set(expected) - available_names)

  for trace_dir in available_dirs:
    summary_path = trace_dir / "fulltrace" / "experiment_summary.json"
    if not summary_path.is_file():
      continue

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    source_trace = trace_dir.name.removesuffix("_combo")
    best_policy = str(summary["best_fixed_policy"]["action"])
    best_ipc = float(summary["best_fixed_policy"]["ipc"])

    per_policy: dict[str, BaselineRow] = {}
    for policy in sorted(summary["fixed_policies"].keys()):
      stats_path = trace_dir / "fulltrace" / "baseline" / policy / "full_trace_stats.json"
      if not stats_path.is_file():
        continue
      metrics = parse_stats_json(stats_path)
      row = BaselineRow(
          trace=trace_dir.name,
          source_trace=source_trace,
          policy=policy,
          l1d_coverage=metrics.prefetch_coverage,
          l1d_accuracy=metrics.prefetch_accuracy,
          total_ipc=float(summary["fixed_policies"][policy]["total_ipc"]),
          is_best_fixed_policy=(policy == best_policy),
      )
      rows.append(row)
      per_policy[policy] = row

    if best_policy in per_policy:
      best_row = per_policy[best_policy]
      best_rows.append(
          {
              "trace": trace_dir.name,
              "source_trace": source_trace,
              "best_policy": best_policy,
              "best_total_ipc": best_ipc,
              "best_l1d_coverage": best_row.l1d_coverage,
              "best_l1d_accuracy": best_row.l1d_accuracy,
          }
      )

  return rows, best_rows, expected, pending


def write_all_baselines_csv(rows: list[BaselineRow]) -> None:
  with ALL_BASELINES_CSV.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(
        [
            "trace",
            "source_trace",
            "policy",
            "l1d_coverage",
            "l1d_accuracy",
            "total_ipc",
            "is_best_fixed_policy",
        ]
    )
    for row in sorted(rows, key=lambda item: (item.trace, item.policy)):
      writer.writerow(
          [
              row.trace,
              row.source_trace,
              row.policy,
              fmt(row.l1d_coverage),
              fmt(row.l1d_accuracy),
              fmt(row.total_ipc),
              int(row.is_best_fixed_policy),
          ]
      )


def write_best_csv(best_rows: list[dict[str, object]]) -> None:
  with BEST_CSV.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(
        [
            "trace",
            "source_trace",
            "best_policy",
            "best_total_ipc",
            "best_l1d_coverage",
            "best_l1d_accuracy",
        ]
    )
    for row in sorted(best_rows, key=lambda item: str(item["trace"])):
      writer.writerow(
          [
              row["trace"],
              row["source_trace"],
              row["best_policy"],
              fmt(float(row["best_total_ipc"])),
              fmt(float(row["best_l1d_coverage"])),
              fmt(float(row["best_l1d_accuracy"])),
          ]
      )


def write_policy_summary_csv(rows: list[BaselineRow]) -> list[dict[str, object]]:
  by_policy: dict[str, list[BaselineRow]] = {}
  for row in rows:
    by_policy.setdefault(row.policy, []).append(row)

  summary_rows: list[dict[str, object]] = []
  for policy, items in sorted(by_policy.items()):
    coverages = [item.l1d_coverage for item in items]
    accuracies = [item.l1d_accuracy for item in items]
    ipcs = [item.total_ipc for item in items]
    win_count = sum(1 for item in items if item.is_best_fixed_policy)
    summary_rows.append(
        {
            "policy": policy,
            "trace_count": len(items),
            "avg_l1d_coverage": statistics.fmean(coverages),
            "median_l1d_coverage": statistics.median(coverages),
            "avg_l1d_accuracy": statistics.fmean(accuracies),
            "median_l1d_accuracy": statistics.median(accuracies),
            "avg_total_ipc": statistics.fmean(ipcs),
            "best_policy_wins": win_count,
        }
    )

  with POLICY_SUMMARY_CSV.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(
        [
            "policy",
            "trace_count",
            "avg_l1d_coverage",
            "median_l1d_coverage",
            "avg_l1d_accuracy",
            "median_l1d_accuracy",
            "avg_total_ipc",
            "best_policy_wins",
        ]
    )
    for row in summary_rows:
      writer.writerow(
          [
              row["policy"],
              row["trace_count"],
              fmt(float(row["avg_l1d_coverage"])),
              fmt(float(row["median_l1d_coverage"])),
              fmt(float(row["avg_l1d_accuracy"])),
              fmt(float(row["median_l1d_accuracy"])),
              fmt(float(row["avg_total_ipc"])),
              row["best_policy_wins"],
          ]
      )

  return summary_rows


def write_markdown(
    rows: list[BaselineRow],
    best_rows: list[dict[str, object]],
    policy_rows: list[dict[str, object]],
    expected: list[str],
    pending: list[str],
) -> None:
  lines: list[str] = []
  lines.append("# Native Full-Trace L1D Coverage and Accuracy")
  lines.append("")
  lines.append("This document summarizes the `rl_results_native_no_ckpt_20M/*_combo/fulltrace` result set.")
  lines.append("")
  lines.append("Metric definition matches `rl_controller/state.py`:")
  lines.append("")
  lines.append("- `L1D coverage = useful_prefetch / total_L1D_misses`")
  lines.append("- `L1D accuracy = useful_prefetch / L1D_prefetch_issued`")
  lines.append("- `total_L1D_misses` sums `LOAD`, `WRITE`, `TRANSLATION`, `PREFETCH`, and `RFO` misses")
  lines.append("- `total_ipc` and `best_policy` come from each trace's `fulltrace/experiment_summary.json`")
  lines.append("- coverage/accuracy come from each baseline's `full_trace_stats.json`")
  lines.append("")
  lines.append("Generated files:")
  lines.append("")
  lines.append(f"- `docs/{ALL_BASELINES_CSV.name}`")
  lines.append(f"- `docs/{BEST_CSV.name}`")
  lines.append(f"- `docs/{POLICY_SUMMARY_CSV.name}`")
  lines.append("")
  lines.append(f"Expected traces: {len(expected)}")
  lines.append(f"Completed traces analyzed: {len(best_rows)}")
  lines.append(f"Pending traces: {len(pending)}")
  lines.append(f"Total fixed baseline rows analyzed: {len(rows)}")
  lines.append(f"Unique fixed policies: {len(policy_rows)}")
  lines.append("")
  if pending:
    lines.append("Pending traces:")
    lines.append("")
    for item in pending:
      lines.append(f"- `{item}`")
    lines.append("")

  lines.append("## Policy-Level Aggregate Summary")
  lines.append("")
  lines.append("| Policy | Traces | Avg L1D Coverage | Median L1D Coverage | Avg L1D Accuracy | Median L1D Accuracy | Avg IPC | Best-Policy Wins |")
  lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
  for row in sorted(policy_rows, key=lambda item: (-float(item["avg_l1d_coverage"]), -float(item["avg_l1d_accuracy"]), str(item["policy"]))):
    lines.append(
        "| {policy} | {trace_count} | {avg_cov:.12f} | {med_cov:.12f} | {avg_acc:.12f} | {med_acc:.12f} | {avg_ipc:.12f} | {wins} |".format(
            policy=f"`{row['policy']}`",
            trace_count=row["trace_count"],
            avg_cov=float(row["avg_l1d_coverage"]),
            med_cov=float(row["median_l1d_coverage"]),
            avg_acc=float(row["avg_l1d_accuracy"]),
            med_acc=float(row["median_l1d_accuracy"]),
            avg_ipc=float(row["avg_total_ipc"]),
            wins=row["best_policy_wins"],
        )
    )
  lines.append("")

  lines.append("## Best Fixed Policy Per Completed Trace")
  lines.append("")
  lines.append("| Trace | Source Trace | Best Policy | Best IPC | L1D Coverage | L1D Accuracy |")
  lines.append("| --- | --- | --- | ---: | ---: | ---: |")
  for row in sorted(best_rows, key=lambda item: str(item["trace"])):
    lines.append(
        "| {trace} | {source_trace} | `{best_policy}` | {best_ipc:.12f} | {cov:.12f} | {acc:.12f} |".format(
            trace=row["trace"],
            source_trace=row["source_trace"],
            best_policy=row["best_policy"],
            best_ipc=float(row["best_total_ipc"]),
            cov=float(row["best_l1d_coverage"]),
            acc=float(row["best_l1d_accuracy"]),
        )
    )
  lines.append("")

  lines.append("## Notes")
  lines.append("")
  lines.append("- This report only includes traces with a complete `fulltrace/experiment_summary.json` and all baseline stats present locally.")
  if pending:
    pending_list = ", ".join(f"`{item}`" for item in pending)
    lines.append(
        f"- Re-run `python3 scripts/analyze_native_fulltrace_l1d.py` after the pending traces finish to refresh the final view: {pending_list}."
    )
  else:
    lines.append("- All 49 traces are complete in the local result set used for this report.")
  lines.append("")

  MARKDOWN_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
  DOCS_DIR.mkdir(parents=True, exist_ok=True)
  rows, best_rows, expected, pending = load_rows()
  write_all_baselines_csv(rows)
  write_best_csv(best_rows)
  policy_rows = write_policy_summary_csv(rows)
  write_markdown(rows, best_rows, policy_rows, expected, pending)
  print(f"[written] {ALL_BASELINES_CSV}")
  print(f"[written] {BEST_CSV}")
  print(f"[written] {POLICY_SUMMARY_CSV}")
  print(f"[written] {MARKDOWN_PATH}")
  print(f"[summary] completed_traces={len(best_rows)} pending_traces={len(pending)} baseline_rows={len(rows)}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
