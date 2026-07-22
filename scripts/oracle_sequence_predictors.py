#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import glob
import json
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

EPS = 1e-12
BERTI = "Berti"
GAZE = "Gaze"


@dataclass
class Step:
    trace: str
    idx: int
    berti_ipc: float
    gaze_ipc: float

    @property
    def oracle_ipc(self) -> float:
        return max(self.berti_ipc, self.gaze_ipc)

    @property
    def tie(self) -> bool:
        return abs(self.berti_ipc - self.gaze_ipc) <= EPS


def policy_ipc(step: Step, policy: str) -> float:
    if policy == BERTI:
        return step.berti_ipc
    if policy == GAZE:
        return step.gaze_ipc
    raise ValueError(policy)


def load_trace(path: Path) -> List[Step]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    trace = path.parent.name
    steps: List[Step] = []
    for row in data.get("per_step_comparison", {}).get("results", []):
        per_action = row.get("per_action_ipc", {})
        berti = [v for k, v in per_action.items() if "l1d_prefetcher-berti" in k]
        gaze = [v for k, v in per_action.items() if "l1d_prefetcher-gaze" in k]
        if len(berti) != 1 or len(gaze) != 1:
            continue
        steps.append(
            Step(
                trace=trace,
                idx=int(row.get("step", len(steps))),
                berti_ipc=float(berti[0]),
                gaze_ipc=float(gaze[0]),
            )
        )
    return steps


def load_traces(pattern: str) -> Dict[str, List[Step]]:
    traces = {}
    for raw in sorted(glob.glob(pattern)):
        path = Path(raw)
        steps = load_trace(path)
        if steps:
            traces[path.parent.name] = steps
    return traces


def oracle_labels(steps: Sequence[Step], default: str = GAZE) -> List[str]:
    labels: List[str] = []
    last = default
    for step in steps:
        if step.berti_ipc > step.gaze_ipc + EPS:
            last = BERTI
        elif step.gaze_ipc > step.berti_ipc + EPS:
            last = GAZE
        labels.append(last)
    return labels


def majority(values: Iterable[str], default: str) -> str:
    counts = Counter(values)
    if counts[BERTI] > counts[GAZE]:
        return BERTI
    if counts[GAZE] > counts[BERTI]:
        return GAZE
    return default


class Predictor:
    name = "base"

    def train(self, labels: Sequence[str]) -> None:
        raise NotImplementedError

    def predict(self) -> str:
        raise NotImplementedError

    def update(self, label: str) -> None:
        raise NotImplementedError


class LastOracle(Predictor):
    name = "last_oracle"

    def __init__(self, default: str = GAZE) -> None:
        self.last = default

    def train(self, labels: Sequence[str]) -> None:
        if labels:
            self.last = labels[-1]

    def predict(self) -> str:
        return self.last

    def update(self, label: str) -> None:
        self.last = label


class MajorityK(Predictor):
    def __init__(self, k: int, default: str = GAZE) -> None:
        self.k = k
        self.default = default
        self.name = f"majority_{k}"
        self.hist: deque[str] = deque(maxlen=k)

    def train(self, labels: Sequence[str]) -> None:
        self.hist.clear()
        for label in labels[-self.k :]:
            self.hist.append(label)

    def predict(self) -> str:
        if not self.hist:
            return self.default
        return majority(self.hist, self.hist[-1])

    def update(self, label: str) -> None:
        self.hist.append(label)


class MarkovK(Predictor):
    def __init__(self, k: int, default: str = GAZE) -> None:
        self.k = k
        self.default = default
        self.name = f"markov_{k}"
        self.hist: deque[str] = deque(maxlen=k)
        self.table: Dict[Tuple[str, ...], Counter[str]] = defaultdict(Counter)

    def train(self, labels: Sequence[str]) -> None:
        self.hist.clear()
        self.table.clear()
        for i in range(self.k, len(labels)):
            context = tuple(labels[i - self.k : i])
            self.table[context][labels[i]] += 1
        for label in labels[-self.k :]:
            self.hist.append(label)

    def predict(self) -> str:
        if len(self.hist) < self.k:
            return self.hist[-1] if self.hist else self.default
        counts = self.table.get(tuple(self.hist))
        if not counts:
            return self.hist[-1]
        return majority(counts.elements(), self.hist[-1])

    def update(self, label: str) -> None:
        if len(self.hist) == self.k:
            self.table[tuple(self.hist)][label] += 1
        self.hist.append(label)


