from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .action_space import Action, ActionSpace, load_action_space
from .agent import EpsilonGreedyAgent
from .builder import ChampSimBuildManager
from .runner import ChampSimRunner, RunResult
from .state import parse_stats_json


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="ChampSim RL experiments")
  parser.add_argument("--config", type=Path, default=Path("rl_controller/action_space.json"), help="Action space configuration")
  parser.add_argument("--trace", type=Path, required=True, help="ChampSim trace path")
  parser.add_argument("--warmup", type=int, default=10_000_000, help="Warmup instructions for initial checkpoint")
  parser.add_argument("--window", type=int, default=50_000_000, help="Simulation instructions per window")
  parser.add_argument("--resume-warmup", type=int, default=100, help="Warmup instructions before each measurement window")
  parser.add_argument("--steps", type=int, default=100, help="Number of windows/subtraces to evaluate")
  parser.add_argument("--epsilon", type=float, default=0.1, help="Exploration rate for epsilon-greedy RL agent")
  parser.add_argument("--seed", type=int, default=0, help="Random seed for the agent")
  parser.add_argument("--compare-limit", type=int, default=None, help="Limit the number of windows in per-step comparison (default: all)")
  parser.add_argument("--skip-grid", action="store_true", help="Skip the per-step optimal action comparison")
  parser.add_argument("--output", type=Path, default=Path("rl_experiments"), help="Root directory for experiment outputs")
  return parser.parse_args()


def sanitize(name: str) -> str:
  return name.replace("/", "_").replace(" ", "").replace(".", "_")


def action_display(action: Action) -> Dict[str, str]:
  return dict(action.values)


def ensure_dir(path: Path) -> Path:
  path.mkdir(parents=True, exist_ok=True)
  return path


def run_rl_episode(
    runner: ChampSimRunner,
    action_space: ActionSpace,
    base_action: Action,
    epsilon: float,
    seed: int,
    steps: int,
) -> tuple[Path, List[RunResult]]:
  base_checkpoint = runner.initialise_checkpoint(base_action, action_space)
  agent = EpsilonGreedyAgent(action_space, epsilon=epsilon, seed=seed)

  results: List[RunResult] = []
  state = None
  for step in range(steps):
    action = agent.select_action(state)
    result = runner.run_window(action, action_space, base_checkpoint, step)
    reward = result.metrics.ipc
    next_state = result.metrics.feature_vector
    agent.observe(state, action, reward, next_state)
    state = next_state
    results.append(result)
  return base_checkpoint, results


def run_fixed_policy_episode(
    runner: ChampSimRunner,
    action_space: ActionSpace,
    policy_action: Action,
    steps: int,
) -> tuple[Path, List[RunResult]]:
  base_checkpoint = runner.initialise_checkpoint(policy_action, action_space)
  results: List[RunResult] = []
  for step in range(steps):
    results.append(runner.run_window(policy_action, action_space, base_checkpoint, step))
  return base_checkpoint, results


def run_single_window(
    repo_root: Path,
    build_manager: ChampSimBuildManager,
    action_space: ActionSpace,
    trace_path: Path,
    start_checkpoint: Path,
    skip_instructions: int,
    resume_warmup: int,
    window_instructions: int,
    action: Action,
    output_cache: Path,
    stats_path: Path,
) -> RunResult:
  shutil.copy2(start_checkpoint, output_cache)
  updates = action.as_config_updates(action_space.heads)
  build = build_manager.ensure_binary(updates)

  cmd = (
      f"{build.binary_path} "
      f"--skip-instructions {skip_instructions} "
      f"--warmup-instructions {resume_warmup} "
      f"--simulation-instructions {window_instructions} "
      f"--subtrace-count 1 "
      f"--cache-checkpoint {output_cache} "
      f"--json {stats_path} "
      f"{trace_path}"
  )
  import subprocess
  subprocess.run(["bash", "-lc", cmd], cwd=repo_root, check=True)

  metrics = parse_stats_json(stats_path)
  return RunResult(action=action, metrics=metrics, stats_path=stats_path, cache_path=output_cache, skip_instructions=skip_instructions)


def summarize_results(results: Iterable[RunResult]) -> float:
  return sum(r.metrics.ipc for r in results)


