import json
import signal
from pathlib import Path

try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except AttributeError:
    pass

summary_path = Path(__file__).resolve().with_name("experiment_summary.json")
data = json.load(summary_path.open())

fixed = data["fixed_policies"]
keys = sorted(fixed.keys())
steps = len(next(iter(fixed.values()))["per_step_ipc"])

EPS = 1e-12  # 判定并列的容差

def pct_loss_vs_best(best: float, val: float) -> float:
    if abs(best) <= EPS:
        return 0.0
    return (best - val) / best * 100.0

best_step_counts = {k: 0 for k in keys}
loss_sums = {k: 0.0 for k in keys}
loss_max = {k: 0.0 for k in keys}

for i in range(steps):
    vals = {k: fixed[k]["per_step_ipc"][i] for k in keys}
    max_ipc = max(vals.values())
    winners = [k for k, v in vals.items() if abs(v - max_ipc) <= EPS]
    print(f"step {i+1:03d}  best_ipc={max_ipc:.6f}  configs={','.join(winners)}")

    losses = {k: pct_loss_vs_best(max_ipc, v) for k, v in vals.items()}
    for k in winners:
        best_step_counts[k] += 1
    for k, loss in losses.items():
        loss_sums[k] += loss
        loss_max[k] = max(loss_max[k], loss)

    losers = [(k, losses[k]) for k in keys if k not in winners]
    losers.sort(key=lambda kv: kv[1], reverse=True)
    if losers:
        print(
            "          pct_loss_vs_best="
            + ",".join(f"{k}:{loss:.3f}%" for k, loss in losers)
        )

print("\nSummary vs per-step best:")
for k in sorted(keys, key=lambda k: (loss_sums[k] / steps, k)):
    avg_loss = loss_sums[k] / steps
    print(
        f"{k}  best_steps={best_step_counts[k]:3d}/{steps}  "
        f"avg_loss={avg_loss:.3f}%  max_loss={loss_max[k]:.3f}%"
    )
