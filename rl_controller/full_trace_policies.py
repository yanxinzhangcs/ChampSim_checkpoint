from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
from pathlib import Path
from typing import Dict, Optional

from .action_space import Action, ActionSpace, load_action_space
from .builder import ChampSimBuildManager
from .state import WindowMetrics, parse_stats_json

try:
  signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except AttributeError:
  pass

EPS = 1e-12


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
      description=(
          "Run every fixed policy in the action space over the whole trace (one warmup + one simulation run). "
          "If --simulation-instructions is omitted, ChampSim runs to the end of the trace."
      )
  )
  parser.add_argument(
      "--config",
      type=Path,
      default=Path("rl_controller/action_space.json"),
      help="Action space configuration JSON",
  )
  parser.add_argument("--trace", type=Path, required=True, help="ChampSim trace path")
  parser.add_argument("--warmup", type=int, default=10_000_000, help="Warmup instructions before simulation")
  parser.add_argument("--skip-instructions", type=int, default=0, help="Fast-forward before warmup")
  parser.add_argument(
      "--simulation-instructions",
      type=int,
      default=None,
      help="Simulation instructions (omit to run to end-of-trace)",
  )
  parser.add_argument(
      "--output",
      type=Path,
      default=Path("rl_results/full_trace_policies"),
      help="Output directory for logs, stats, and summary JSON",
  )
  parser.add_argument(
      "--l2c-ipv",
      type=str,
      default=None,
      help='Value for env var L2C_IPV (required by PACIPV). If omitted, uses existing $L2C_IPV.',
  )
  parser.add_argument("--dry-run", action="store_true", help="Print commands without running them")
  parser.add_argument("--force", action="store_true", help="Re-run even if output stats already exist")
  return parser.parse_args()


def ensure_dir(path: Path) -> Path:
  path.mkdir(parents=True, exist_ok=True)
  return path


def sanitize(name: str) -> str:
  return name.replace("/", "_").replace(" ", "").replace(".", "_")


def pct_loss_vs_best(best: float, val: float) -> float:
  if abs(best) <= EPS:
    return 0.0
  return (best - val) / best * 100.0


def _needs_ipv(action_space: ActionSpace) -> bool:
  for action in action_space.all_actions():
    if any(v == "PACIPV" for v in action.values.values()):
      return True
  return False


def run_full_trace(
    repo_root: Path,
    build_manager: ChampSimBuildManager,
    action_space: ActionSpace,
    trace_path: Path,
    action: Action,
    warmup: int,
    skip_instructions: int,
    simulation_instructions: Optional[int],
    out_dir: Path,
    env: Dict[str, str],
    dry_run: bool,
    force: bool,
) -> WindowMetrics:
  ensure_dir(out_dir)
  stats_path = out_dir / "full_trace_stats.json"
  log_path = out_dir / "full_trace.log"

  if stats_path.exists() and not force:
    try:
      return parse_stats_json(stats_path)
    except Exception:
      pass

  updates = action.as_config_updates(action_space.heads)
  build = build_manager.ensure_binary(updates)

  cmd_parts = [
      str(build.binary_path),
      "--warmup-instructions",
      str(warmup),
      "--subtrace-count",
      "1",
      "--json",
      str(stats_path),
  ]
  if skip_instructions:
    cmd_parts[1:1] = ["--skip-instructions", str(skip_instructions)]
  if simulation_instructions is not None:
    cmd_parts[1:1] = ["--simulation-instructions", str(simulation_instructions)]
  cmd_parts.append(str(trace_path))

  cmd = " ".join(cmd_parts)
  if dry_run:
    print(cmd)
    return WindowMetrics(
        instructions=0.0,
        cycles=0.0,
        ipc=0.0,
        l1d_mpki=0.0,
        l2_mpki=0.0,
        llc_mpki=0.0,
        prefetch_coverage=0.0,
        prefetch_accuracy=0.0,
        branch_miss_rate=0.0,
    )

  with log_path.open("w", encoding="utf-8") as log_handle:
    log_handle.write(cmd + "\n")
    log_handle.flush()
    subprocess.run(["bash", "-lc", cmd], cwd=repo_root, check=True, stdout=log_handle, stderr=subprocess.STDOUT, env=env)

  return parse_stats_json(stats_path)


def main() -> int:
  args = parse_args()
  repo_root = Path(__file__).resolve().parents[1]
  output_root = ensure_dir(args.output.resolve())

  action_space, _, template_config = load_action_space(args.config.resolve())
  build_manager = ChampSimBuildManager(repo_root=repo_root, template_config=template_config.resolve())

  env = os.environ.copy()
  ipv_value = args.l2c_ipv or env.get("L2C_IPV")
  if _needs_ipv(action_space) and not ipv_value:
    raise SystemExit('PACIPV requires env var L2C_IPV (example: export L2C_IPV="0 1 1 0 3#0 1 0 0 3")')
  if ipv_value:
    env["L2C_IPV"] = ipv_value

  results: Dict[str, Dict[str, object]] = {}
  actions = action_space.all_actions()
  for idx, action in enumerate(actions):
    key = action.key()
    safe_key = sanitize(key)
    out_dir = output_root / "baseline" / safe_key
    print(f"[{idx+1}/{len(actions)}] {key}")
    metrics = run_full_trace(
        repo_root=repo_root,
        build_manager=build_manager,
        action_space=action_space,
        trace_path=args.trace.resolve(),
        action=action,
        warmup=args.warmup,
        skip_instructions=args.skip_instructions,
        simulation_instructions=args.simulation_instructions,
        out_dir=out_dir,
        env=env,
        dry_run=args.dry_run,
        force=args.force,
    )
    if not args.dry_run:
      results[key] = {
          # Keep compatibility with existing analysis scripts
          "total_ipc": metrics.ipc,
          "per_step_ipc": [metrics.ipc],
          # Full-trace metrics
          "instructions": metrics.instructions,
          "cycles": metrics.cycles,
          "ipc": metrics.ipc,
          "stats_path": str(out_dir / "full_trace_stats.json"),
          "log_path": str(out_dir / "full_trace.log"),
      }

  if args.dry_run:
    return 0

  best_key, best_data = max(results.items(), key=lambda item: float(item[1]["ipc"]))
  best_ipc = float(best_data["ipc"])

  summary = {
      "config": {
          "trace": str(args.trace.resolve()),
          "warmup": args.warmup,
          "skip_instructions": args.skip_instructions,
          "simulation_instructions": args.simulation_instructions,
          "action_space": str(args.config.resolve()),
      },
      "fixed_policies": results,
      "best_fixed_policy": {
          "action": best_key,
          "ipc": best_ipc,
      },
  }

  summary_path = output_root / "experiment_summary.json"
  with summary_path.open("w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2)

  print(f"\nExperiment summary saved to {summary_path}\n")
  print(f"best_ipc={best_ipc:.6f}  policy={best_key}")
  print()
  rows = sorted(((k, float(v["ipc"])) for k, v in results.items()), key=lambda kv: kv[1], reverse=True)
  for k, ipc in rows:
    print(f"{k:80s}  ipc={ipc:9.6f}  loss_vs_best={pct_loss_vs_best(best_ipc, ipc):7.3f}%")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
