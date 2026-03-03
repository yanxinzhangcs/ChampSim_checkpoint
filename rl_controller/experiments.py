from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from .action_space import Action, ActionSpace, load_action_space
from .agent import DEFAULT_STATE_CUTOFFS, FEATURE_ORDER, Agent, EpsilonGreedyAgent, HashTableAgent, PPOAgent, RandomAgent
from .builder import ChampSimBuildManager
from .runner import ChampSimRunner, RunResult
from .state import parse_stats_json


def _parse_hash_cutoffs(text: str) -> Tuple[float, ...]:
  parts = [part.strip() for part in text.split(",") if part.strip()]
  expected = len(DEFAULT_STATE_CUTOFFS)
  if len(parts) != expected:
    raise argparse.ArgumentTypeError(f"--hash-cutoffs expects {expected} comma-separated floats (got {len(parts)})")
  try:
    return tuple(float(part) for part in parts)
  except ValueError as exc:
    raise argparse.ArgumentTypeError(f"Invalid float in --hash-cutoffs: {text}") from exc


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="ChampSim RL experiments")
  parser.add_argument("--config", type=Path, default=Path("rl_controller/action_space.json"), help="Action space configuration")
  parser.add_argument("--trace", type=Path, required=True, help="ChampSim trace path")
  parser.add_argument("--warmup", type=int, default=10_000_000, help="Warmup instructions for initial checkpoint")
  parser.add_argument("--window", type=int, default=50_000_000, help="Simulation instructions per window")
  parser.add_argument("--resume-warmup", type=int, default=100, help="Warmup instructions before each measurement window")
  parser.add_argument("--steps", type=int, default=100, help="Number of windows/subtraces to evaluate")
  parser.add_argument("--agent", choices=["ppo", "random", "epsilon_greedy", "hash_table"], default="ppo", help="RL agent to use")
  parser.add_argument("--epsilon", type=float, default=0.1, help="Exploration rate for epsilon-greedy/hash-table policies")
  parser.add_argument("--seed", type=int, default=0, help="Random seed for the agent")
  parser.add_argument("--state-dim", type=int, default=7, help="State vector dimension expected by PPO")
  parser.add_argument(
      "--hash-cutoffs",
      type=_parse_hash_cutoffs,
      default=DEFAULT_STATE_CUTOFFS,
      help=f"Comma-separated cutoffs for state binning (order: {','.join(FEATURE_ORDER)})",
  )
  parser.add_argument("--hash-table", type=Path, default=None, help="Path to load/save the hash table policy JSON (default: <output>/hash_table.json)")
  parser.add_argument("--ppo-rollout-size", type=int, default=32, help="Transitions per PPO update")
  parser.add_argument("--ppo-epochs", type=int, default=4, help="PPO update epochs per rollout")
  parser.add_argument("--ppo-minibatch-size", type=int, default=32, help="PPO minibatch size")
  parser.add_argument("--ppo-policy-lr", type=float, default=0.01, help="PPO policy learning rate")
  parser.add_argument("--ppo-value-lr", type=float, default=0.02, help="PPO value learning rate")
  parser.add_argument("--ppo-gamma", type=float, default=0.99, help="PPO discount factor")
  parser.add_argument("--ppo-lambda", type=float, default=0.95, help="PPO GAE lambda")
  parser.add_argument("--ppo-clip", type=float, default=0.2, help="PPO clipping epsilon")
  parser.add_argument("--ppo-value-coef", type=float, default=0.5, help="PPO value loss coefficient")
  parser.add_argument("--ppo-entropy-coef", type=float, default=0.0, help="PPO entropy coefficient")
  parser.add_argument("--compare-limit", type=int, default=None, help="Limit the number of windows in per-step comparison (default: all)")
  parser.add_argument("--skip-grid", action="store_true", help="Skip the per-step optimal action comparison")
  parser.add_argument("--topk", type=int, default=3, help="Number of top policies to record per step")
  parser.add_argument("--output", type=Path, default=Path("rl_experiments"), help="Root directory for experiment outputs")
  return parser.parse_args()


def sanitize(name: str) -> str:
  return name.replace("/", "_").replace(" ", "").replace(".", "_")


def action_display(action: Action) -> Dict[str, str]:
  return dict(action.values)


def ensure_dir(path: Path) -> Path:
  path.mkdir(parents=True, exist_ok=True)
  return path


