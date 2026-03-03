from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import pandas as pd


@dataclass(frozen=True)
class BenchmarkData:
  name: str
  fixed_policies: Mapping[str, Mapping[str, object]]
  per_step_results: Sequence[Mapping[str, object]]


def _script_dir() -> Path:
  return Path(__file__).resolve().parent


def _default_results_dir() -> Path:
  # `.../rl_results_final/LOL` -> `.../rl_results_final`
  return _script_dir().parent


def _iter_benchmark_dirs(results_dir: Path) -> List[Path]:
  return sorted([p for p in results_dir.iterdir() if p.is_dir() and p.name.endswith("_combo")])


def _load_benchmark(path: Path) -> BenchmarkData:
  summary_path = path / "experiment_summary.json"
  with summary_path.open("r", encoding="utf-8") as handle:
    data = json.load(handle)

  name = path.name[: -len("_combo")] if path.name.endswith("_combo") else path.name
  fixed_policies = data.get("fixed_policies", {})
  per_step = data.get("per_step_comparison", {}).get("results", [])
  if not isinstance(fixed_policies, dict):
    raise TypeError(f"{summary_path}: expected fixed_policies dict, got {type(fixed_policies)}")
  if not isinstance(per_step, list):
    raise TypeError(f"{summary_path}: expected per_step_comparison.results list, got {type(per_step)}")

  return BenchmarkData(name=name, fixed_policies=fixed_policies, per_step_results=per_step)


def _policy_order(benchmarks: Sequence[BenchmarkData]) -> List[str]:
  for bench in benchmarks:
    keys = list(bench.fixed_policies.keys())
    if keys:
      return keys
  raise ValueError("No fixed_policies found in any benchmark summary")


def _best_policy_key(per_action_ipc: Mapping[str, object]) -> Optional[Tuple[str, float]]:
  if not per_action_ipc:
    return None
  # Preserve insertion order tie-breaking (first max).
  best_key = max(per_action_ipc, key=lambda k: float(per_action_ipc[k]))
  return best_key, float(per_action_ipc[best_key])


def _format_cell(policy_order: Sequence[str], per_action_ipc: Mapping[str, object]) -> Optional[str]:
  best = _best_policy_key(per_action_ipc)
  if best is None:
    return None
  best_key, best_ipc = best
  lines = [f"BEST: {best_key} (IPC={best_ipc:.6f})"]
  for policy in policy_order:
    if policy in per_action_ipc:
      lines.append(f"{policy}: {float(per_action_ipc[policy]):.6f}")
  return "\n".join(lines)


def build_policy_ipc_table(benchmarks: Sequence[BenchmarkData], policy_order: Sequence[str]) -> pd.DataFrame:
  # Collect all steps seen across all benchmarks.
  step_set = set()
  per_bench_step_map: Dict[str, Dict[int, Mapping[str, object]]] = {}
  for bench in benchmarks:
    step_map: Dict[int, Mapping[str, object]] = {}
    for entry in bench.per_step_results:
      step = int(entry.get("step"))
      step_set.add(step)
      step_map[step] = entry
    per_bench_step_map[bench.name] = step_map

  steps = sorted(step_set)
  rows: List[MutableMapping[str, object]] = []
  for step in steps:
    row: MutableMapping[str, object] = {"step": step}
    for bench in benchmarks:
      entry = per_bench_step_map[bench.name].get(step)
      if not entry:
        row[bench.name] = None
        continue
      per_action_ipc = entry.get("per_action_ipc", {})
      if not isinstance(per_action_ipc, dict):
        row[bench.name] = None
        continue
      row[bench.name] = _format_cell(policy_order, per_action_ipc)
    rows.append(row)

  df = pd.DataFrame(rows)
  # Keep columns ordered: step first, then benchmark names (directory-sorted).
  df = df[["step"] + [b.name for b in benchmarks]]
  return df


def _avg_policy_ipc(policy_blob: Mapping[str, object]) -> Optional[float]:
  per_step = policy_blob.get("per_step_ipc")
  if isinstance(per_step, list) and per_step:
    total = policy_blob.get("total_ipc")
    if total is None:
      try:
        total = sum(float(v) for v in per_step)
      except (TypeError, ValueError):
        total = None
    if total is not None:
      return float(total) / len(per_step)
  if "ipc" in policy_blob:
    try:
      return float(policy_blob["ipc"])
    except (TypeError, ValueError):
      return None
  if "total_ipc" in policy_blob:
    try:
      return float(policy_blob["total_ipc"])
    except (TypeError, ValueError):
      return None
  return None


def build_policy_ipc_fulltrace_table(
    benchmarks: Sequence[BenchmarkData], policy_order: Sequence[str]
) -> pd.DataFrame:
  rows: List[MutableMapping[str, object]] = []
  for bench in benchmarks:
    row: MutableMapping[str, object] = {"application": bench.name}
    for policy in policy_order:
      policy_blob = bench.fixed_policies.get(policy, {})
      if isinstance(policy_blob, dict):
        row[policy] = _avg_policy_ipc(policy_blob)
      else:
        row[policy] = None
    rows.append(row)
  return pd.DataFrame(rows)


def _write_excel(df: pd.DataFrame, out_path: Path) -> None:
  df.to_excel(out_path, index=False)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Generate LOL policy tables from rl_results_final/*_combo/experiment_summary.json")
  parser.add_argument("--results-dir", type=Path, default=_default_results_dir(), help="Directory containing *_combo dirs (default: rl_results_final)")
  parser.add_argument("--out-dir", type=Path, default=_script_dir(), help="Output directory (default: rl_results_final/LOL)")
  parser.add_argument("--skip-excel", action="store_true", help="Skip generating policy_ipc_table.xlsx")
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  results_dir = args.results_dir.resolve()
  out_dir = args.out_dir.resolve()
  out_dir.mkdir(parents=True, exist_ok=True)

  bench_dirs = _iter_benchmark_dirs(results_dir)
  if not bench_dirs:
    raise SystemExit(f"No *_combo directories found under {results_dir}")

  benchmarks = [_load_benchmark(d) for d in bench_dirs]
  policy_order = _policy_order(benchmarks)

  df_steps = build_policy_ipc_table(benchmarks, policy_order)
  steps_csv = out_dir / "policy_ipc_table.csv"
  df_steps.to_csv(steps_csv, index=False, encoding="utf-8-sig")
  print(f"Wrote {steps_csv}  (shape={df_steps.shape[0]}x{df_steps.shape[1]})")

  if not args.skip_excel:
    try:
      excel_path = out_dir / "policy_ipc_table.xlsx"
      _write_excel(df_steps, excel_path)
      print(f"Wrote {excel_path}")
    except Exception as exc:
      print(f"WARNING: failed to write Excel file (skipping): {exc}")

  df_fulltrace = build_policy_ipc_fulltrace_table(benchmarks, policy_order)
  fulltrace_csv = out_dir / "policy_ipc_fulltrace_table.csv"
  df_fulltrace.to_csv(fulltrace_csv, index=False, encoding="utf-8-sig")
  print(f"Wrote {fulltrace_csv}  (shape={df_fulltrace.shape[0]}x{df_fulltrace.shape[1]})")

  return 0


if __name__ == "__main__":
  raise SystemExit(main())

