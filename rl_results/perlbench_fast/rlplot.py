import json
import matplotlib.pyplot as plt
from pathlib import Path

root = Path("/home/ubuntu/yanxin/ChampSim_checkpoint/rl_results/perlbench_fast")
summary = json.loads((root / "experiment_summary.json").read_text())
episode = summary["rl"]["episode"]

steps = [row["step"] for row in episode]
ipc = [row["ipc"] for row in episode]

plt.figure(figsize=(8,4))
plt.plot(steps, ipc, marker="o", linewidth=1)
plt.xlabel("Window index")
plt.ylabel("IPC (reward)")
plt.title("RL reward per sub-trace window")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(root / "rl_reward_curve.png", dpi=150)
print("Plot saved as", (root / "rl_reward_curve.png").resolve())
