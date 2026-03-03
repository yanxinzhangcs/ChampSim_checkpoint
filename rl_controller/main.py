from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Tuple

from .action_space import load_action_space
from .agent import DEFAULT_STATE_CUTOFFS, FEATURE_ORDER, EpsilonGreedyAgent, HashTableAgent, PPOAgent, RandomAgent
from .builder import ChampSimBuildManager
from .runner import ChampSimRunner


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
  parser = argparse.ArgumentParser(description="ChampSim RL harness")
  parser.add_argument("--config", type=Path, default=Path("rl_controller/action_space.json"), help="Action space configuration")
  parser.add_argument("--trace", type=Path, required=True, help="ChampSim trace path")
  parser.add_argument("--warmup", type=int, default=10_000_000, help="Warmup instructions per window")
  parser.add_argument("--window", type=int, default=50_000_000, help="Simulation instructions per window")
  parser.add_argument("--steps", type=int, default=5, help="Number of RL steps to execute")
  parser.add_argument("--seed", type=int, default=0, help="Random seed")
  parser.add_argument("--output", type=Path, default=Path("rl_runs"), help="Directory to store checkpoints and stats")
  parser.add_argument("--resume-warmup", type=int, default=1, help="Warmup instructions to run before each measurement window")
  parser.add_argument(
      "--agent",
      choices=["ppo", "random", "epsilon_greedy", "hash_table"],
      default="ppo",
      help="Policy used to select actions",
  )
  parser.add_argument("--epsilon", type=float, default=0.1, help="Exploration rate for epsilon-greedy/hash-table policies")
  parser.add_argument("--state-dim", type=int, default=7, help="State vector dimension expected by PPO (ignored otherwise)")
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
  return parser.parse_args()


def main() -> None:
  args = parse_args()
  repo_root = Path(__file__).resolve().parents[1]

  action_space, base_action, template_config = load_action_space(args.config.resolve())
  build_manager = ChampSimBuildManager(repo_root=repo_root, template_config=template_config.resolve())

  runner = ChampSimRunner(
      repo_root=repo_root,
      build_manager=build_manager,
      trace_path=args.trace.resolve(),
      warmup_instructions=args.warmup,
      window_instructions=args.window,
      output_dir=args.output.resolve(),
      resume_warmup=args.resume_warmup,
  )

  base_checkpoint = runner.initialise_checkpoint(base_action, action_space)

  if args.agent == "random":
    agent = RandomAgent(action_space, seed=args.seed)
  elif args.agent == "epsilon_greedy":
    agent = EpsilonGreedyAgent(action_space, epsilon=args.epsilon, seed=args.seed)
  elif args.agent == "hash_table":
    table_path = args.hash_table.resolve() if args.hash_table is not None else (args.output.resolve() / "hash_table.json")
    agent = HashTableAgent(
        action_space=action_space,
        cutoffs=args.hash_cutoffs,
        epsilon=args.epsilon,
        seed=args.seed,
        table_path=table_path,
        initial_action=base_action,
    )
  else:
    agent = PPOAgent(
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
  episode_log: List[dict] = []

  state = None
  for step in range(args.steps):
    action = agent.select_action(state)
    result = runner.run_window(action, action_space, base_checkpoint, step)
    metrics = result.metrics
    next_state = metrics.feature_vector
    reward = metrics.ipc
    agent.observe(state, action, reward, next_state)
    state = next_state

    episode_log.append(
        {
            "step": step,
            "action": action.values,
            "reward": reward,
            "ipc": metrics.ipc,
            "l1d_mpki": metrics.l1d_mpki,
            "l2_mpki": metrics.l2_mpki,
            "llc_mpki": metrics.llc_mpki,
            "prefetch_coverage": metrics.prefetch_coverage,
            "prefetch_accuracy": metrics.prefetch_accuracy,
            "branch_miss_rate": metrics.branch_miss_rate,
            "skip_instructions": result.skip_instructions,
            "stats_path": str(result.stats_path),
            "cache_path": str(result.cache_path),
        }
    )
    print(f"[step {step}] action={action.values} IPC={metrics.ipc:.6f} reward={reward:.6f}")

  agent.finalize(state)

  summary_path = args.output / "episode_summary.json"
  with summary_path.open("w", encoding="utf-8") as handle:
    json.dump(episode_log, handle, indent=2)

  print(f"Episode summary saved to {summary_path}")


if __name__ == "__main__":
  main()
