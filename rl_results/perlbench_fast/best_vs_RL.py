import json, csv
from pathlib import Path

root = Path("/home/ubuntu/yanxin/ChampSim_checkpoint/rl_results/perlbench_fast")  # adjust if you used another output dir
summary = json.loads((root / "experiment_summary.json").read_text())

rows = summary["per_step_comparison"]["results"]
csv_path = root / "rl_vs_optimal.csv"

with csv_path.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "step",
        "skip_instructions",
        "rl_action",
        "rl_ipc",
        "best_action",
        "best_ipc",
    ])
    for row in rows:
        writer.writerow([
            row["step"],
            row["skip_instructions"],
            "|".join(f"{k}={v}" for k, v in row["rl_action"].items()),
            row["rl_ipc"],
            "|".join(f"{k}={v}" for k, v in row["best_action"].items()),
            row["best_ipc"],
        ])

print("Comparison saved to", csv_path.resolve())
matches = sum(1 for r in rows if r["rl_action"] == r["best_action"])
print(f"{matches}/{len(rows)} windows: RL chose the optimal policy.")
