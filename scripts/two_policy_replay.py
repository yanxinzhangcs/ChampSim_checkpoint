#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import random
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

EPS = 1e-12


@dataclass
class Step:
    trace: str
    idx: int
    per_action_ipc: Dict[str, float]

    @property
    def full_oracle_ipc(self) -> float:
        return max(self.per_action_ipc.values())


@dataclass
class TraceData:
    name: str
    path: Path
    steps: List[Step]


def trace_name_from_path(path: Path) -> str:
    name = path.parent.name
    return name[:-6] if name.endswith("_combo") else name


def load_traces(pattern: str) -> List[TraceData]:
    traces: List[TraceData] = []
    for raw in sorted(glob.glob(pattern)):
        path = Path(raw)
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        rows = data.get("per_step_comparison", {}).get("results", [])
        steps: List[Step] = []
        trace = trace_name_from_path(path)
        for row in rows:
            per_action = row.get("per_action_ipc") or {}
            if not per_action:
                continue
            steps.append(
                Step(
                    trace=trace,
                    idx=int(row.get("step", len(steps))),
                    per_action_ipc={k: float(v) for k, v in per_action.items()},
                )
            )
        if steps:
            traces.append(TraceData(name=trace, path=path, steps=steps))
    return traces


def all_steps(traces: Iterable[TraceData]) -> List[Step]:
    return [step for trace in traces for step in trace.steps]


def common_actions(traces: Sequence[TraceData]) -> List[str]:
    action_sets = [set(step.per_action_ipc) for step in all_steps(traces)]
    if not action_sets:
        return []
    return sorted(set.intersection(*action_sets))


def mean_loss_pct(steps: Sequence[Step], chooser: Callable[[Step], str]) -> Tuple[float, float, float]:
    losses = []
    within_05 = 0
    exact = 0
    for step in steps:
        oracle = step.full_oracle_ipc
        action = chooser(step)
        val = step.per_action_ipc[action]
        loss = 0.0 if oracle <= EPS else 100.0 * (oracle - val) / oracle
        losses.append(loss)
        if loss <= 0.5 + 1e-9:
            within_05 += 1
        if abs(val - oracle) <= 1e-12:
            exact += 1
    if not losses:
        return 0.0, 0.0, 0.0
    n = len(losses)
    return sum(losses) / n, 100.0 * exact / n, 100.0 * within_05 / n


def select_best_static(steps: Sequence[Step], actions: Sequence[str]) -> str:
    scores = {}
    for action in actions:
        loss, _, _ = mean_loss_pct(steps, lambda _s, a=action: a)
        scores[action] = loss
    return min(scores, key=scores.get)


def select_best_complement(steps: Sequence[Step], actions: Sequence[str], p0: str) -> str:
    candidates = [a for a in actions if a != p0]
    scores = {}
    for action in candidates:
        def choose(step: Step, a=action) -> str:
            return p0 if step.per_action_ipc[p0] >= step.per_action_ipc[a] else a
        loss, _, _ = mean_loss_pct(steps, choose)
        scores[action] = loss
    return min(scores, key=scores.get)


def eval_static_pair_oracle(steps: Sequence[Step], p0: str, p1: str) -> Tuple[float, float, float]:
    return mean_loss_pct(steps, lambda s: p0 if s.per_action_ipc[p0] >= s.per_action_ipc[p1] else p1)


def replay_random(traces: Sequence[TraceData], p0: str, p1: str, seed: int) -> Tuple[float, float, float]:
    rng = random.Random(seed)
    chosen: Dict[Tuple[str, int], str] = {}
    for trace in traces:
        for step in trace.steps:
            chosen[(trace.name, step.idx)] = p0 if rng.random() < 0.5 else p1
    return mean_loss_pct(all_steps(traces), lambda s: chosen[(s.trace, s.idx)])