def run_experiments() -> None:
  args = parse_args()
  repo_root = Path(__file__).resolve().parents[1]
  output_root = ensure_dir(args.output.resolve())

  action_space, base_action, template_config = load_action_space(args.config.resolve())
  build_manager = ChampSimBuildManager(repo_root=repo_root, template_config=template_config.resolve())

  # === Experiment 1: RL vs fixed policies ===
  rl_dir = ensure_dir(output_root / "rl")
  rl_runner = ChampSimRunner(
      repo_root=repo_root,
      build_manager=build_manager,
      trace_path=args.trace.resolve(),
      warmup_instructions=args.warmup,
      window_instructions=args.window,
      output_dir=rl_dir,
      resume_warmup=args.resume_warmup,
  )
  rl_base_checkpoint, rl_results = run_rl_episode(
      runner=rl_runner,
      action_space=action_space,
      base_action=base_action,
      epsilon=args.epsilon,
      seed=args.seed,
      steps=args.steps,
  )
  rl_total_ipc = summarize_results(rl_results)

  rl_episode_log = [
      {
          "step": step,
          "action": action_display(result.action),
          "reward": result.metrics.ipc,
          "ipc": result.metrics.ipc,
          "skip_instructions": result.skip_instructions,
          "stats_path": str(result.stats_path),
          "cache_path": str(result.cache_path),
      }
      for step, result in enumerate(rl_results)
  ]

  baselines: Dict[str, Dict[str, object]] = {}
  for action in action_space.all_actions():
    action_key = sanitize(action.key())
    baseline_dir = ensure_dir(output_root / "baseline" / action_key)
    baseline_runner = ChampSimRunner(
        repo_root=repo_root,
        build_manager=build_manager,
        trace_path=args.trace.resolve(),
        warmup_instructions=args.warmup,
        window_instructions=args.window,
        output_dir=baseline_dir,
        resume_warmup=args.resume_warmup,
    )
    _, baseline_results = run_fixed_policy_episode(
        runner=baseline_runner,
        action_space=action_space,
        policy_action=action,
        steps=args.steps,
    )
    baselines[action.key()] = {
        "total_ipc": summarize_results(baseline_results),
        "per_step_ipc": [r.metrics.ipc for r in baseline_results],
    }

  best_policy_key, best_policy_data = max(baselines.items(), key=lambda item: item[1]["total_ipc"])

  summary = {
      "config": {
          "trace": str(args.trace.resolve()),
          "warmup": args.warmup,
          "window": args.window,
          "resume_warmup": args.resume_warmup,
          "steps": args.steps,
          "epsilon": args.epsilon,
          "seed": args.seed,
      },
      "rl": {
          "total_ipc": rl_total_ipc,
          "episode": rl_episode_log,
      },
      "fixed_policies": baselines,
      "best_fixed_policy": {
          "action": best_policy_key,
          "total_ipc": best_policy_data["total_ipc"],
      },
  }

  # === Experiment 2: per-step optimal action ===
  if not args.skip_grid:
    grid_dir = ensure_dir(output_root / "per_step_grid")
    start_checkpoint = rl_base_checkpoint
    step_results = []
    action_choices = action_space.all_actions()
    compare_steps = args.compare_limit if args.compare_limit is not None else len(rl_results)

    for step_idx, rl_result in enumerate(rl_results[:compare_steps]):
      skip_value = rl_result.skip_instructions
      per_action_ipc: Dict[str, float] = {}
      best_action = None
      best_ipc = float("-inf")

      for action in action_choices:
        temp_cache = grid_dir / f"step{step_idx:04d}_{sanitize(action.key())}.log"
        stats_path = grid_dir / f"step{step_idx:04d}_{sanitize(action.key())}.json"
        result = run_single_window(
            repo_root=repo_root,
            build_manager=build_manager,
            action_space=action_space,
            trace_path=args.trace.resolve(),
            start_checkpoint=start_checkpoint,
            skip_instructions=skip_value,
            resume_warmup=args.resume_warmup,
            window_instructions=args.window,
            action=action,
            output_cache=temp_cache,
            stats_path=stats_path,
        )
        ipc = result.metrics.ipc
        per_action_ipc[action.key()] = ipc
        if ipc > best_ipc:
          best_ipc = ipc
          best_action = action

      step_results.append(
          {
              "step": step_idx,
              "skip_instructions": skip_value,
              "rl_action": action_display(rl_result.action),
              "rl_ipc": rl_result.metrics.ipc,
              "best_action": action_display(best_action) if best_action else None,
              "best_ipc": best_ipc,
              "per_action_ipc": per_action_ipc,
          }
      )
      start_checkpoint = rl_result.cache_path

    summary["per_step_comparison"] = {
        "steps_evaluated": len(step_results),
        "results": step_results,
    }

  summary_path = output_root / "experiment_summary.json"
  with summary_path.open("w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2)

  print(f"Experiment summary saved to {summary_path}")


if __name__ == "__main__":
  run_experiments()
