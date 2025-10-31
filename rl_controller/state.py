from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping
import json
import math
from pathlib import Path


@dataclass
class WindowMetrics:
  instructions: float
  cycles: float
  ipc: float
  l1d_mpki: float
  l2_mpki: float
  llc_mpki: float
  prefetch_coverage: float
  prefetch_accuracy: float
  branch_miss_rate: float

  @property
  def feature_vector(self) -> List[float]:
    return [
        self.ipc,
        self.l1d_mpki,
        self.l2_mpki,
        self.llc_mpki,
        self.prefetch_coverage,
        self.prefetch_accuracy,
        self.branch_miss_rate,
    ]


def _safe_div(num: float, den: float) -> float:
  if den == 0:
    return 0.0
  return num / den


def parse_stats_json(stats_path: Path) -> WindowMetrics:
  with stats_path.open("r", encoding="utf-8") as handle:
    data = json.load(handle)

  if not data:
    raise ValueError(f"Stats file {stats_path} is empty")

  phase = data[0]["sim"]
  core = phase["cores"][0]
  instructions = float(core.get("instructions", 0))
  cycles = float(core.get("cycles", 0))
  ipc = _safe_div(instructions, cycles)

  l1d = phase["cpu0_L1D"]
  l2c = phase["cpu0_L2C"]
  llc = phase["LLC"]

  l1d_misses = _load_total_misses(l1d)
  l2_misses = _load_total_misses(l2c)
  llc_misses = _load_total_misses(llc)

  l1d_mpki = _safe_div(l1d_misses * 1000.0, instructions)
  l2_mpki = _safe_div(l2_misses * 1000.0, instructions)
  llc_mpki = _safe_div(llc_misses * 1000.0, instructions)

  useful_prefetch = float(l1d.get("useful prefetch", 0))
  issued_prefetch = float(l1d.get("prefetch issued", 0))

  prefetch_coverage = _safe_div(useful_prefetch, l1d_misses) if l1d_misses else 0.0
  prefetch_accuracy = _safe_div(useful_prefetch, issued_prefetch) if issued_prefetch else 0.0

  mispredicts = core.get("mispredict", {})
  branch_total = sum(mispredicts.values())
  branch_miss_rate = _safe_div(branch_total, instructions) if branch_total else 0.0

  return WindowMetrics(
      instructions=instructions,
      cycles=cycles,
      ipc=ipc,
      l1d_mpki=l1d_mpki,
      l2_mpki=l2_mpki,
      llc_mpki=llc_mpki,
      prefetch_coverage=prefetch_coverage,
      prefetch_accuracy=prefetch_accuracy,
      branch_miss_rate=branch_miss_rate,
  )


def _load_total_misses(node: Mapping) -> float:
  total = 0.0
  for bucket in ("LOAD", "WRITE", "TRANSLATION", "PREFETCH", "RFO"):
    entry = node.get(bucket, {})
    misses = entry.get("miss", [])
    if misses:
      total += float(misses[0])
  return total
