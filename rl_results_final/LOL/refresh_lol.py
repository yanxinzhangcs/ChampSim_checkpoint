from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _script_dir() -> Path:
  return Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Refresh all LOL tables/plots from rl_results_final/*_combo raw summaries")
  parser.add_argument("--skip-excel", action="store_true", help="Skip regenerating policy_ipc_table.xlsx")
  parser.add_argument("--tables-only", action="store_true", help="Only regenerate base tables (no plots)")
  return parser.parse_args()


def _run(cmd: list[str], cwd: Path) -> None:
  print(f"\n$ {' '.join(cmd)}")
  subprocess.run(cmd, cwd=cwd, check=True)


def main() -> int:
  args = parse_args()
  cwd = _script_dir()

  generate_cmd = [sys.executable, "generate_policy_tables.py"]
  if args.skip_excel:
    generate_cmd.append("--skip-excel")
  _run(generate_cmd, cwd=cwd)

  if args.tables_only:
    return 0

  # Downstream analyses (consume policy_ipc_table*.csv).
  scripts = [
      "analyze_policy_performance.py",
      "analyze_all_benchmarks.py",
      "analyze_policies_vs_baseline.py",
      "analyze_static_policy_median.py",
      "analyze_worst_case_steps.py",
      "baseline_chip_analysis.py",
      "calculate_improvement_headroom.py",
      "compute_policy_optimality.py",
      "create_global_policy_distributions.py",
      "create_loss_boxplots.py",
      "create_static_vs_oracle_distributions.py",
      "visualize_global_baseline_loss.py",
      "analyze_fulltrace_policy.py",
  ]
  for script in scripts:
    _run([sys.executable, script], cwd=cwd)

  return 0


if __name__ == "__main__":
  raise SystemExit(main())

