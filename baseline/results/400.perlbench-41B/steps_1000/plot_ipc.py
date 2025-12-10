#!/usr/bin/env python3
"""Plot IPC vs step for each experiment_summary.json in subdirectories."""

import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Use a non-GUI backend so saving works in headless setups.
import matplotlib.pyplot as plt


def load_ipc(summary_path: Path):
    """Return step->ipc mapping from a single experiment_summary.json file."""
    data = json.loads(summary_path.read_text())
    episodes = data.get("rl", {}).get("episode", [])
    return {entry["step"]: entry["ipc"] for entry in episodes if "step" in entry and "ipc" in entry}


def main():
    root = Path(__file__).resolve().parent
    summaries = sorted(
        p for p in root.iterdir() if p.is_dir() and (p / "experiment_summary.json").exists()
    )
    if not summaries:
        raise SystemExit("No experiment_summary.json files found in subdirectories.")

    plt.figure(figsize=(10, 6))
    series = {}
    for folder in summaries:
        step_ipc = load_ipc(folder / "experiment_summary.json")
        if not step_ipc:
            continue
        steps_sorted = sorted(step_ipc)
        plt.plot(
            steps_sorted,
            [step_ipc[s] for s in steps_sorted],
            marker="o",
            markersize=2,
            linewidth=1.2,
            label=folder.name,
        )
        series[folder.name] = step_ipc

    plt.xlabel("step")
    plt.ylabel("ipc")
    plt.title("IPC per step")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()

    output_path = root / "ipc_plot.png"
    plt.savefig(output_path, dpi=200)
    print(f"Saved plot to {output_path}")

    # Check whether the same variant holds the max IPC at every step.
    if not series:
        raise SystemExit("No IPC data found.")

    all_steps = sorted({step for data in series.values() for step in data})
    winners_by_step = {}
    for step in all_steps:
        max_ipc = None
        winners = []
        for name, data in series.items():
            if step not in data:
                continue
            ipc_val = data[step]
            if max_ipc is None or ipc_val > max_ipc:
                max_ipc = ipc_val
                winners = [name]
            elif ipc_val == max_ipc:
                winners.append(name)
        winners_by_step[step] = winners

    all_winners = {w for winners in winners_by_step.values() for w in winners}
    single_winner = len(all_winners) == 1 and all(len(w) == 1 for w in winners_by_step.values())

    if single_winner:
        winner_name = next(iter(all_winners))
        print(f"Same variant has max IPC at every step: {winner_name}")
    else:
        print("Not the same variant at every step (ties included).")
        counts = Counter(w for winners in winners_by_step.values() for w in winners)
        print("Max IPC counts per variant:", dict(counts))
        print("Step-wise max IPC winners:")
        for step in all_steps:
            winners = ", ".join(winners_by_step[step])
            print(f"  step {step}: {winners}")


if __name__ == "__main__":
    main()
