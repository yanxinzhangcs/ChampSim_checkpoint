from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from .action_space import Action, ActionSpace
from .builder import ChampSimBuildManager
from .state import WindowMetrics, parse_stats_json


@dataclass
class RunResult:
  action: Action
  metrics: WindowMetrics
  stats_path: Path
  cache_path: Path


class ChampSimRunner:
  """Execute ChampSim windows under RL control."""

  def __init__(
      self,
      repo_root: Path,
      build_manager: ChampSimBuildManager,
      trace_path: Path,
      warmup_instructions: int,
      window_instructions: int,
      output_dir: Path,
      shared_base: bool,
      resume_warmup: int,
  ):
    self.repo_root = repo_root
    self.build_manager = build_manager
    self.trace_path = trace_path
    self.warmup_instructions = warmup_instructions
    self.window_instructions = window_instructions
    self.output_dir = output_dir
    self.output_dir.mkdir(parents=True, exist_ok=True)
    self.shared_base = shared_base
    self.resume_warmup = resume_warmup
    self._shared_checkpoint: Path | None = None
    self._action_checkpoints: dict[str, Path] = {}

  def initialise_checkpoint(self, base_action: Action, action_space: ActionSpace) -> Path:
    """Generate (or reuse) the baseline cache checkpoint."""
    if self.shared_base:
      if self._shared_checkpoint is None:
        self._shared_checkpoint = self._create_checkpoint(base_action, action_space, suffix="base")
      return self._shared_checkpoint

    # Per-action warmup still benefits from caching the base policy
    key = self._action_key(base_action)
    if key not in self._action_checkpoints:
      self._action_checkpoints[key] = self._create_checkpoint(base_action, action_space, suffix=f"warm_{key}")
    return self._action_checkpoints[key]

  def run_window(
      self,
      action: Action,
      action_space: ActionSpace,
      base_checkpoint: Path,
      step: int,
  ) -> RunResult:
    updates = action.as_config_updates(action_space.heads)
    build = self.build_manager.ensure_binary(updates)

    if self.shared_base:
      source_checkpoint = self._shared_checkpoint or base_checkpoint
    else:
      action_key = self._action_key(action)
      source_checkpoint = self._action_checkpoints.get(action_key)
      if source_checkpoint is None:
        source_checkpoint = self._create_checkpoint(action, action_space, suffix=f"warm_{action_key}")
        self._action_checkpoints[action_key] = source_checkpoint

    cache_path = self.output_dir / f"iter_{step:04d}_cache.log"
    shutil.copy2(source_checkpoint, cache_path)

    stats_path = self.output_dir / f"iter_{step:04d}_stats.json"
    cmd = (
        f"{build.binary_path} "
        f"--warmup-instructions {self.resume_warmup} "
        f"--simulation-instructions {self.window_instructions} "
        f"--subtrace-count 1 "
        f"--cache-checkpoint {cache_path} "
        f"--json {stats_path} "
        f"{self.trace_path}"
    )
    subprocess.run(["bash", "-lc", cmd], cwd=self.repo_root, check=True)

    metrics = parse_stats_json(stats_path)
    return RunResult(action=action, metrics=metrics, stats_path=stats_path, cache_path=cache_path)

  def _create_checkpoint(self, action: Action, action_space: ActionSpace, suffix: str) -> Path:
    updates = action.as_config_updates(action_space.heads)
    build = self.build_manager.ensure_binary(updates)

    checkpoint_path = self.output_dir / f"{suffix}_cache.log"
    json_path = self.output_dir / f"{suffix}_warmup.json"
    cmd = (
        f"{build.binary_path} "
        f"--warmup-instructions {self.warmup_instructions} "
        f"--simulation-instructions 0 "
        f"--subtrace-count 1 "
        f"--cache-checkpoint {checkpoint_path} "
        f"--json {json_path} "
        f"{self.trace_path}"
    )
    subprocess.run(["bash", "-lc", cmd], cwd=self.repo_root, check=True)
    return checkpoint_path

  @staticmethod
  def _action_key(action: Action) -> str:
    return "_".join(f"{k}-{v}" for k, v in sorted(action.values.items()))
