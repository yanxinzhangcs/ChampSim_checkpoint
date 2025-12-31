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


for i in range(steps):
    vals = {k: fixed[k]["per_step_ipc"][i] for k in keys}
    best_ipc = max(vals.values())
    winners = {k for k, v in vals.items() if abs(v - best_ipc) <= EPS}

    losers = [(k, pct_loss_vs_best(best_ipc, v)) for k, v in vals.items() if k not in winners]
    losers.sort(key=lambda kv: kv[1], reverse=True)

    if not losers:
        print(f"step {i+1:03d}  pct_loss_vs_best=none")
        continue

    print(
        f"step {i+1:03d}  pct_loss_vs_best="
        + ",".join(f"{k}:{loss:.3f}%" for k, loss in losers)
    )
