from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from .action_space import Action, ActionSpace, load_action_space
from .agent import EpsilonGreedyAgent, RandomAgent
from .builder import ChampSimBuildManager
from .runner import ChampSimRunner


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
  parser.add_argument("--agent", choices=["random", "epsilon_greedy"], default="epsilon_greedy", help="Policy used to select actions")
  parser.add_argument("--epsilon", type=float, default=0.1, help="Exploration rate for epsilon-greedy policy")
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
  else:
    agent = EpsilonGreedyAgent(action_space, epsilon=args.epsilon, seed=args.seed)
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

  summary_path = args.output / "episode_summary.json"
  with summary_path.open("w", encoding="utf-8") as handle:
    json.dump(episode_log, handle, indent=2)

  print(f"Episode summary saved to {summary_path}")


if __name__ == "__main__":
  main()
