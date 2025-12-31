import json
from pathlib import Path
import matplotlib.pyplot as plt

summary_path = Path("/home/ubuntu/yanxin/ChampSim_checkpoint/rl_results/perlbench_combo/experiment_summary.json")
data = json.load(summary_path.open())

fixed = data["fixed_policies"]
steps = len(next(iter(fixed.values()))["per_step_ipc"])

def short_label(key: str) -> str:
    parts = key.split("_")
    out = []
    for p in parts:
        if p.startswith("l1d_prefetcher-"):
            out.append("D:" + p.split("-", 2)[-1])
        elif p.startswith("l1i_prefetcher-"):
            out.append("I:" + p.split("-", 2)[-1])
        elif p.startswith("l2c_replacement-"):
            out.append("L2:" + p.split("-", 2)[-1])
    return " ".join(out)

plt.figure(figsize=(12, 6))
for key, val in fixed.items():
    y = val["per_step_ipc"]
    plt.plot(range(1, steps + 1), y, label=short_label(key), linewidth=1.5)

plt.xlabel("Step")
plt.ylabel("IPC")
plt.title("IPC per Step (8 Policies)")
plt.legend(fontsize=8, ncol=2)
plt.tight_layout()
plt.savefig("/home/ubuntu/yanxin/ChampSim_checkpoint/rl_results/perlbench_combo/ipc_per_step_8lines.png", dpi=160)
plt.show()