def replay_epsilon_greedy(traces: Sequence[TraceData], p0: str, p1: str, seed: int, epsilon: float) -> Tuple[float, float, float]:
    rng = random.Random(seed)
    chosen: Dict[Tuple[str, int], str] = {}
    for trace in traces:
        counts = {p0: 0, p1: 0}
        values = {p0: 0.0, p1: 0.0}
        for local_idx, step in enumerate(trace.steps):
            if counts[p0] == 0:
                action = p0
            elif counts[p1] == 0:
                action = p1
            elif rng.random() < epsilon:
                action = p0 if rng.random() < 0.5 else p1
            else:
                if values[p0] == values[p1]:
                    action = p0 if rng.random() < 0.5 else p1
                else:
                    action = p0 if values[p0] > values[p1] else p1
            reward = step.per_action_ipc[action]
            counts[action] += 1
            values[action] += (reward - values[action]) / counts[action]
            chosen[(trace.name, step.idx)] = action
    return mean_loss_pct(all_steps(traces), lambda s: chosen[(s.trace, s.idx)])


def replay_sliding_epsilon(traces: Sequence[TraceData], p0: str, p1: str, seed: int, epsilon: float, window: int) -> Tuple[float, float, float]:
    rng = random.Random(seed)
    chosen: Dict[Tuple[str, int], str] = {}
    for trace in traces:
        hist = {p0: deque(maxlen=window), p1: deque(maxlen=window)}
        for step in trace.steps:
            if not hist[p0]:
                action = p0
            elif not hist[p1]:
                action = p1
            elif rng.random() < epsilon:
                action = p0 if rng.random() < 0.5 else p1
            else:
                m0 = sum(hist[p0]) / len(hist[p0])
                m1 = sum(hist[p1]) / len(hist[p1])
                action = p0 if m0 >= m1 else p1
            reward = step.per_action_ipc[action]
            hist[action].append(reward)
            chosen[(trace.name, step.idx)] = action
    return mean_loss_pct(all_steps(traces), lambda s: chosen[(s.trace, s.idx)])


def replay_exp3(traces: Sequence[TraceData], p0: str, p1: str, seed: int, gamma: float) -> Tuple[float, float, float]:
    rng = random.Random(seed)
    chosen: Dict[Tuple[str, int], str] = {}
    arms = [p0, p1]
    for trace in traces:
        weights = {p0: 1.0, p1: 1.0}
        observed_max = EPS
        for step in trace.steps:
            total = weights[p0] + weights[p1]
            probs = {a: (1.0 - gamma) * weights[a] / total + gamma / 2.0 for a in arms}
            action = p0 if rng.random() < probs[p0] else p1
            reward_raw = step.per_action_ipc[action]
            observed_max = max(observed_max, reward_raw)
            reward = max(0.0, min(1.0, reward_raw / observed_max))
            estimated = reward / max(probs[action], EPS)
            weights[action] *= math.exp(gamma * estimated / 2.0)
            chosen[(trace.name, step.idx)] = action
    return mean_loss_pct(all_steps(traces), lambda s: chosen[(s.trace, s.idx)])


def average_seeded(fn: Callable[[int], Tuple[float, float, float]], seeds: int) -> Tuple[float, float, float]:
    vals = [fn(seed) for seed in range(seeds)]
    return tuple(sum(v[i] for v in vals) / len(vals) for i in range(3))  # type: ignore[return-value]


def evaluate_dataset(traces: Sequence[TraceData], actions: Sequence[str], seeds: int) -> Tuple[List[Dict[str, object]], Tuple[str, str]]:
    steps = all_steps(traces)
    p0 = select_best_static(steps, actions)
    p1 = select_best_complement(steps, actions, p0)
    rows: List[Dict[str, object]] = []

    def add(method: str, metrics: Tuple[float, float, float]) -> None:
        rows.append({
            "method": method,
            "p0": p0,
            "p1": p1,
            "mean_loss_pct": metrics[0],
            "oracle_match_pct": metrics[1],
            "within_0p5_pct": metrics[2],
        })

    add("best_static_p0", mean_loss_pct(steps, lambda _s: p0))
    add("static_p1", mean_loss_pct(steps, lambda _s: p1))
    add("two_policy_oracle", eval_static_pair_oracle(steps, p0, p1))
    add("random_binary", average_seeded(lambda seed: replay_random(traces, p0, p1, seed), seeds))
    add("epsilon_greedy_0p10", average_seeded(lambda seed: replay_epsilon_greedy(traces, p0, p1, seed, 0.10), seeds))
    add("sliding_epsilon_w5_0p10", average_seeded(lambda seed: replay_sliding_epsilon(traces, p0, p1, seed, 0.10, 5), seeds))
    add("exp3_gamma_0p10", average_seeded(lambda seed: replay_exp3(traces, p0, p1, seed, 0.10), seeds))
    return rows, (p0, p1)