def evaluate_trace(
    trace: str,
    steps: Sequence[Step],
    predictor: Predictor,
    train_windows: int,
) -> Tuple[Dict[str, object], List[Dict[str, object]]]:
    labels = oracle_labels(steps)
    train_end = min(train_windows, len(steps) - 1)
    predictor.train(labels[:train_end])
    rows: List[Dict[str, object]] = []
    loss_sum = 0.0
    selected_ipc_sum = 0.0
    oracle_ipc_sum = 0.0
    gaze_ipc_sum = 0.0
    strict_correct = 0
    tie_aware_correct = 0
    evaluated = 0

    for i in range(train_end, len(steps)):
        step = steps[i]
        predicted = predictor.predict()
        selected_ipc = policy_ipc(step, predicted)
        oracle_ipc = step.oracle_ipc
        loss = 0.0 if oracle_ipc <= EPS else 100.0 * (oracle_ipc - selected_ipc) / oracle_ipc
        strict = predicted == labels[i] and not step.tie
        tie_aware = abs(selected_ipc - oracle_ipc) <= EPS
        gain_vs_gaze = 0.0 if step.gaze_ipc <= EPS else 100.0 * (selected_ipc - step.gaze_ipc) / step.gaze_ipc

        rows.append(
            {
                "trace": trace,
                "step": step.idx,
                "method": predictor.name,
                "predicted_policy": predicted,
                "oracle_label": "Tie" if step.tie else labels[i],
                "selected_ipc": selected_ipc,
                "berti_ipc": step.berti_ipc,
                "gaze_ipc": step.gaze_ipc,
                "oracle_ipc": oracle_ipc,
                "loss_vs_two_policy_oracle_pct": loss,
                "gain_vs_gaze_pct": gain_vs_gaze,
                "strict_correct": int(strict),
                "tie_aware_correct": int(tie_aware),
                "is_train_window": 0,
            }
        )

        loss_sum += loss
        selected_ipc_sum += selected_ipc
        oracle_ipc_sum += oracle_ipc
        gaze_ipc_sum += step.gaze_ipc
        strict_correct += int(strict)
        tie_aware_correct += int(tie_aware)
        evaluated += 1
        predictor.update(labels[i])

    summary = {
        "method": predictor.name,
        "trace": trace,
        "train_windows": train_end,
        "test_windows": evaluated,
        "selector_total_ipc": selected_ipc_sum,
        "always_gaze_total_ipc": gaze_ipc_sum,
        "oracle_total_ipc": oracle_ipc_sum,
        "gain_vs_always_gaze_pct": 100.0 * (selected_ipc_sum - gaze_ipc_sum) / gaze_ipc_sum if gaze_ipc_sum > EPS else 0.0,
        "mean_loss_vs_two_policy_oracle_pct": loss_sum / evaluated if evaluated else 0.0,
        "aggregate_loss_vs_two_policy_oracle_pct": 100.0 * (oracle_ipc_sum - selected_ipc_sum) / oracle_ipc_sum if oracle_ipc_sum > EPS else 0.0,
        "strict_action_accuracy_pct": 100.0 * strict_correct / evaluated if evaluated else 0.0,
        "tie_aware_accuracy_pct": 100.0 * tie_aware_correct / evaluated if evaluated else 0.0,
    }
    return summary, rows


def aggregate(rows: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["method"])].append(row)
    out = []
    for method, items in sorted(grouped.items()):
        selector_total = sum(float(r["selector_total_ipc"]) for r in items)
        gaze_total = sum(float(r["always_gaze_total_ipc"]) for r in items)
        oracle_total = sum(float(r["oracle_total_ipc"]) for r in items)
        test_windows = sum(int(r["test_windows"]) for r in items)
        out.append(
            {
                "method": method,
                "num_traces": len(items),
                "test_windows": test_windows,
                "selector_total_ipc": selector_total,
                "always_gaze_total_ipc": gaze_total,
                "oracle_total_ipc": oracle_total,
                "gain_vs_always_gaze_pct": 100.0 * (selector_total - gaze_total) / gaze_total if gaze_total > EPS else 0.0,
                "mean_loss_vs_two_policy_oracle_pct": sum(float(r["mean_loss_vs_two_policy_oracle_pct"]) * int(r["test_windows"]) for r in items) / test_windows,
                "aggregate_loss_vs_two_policy_oracle_pct": 100.0 * (oracle_total - selector_total) / oracle_total if oracle_total > EPS else 0.0,
                "strict_action_accuracy_pct": sum(float(r["strict_action_accuracy_pct"]) * int(r["test_windows"]) for r in items) / test_windows,
                "tie_aware_accuracy_pct": sum(float(r["tie_aware_accuracy_pct"]) * int(r["test_windows"]) for r in items) / test_windows,
            }
        )
    return out


def write_csv(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def predictors() -> List[Predictor]:
    out: List[Predictor] = [LastOracle()]
    out.extend(MajorityK(k) for k in (3, 5, 7, 9))
    out.extend(MarkovK(k) for k in (1, 2, 3, 4, 5))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate oracle-sequence predictors using two-policy shadow IPC.")
    parser.add_argument("--pattern", default="rl_real_two_policy/49_traces/*/experiment_summary.json")
    parser.add_argument("--output", type=Path, default=Path("rl_real_two_policy/49_traces/oracle_sequence_predictors"))
    parser.add_argument("--train-windows", type=int, default=20)
    args = parser.parse_args()

    traces = load_traces(args.pattern)
    if not traces:
        raise SystemExit(f"No traces found for pattern {args.pattern}")

    per_trace_rows: List[Dict[str, object]] = []
    sequence_rows: List[Dict[str, object]] = []
    for trace, steps in traces.items():
        for predictor in predictors():
            summary, rows = evaluate_trace(trace, steps, predictor, args.train_windows)
            per_trace_rows.append(summary)
            sequence_rows.extend(rows)

    summary_rows = aggregate(per_trace_rows)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", summary_rows)
    write_csv(args.output / "per_trace_summary.csv", per_trace_rows)
    write_csv(args.output / "sequence_predictions.csv", sequence_rows)
    with (args.output / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump({"train_windows": args.train_windows, "summary": summary_rows}, handle, indent=2)

    print(f"Loaded {len(traces)} traces; train_windows={args.train_windows}")
    for row in summary_rows:
        print(
            f"{row['method']:12s} "
            f"loss={float(row['mean_loss_vs_two_policy_oracle_pct']):7.4f}% "
            f"agg_loss={float(row['aggregate_loss_vs_two_policy_oracle_pct']):7.4f}% "
            f"gain_gaze={float(row['gain_vs_always_gaze_pct']):7.4f}% "
            f"strict={float(row['strict_action_accuracy_pct']):6.2f}% "
            f"tie={float(row['tie_aware_accuracy_pct']):6.2f}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
