from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping


@dataclass
class BuildResult:
  binary_path: Path
  config_path: Path


class ChampSimBuildManager:
  """Generate policy-specific ChampSim binaries on demand."""

  def __init__(self, repo_root: Path, template_config: Path, build_root: Path | None = None):
    self.repo_root = repo_root
    self.template_config = template_config
    self.build_root = build_root or repo_root / "rl_controller" / "build_configs"
    self.build_root.mkdir(parents=True, exist_ok=True)
    self.bin_root = repo_root / "bin"

  def _binary_name(self, action_updates: Mapping[str, str]) -> str:
    suffix = "_".join(f"{key.replace('.', '-')}-{value}" for key, value in sorted(action_updates.items()))
    return f"champsim_rl_{suffix}"

  def ensure_binary(self, action_updates: Mapping[str, str]) -> BuildResult:
    name = self._binary_name(action_updates)
    binary_path = self.bin_root / name
    config_path = self.build_root / f"{name}.json"

    if not binary_path.exists():
      self._build_binary(name, binary_path, config_path, action_updates)

    return BuildResult(binary_path=binary_path, config_path=config_path)

  def _build_binary(
      self, name: str, binary_path: Path, config_path: Path, action_updates: Mapping[str, str]
  ) -> None:
    with self.template_config.open("r", encoding="utf-8") as handle:
      config = json.load(handle)

    config["executable_name"] = name
    for dotted_path, value in action_updates.items():
      self._set_config_value(config, dotted_path.split("."), value)

    with config_path.open("w", encoding="utf-8") as handle:
      json.dump(config, handle, indent=2)

    # Reconfigure ChampSim for this binary
    subprocess.run(
        ["bash", "-lc", f"./config.sh {config_path}"],
        cwd=self.repo_root,
        check=True,
    )

    # Build the executable
    subprocess.run(
        ["bash", "-lc", f"make -j$(nproc) bin/{name}"],
        cwd=self.repo_root,
        check=True,
    )

    if not binary_path.exists():  # pragma: no cover - defensive
      raise FileNotFoundError(f"Expected binary {binary_path} was not produced.")

  @staticmethod
  def _set_config_value(config: Dict, path: list[str], value: str) -> None:
    ref = config
    for key in path[:-1]:
      if key not in ref or not isinstance(ref[key], dict):
        raise KeyError(f"Config does not contain path {'/'.join(path)}")
      ref = ref[key]
    ref[path[-1]] = value