def leave_one_trace_out(traces: Sequence[TraceData], actions: Sequence[str], seeds: int) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for held in traces:
        train = [t for t in traces if t.name != held.name]
        train_steps = all_steps(train)
        p0 = select_best_static(train_steps, actions)
        p1 = select_best_complement(train_steps, actions, p0)
        test = [held]
        test_steps = held.steps

        def add(method: str, metrics: Tuple[float, float, float]) -> None:
            rows.append({
                "heldout_trace": held.name,
                "method": method,
                "p0": p0,
                "p1": p1,
                "mean_loss_pct": metrics[0],
                "oracle_match_pct": metrics[1],
                "within_0p5_pct": metrics[2],
            })

        add("best_static_p0", mean_loss_pct(test_steps, lambda _s: p0))
        add("two_policy_oracle", eval_static_pair_oracle(test_steps, p0, p1))
        add("random_binary", average_seeded(lambda seed: replay_random(test, p0, p1, seed), seeds))
        add("epsilon_greedy_0p10", average_seeded(lambda seed: replay_epsilon_greedy(test, p0, p1, seed, 0.10), seeds))
        add("sliding_epsilon_w5_0p10", average_seeded(lambda seed: replay_sliding_epsilon(test, p0, p1, seed, 0.10, 5), seeds))
        add("exp3_gamma_0p10", average_seeded(lambda seed: replay_exp3(test, p0, p1, seed, 0.10), seeds))
    return rows


def aggregate_loto(rows: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["method"])].append(row)
    out: List[Dict[str, object]] = []
    for method, items in sorted(grouped.items()):
        out.append({
            "method": method,
            "mean_loss_pct": sum(float(r["mean_loss_pct"]) for r in items) / len(items),
            "oracle_match_pct": sum(float(r["oracle_match_pct"]) for r in items) / len(items),
            "within_0p5_pct": sum(float(r["within_0p5_pct"]) for r in items) / len(items),
        })
    return out


def write_csv(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay two-policy runtime selectors from existing ChampSim per-step grids")
    parser.add_argument("--pattern", default="rl_results_final/*_combo/experiment_summary.json")
    parser.add_argument("--output", type=Path, default=Path("two_policy_replay_results"))
    parser.add_argument("--seeds", type=int, default=50)
    args = parser.parse_args()

    traces = load_traces(args.pattern)
    if not traces:
        raise SystemExit(f"No traces found for pattern {args.pattern}")
    actions = common_actions(traces)
    if len(actions) < 2:
        raise SystemExit("Need at least two common actions")

    all_rows, pair = evaluate_dataset(traces, actions, args.seeds)
    loto_rows = leave_one_trace_out(traces, actions, args.seeds)
    loto_summary = aggregate_loto(loto_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "all_data_summary.csv", all_rows)
    write_csv(args.output / "leave_one_trace_out.csv", loto_rows)
    write_csv(args.output / "leave_one_trace_out_summary.csv", loto_summary)

    metadata = {
        "pattern": args.pattern,
        "num_traces": len(traces),
        "num_steps": len(all_steps(traces)),
        "num_actions": len(actions),
        "selected_pair_all_data": {"p0": pair[0], "p1": pair[1]},
        "actions": actions,
    }
    with (args.output / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)

    print(json.dumps(metadata, indent=2))
    print("\nAll-data replay:")
    for row in all_rows:
        print(f"{row['method']:24s} loss={float(row['mean_loss_pct']):7.4f}% match={float(row['oracle_match_pct']):6.2f}% within0.5={float(row['within_0p5_pct']):6.2f}%")
    print("\nLeave-one-trace-out replay:")
    for row in loto_summary:
        print(f"{row['method']:24s} loss={float(row['mean_loss_pct']):7.4f}% match={float(row['oracle_match_pct']):6.2f}% within0.5={float(row['within_0p5_pct']):6.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