def build_agent(args: argparse.Namespace, action_space: ActionSpace, base_action: Action, output_root: Path) -> Agent:
  if args.agent == "random":
    return RandomAgent(action_space, seed=args.seed)
  if args.agent == "epsilon_greedy":
    return EpsilonGreedyAgent(action_space, epsilon=args.epsilon, seed=args.seed)
  if args.agent == "hash_table":
    table_path = args.hash_table.resolve() if args.hash_table is not None else (output_root / "hash_table.json")
    return HashTableAgent(
        action_space=action_space,
        cutoffs=args.hash_cutoffs,
        epsilon=args.epsilon,
        seed=args.seed,
        table_path=table_path,
        initial_action=base_action,
    )
  return PPOAgent(
      action_space=action_space,
      state_dim=args.state_dim,
      seed=args.seed,
      gamma=args.ppo_gamma,
      gae_lambda=args.ppo_lambda,
      clip_epsilon=args.ppo_clip,
      policy_lr=args.ppo_policy_lr,
      value_lr=args.ppo_value_lr,
      value_coef=args.ppo_value_coef,
      entropy_coef=args.ppo_entropy_coef,
      rollout_size=args.ppo_rollout_size,
      update_epochs=args.ppo_epochs,
      minibatch_size=args.ppo_minibatch_size,
  )


def run_rl_episode(
    runner: ChampSimRunner,
    action_space: ActionSpace,
    base_action: Action,
    agent: Agent,
    steps: int,
) -> tuple[Path, List[RunResult]]:
  base_checkpoint = runner.initialise_checkpoint(base_action, action_space)

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
  agent.finalize(state)
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
  agent = build_agent(args, action_space, base_action, output_root)

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
      agent=agent,
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

  config_summary: Dict[str, object] = {
      "trace": str(args.trace.resolve()),
      "warmup": args.warmup,
      "window": args.window,
      "resume_warmup": args.resume_warmup,
      "steps": args.steps,
      "agent": args.agent,
      "seed": args.seed,
  }
  if args.agent == "epsilon_greedy":
    config_summary["epsilon"] = args.epsilon
  if args.agent == "hash_table":
    config_summary.update(
        {
            "epsilon": args.epsilon,
            "hash_cutoffs": list(args.hash_cutoffs),
            "hash_table": str((args.hash_table.resolve() if args.hash_table else (output_root / "hash_table.json"))),
        }
    )
  if args.agent == "ppo":
    config_summary.update(
        {
            "state_dim": args.state_dim,
            "ppo_rollout_size": args.ppo_rollout_size,
            "ppo_epochs": args.ppo_epochs,
            "ppo_minibatch_size": args.ppo_minibatch_size,
            "ppo_policy_lr": args.ppo_policy_lr,
            "ppo_value_lr": args.ppo_value_lr,
            "ppo_gamma": args.ppo_gamma,
            "ppo_lambda": args.ppo_lambda,
            "ppo_clip": args.ppo_clip,
            "ppo_value_coef": args.ppo_value_coef,
            "ppo_entropy_coef": args.ppo_entropy_coef,
        }
    )

  summary = {
      "config": config_summary,
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
    best_action_counts: Dict[str, int] = {}

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

      # Prepare top-K leaderboard and relative gain versus base action
      base_key = base_action.key()
      base_ipc = per_action_ipc.get(base_key)
      sorted_actions = sorted(per_action_ipc.items(), key=lambda item: item[1], reverse=True)
      top_entries = []
      for action_key, ipc in sorted_actions[: args.topk]:
        delta_pct = None
        if base_ipc and base_ipc != 0:
          delta_pct = 100.0 * (ipc - base_ipc) / base_ipc
        top_entries.append({"action": action_key, "ipc": ipc, "delta_pct_vs_base": delta_pct})

      if best_action:
        best_action_counts[best_action.key()] = best_action_counts.get(best_action.key(), 0) + 1

      step_results.append(
          {
              "step": step_idx,
              "skip_instructions": skip_value,
              "rl_action": action_display(rl_result.action),
              "rl_ipc": rl_result.metrics.ipc,
              "best_action": action_display(best_action) if best_action else None,
              "best_ipc": best_ipc,
              "per_action_ipc": per_action_ipc,
              "top_k": top_entries,
              "base_ipc": base_ipc,
          }
      )
      start_checkpoint = rl_result.cache_path

    summary["per_step_comparison"] = {
        "steps_evaluated": len(step_results),
        "results": step_results,
        "best_action_counts": best_action_counts,
    }

  summary_path = output_root / "experiment_summary.json"
  with summary_path.open("w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2)

  print(f"Experiment summary saved to {summary_path}")


if __name__ == "__main__":
  run_experiments()
