#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
  sys.path.insert(0, str(REPO_ROOT))

from rl_controller.action_space import load_action_space
from rl_controller.full_trace_policies import sanitize
from rl_controller.state import parse_stats_json

SSH_KEY = Path.home() / ".ssh" / "id_ed25519_junnan"
MANIFEST_PATH = REPO_ROOT / "dist" / "emulab_native_fulltrace_policy_split" / "remaining_jobs.tsv"
RESULT_ROOT = REPO_ROOT / "rl_results_native_no_ckpt_20M"
REMOTE_DIR = "champsim-fulltrace-native"


@dataclass(frozen=True)
class JobRow:
  node: str
  host: str
  session: str
  log_path: str
  trace: str
  policy_key: str
  output_dir: str

  @property
  def trace_stem(self) -> str:
    return self.trace.removesuffix(".champsimtrace.xz")

  @property
  def trace_dir(self) -> Path:
    return RESULT_ROOT / f"{self.trace_stem}_combo" / "fulltrace"

  @property
  def baseline_dir_name(self) -> str:
    return sanitize(self.policy_key)

  @property
  def local_baseline_dir(self) -> Path:
    return self.trace_dir / "baseline" / self.baseline_dir_name

  @property
  def remote_baseline_dir(self) -> str:
    return f"{REMOTE_DIR}/data/{self.output_dir}/baseline/{self.baseline_dir_name}/"


def load_jobs() -> list[JobRow]:
  rows: list[JobRow] = []
  with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
    for row in csv.DictReader(handle, delimiter="\t"):
      rows.append(
          JobRow(
              node=row["node"],
              host=row["host"],
              session=row["session"],
              log_path=row["log_path"],
              trace=row["trace"],
              policy_key=row["policy_key"],
              output_dir=row["output_dir"],
          )
      )
  return rows


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
  return subprocess.run(cmd, check=True, text=True, capture_output=True)


def rsync_dir(host: str, remote_dir: str, local_dir: Path) -> None:
  local_dir.mkdir(parents=True, exist_ok=True)
  run(
      [
          "rsync",
          "-az",
          "-e",
          f"ssh -i {SSH_KEY} -o BatchMode=yes -o StrictHostKeyChecking=accept-new",
          f"{host}:{remote_dir}",
          f"{local_dir}/",
      ]
  )


def pull_results(jobs: list[JobRow]) -> None:
  for job in jobs:
    rsync_dir(job.host, job.remote_baseline_dir, job.local_baseline_dir)
    print(f"[pulled] {job.node} {job.trace_stem} {job.policy_key}")


def build_summary(trace_stem: str) -> None:
  trace_dir = RESULT_ROOT / f"{trace_stem}_combo" / "fulltrace"
  config_path = REPO_ROOT / "rl_controller" / f"action_space_{trace_stem}_combo.json"
  action_space, _, _ = load_action_space(config_path.resolve())

  results: dict[str, dict[str, object]] = {}
  for action in action_space.all_actions():
    key = action.key()
    policy_dir = trace_dir / "baseline" / sanitize(key)
    stats_path = policy_dir / "full_trace_stats.json"
    log_path = policy_dir / "full_trace.log"
    if not stats_path.is_file():
      missing = [item.key() for item in action_space.all_actions() if not (trace_dir / "baseline" / sanitize(item.key()) / "full_trace_stats.json").is_file()]
      raise FileNotFoundError(f"Missing baseline stats for {trace_stem}: {missing}")
    metrics = parse_stats_json(stats_path)
    results[key] = {
        "total_ipc": metrics.ipc,
        "per_step_ipc": [metrics.ipc],
        "instructions": metrics.instructions,
        "cycles": metrics.cycles,
        "ipc": metrics.ipc,
        "stats_path": str(stats_path),
        "log_path": str(log_path),
    }

  best_key, best_data = max(results.items(), key=lambda item: float(item[1]["ipc"]))
  summary = {
      "config": {
          "trace": str((REPO_ROOT / "traces" / f"{trace_stem}.champsimtrace.xz").resolve()),
          "warmup": 1_000_000,
          "skip_instructions": 0,
          "simulation_instructions": 20_000_000,
          "action_space": str(config_path.resolve()),
      },
      "fixed_policies": results,
      "best_fixed_policy": {
          "action": best_key,
          "ipc": float(best_data["ipc"]),
      },
  }
  summary_path = trace_dir / "experiment_summary.json"
  summary_path.parent.mkdir(parents=True, exist_ok=True)
  summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
  print(f"[merged] {trace_stem} -> {summary_path}")


def main() -> int:
  if not MANIFEST_PATH.is_file():
    raise SystemExit(f"Manifest not found: {MANIFEST_PATH}")

  jobs = load_jobs()
  pull_results(jobs)

  trace_stems = sorted({job.trace_stem for job in jobs})
  for trace_stem in trace_stems:
    build_summary(trace_stem)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
