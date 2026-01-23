import argparse
import json
import signal
from pathlib import Path

try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except AttributeError:
    pass

EPS = 1e-12


def pct_loss_vs_best(best: float, val: float) -> float:
    if abs(best) <= EPS:
        return 0.0
    return (best - val) / best * 100.0


def load_summary(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="统计各 policy 的整段 trace IPC 与最优 IPC 的百分比差距"
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path(__file__).resolve().with_name("experiment_summary.json"),
        help="experiment_summary.json 路径 (默认同目录)",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="输出为 CSV (逗号分隔，含表头)",
    )
    args = parser.parse_args()

    data = load_summary(args.summary)
    fixed = data.get("fixed_policies", {})
    if not fixed:
        raise SystemExit(f"missing or empty fixed_policies in {args.summary}")

    keys = sorted(fixed.keys())
    steps = len(next(iter(fixed.values()))["per_step_ipc"])

    best_fixed_action = max(keys, key=lambda k: fixed[k]["total_ipc"])
    best_fixed_total = float(fixed[best_fixed_action]["total_ipc"])

    oracle_total = None
    per_step = data.get("per_step_comparison", {}).get("results")
    if isinstance(per_step, list) and per_step:
        oracle_total = float(sum(float(r["best_ipc"]) for r in per_step))
    else:
        oracle_total = float(
            sum(max(float(fixed[k]["per_step_ipc"][i]) for k in keys) for i in range(steps))
        )

    rows = []
    for k in keys:
        total = float(fixed[k]["total_ipc"])
        rows.append(
            {
                "policy": k,
                "total_ipc": total,
                "avg_ipc": total / steps,
                "loss_vs_best_fixed_pct": pct_loss_vs_best(best_fixed_total, total),
                "loss_vs_oracle_pct": pct_loss_vs_best(oracle_total, total),
            }
        )

    rl = data.get("rl")
    if isinstance(rl, dict) and "total_ipc" in rl:
        total = float(rl["total_ipc"])
        rows.append(
            {
                "policy": "__RL__",
                "total_ipc": total,
                "avg_ipc": total / steps,
                "loss_vs_best_fixed_pct": pct_loss_vs_best(best_fixed_total, total),
                "loss_vs_oracle_pct": pct_loss_vs_best(oracle_total, total),
            }
        )

    rows.sort(key=lambda r: r["total_ipc"], reverse=True)

    if args.csv:
        header = [
            "policy",
            "total_ipc",
            "avg_ipc",
            "loss_vs_best_fixed_pct",
            "loss_vs_oracle_pct",
        ]
        print(",".join(header))
        for r in rows:
            print(
                f'{r["policy"]},{r["total_ipc"]:.12f},{r["avg_ipc"]:.12f},'
                f'{r["loss_vs_best_fixed_pct"]:.6f},{r["loss_vs_oracle_pct"]:.6f}'
            )
        return 0

    print(f"steps={steps}")
    print(f"best_fixed_total_ipc={best_fixed_total:.12f}  action={best_fixed_action}")
    print(f"oracle_total_ipc={oracle_total:.12f}  (per-step best)")
    print()
    print(
        f'{"policy":80s}  {"total_ipc":>10s}  {"avg_ipc":>8s}  '
        f'{"loss_vs_best_fixed":>16s}  {"loss_vs_oracle":>13s}'
    )
    for r in rows:
        print(
            f'{r["policy"]:80s}  {r["total_ipc"]:10.3f}  {r["avg_ipc"]:8.6f}  '
            f'{r["loss_vs_best_fixed_pct"]:15.3f}%  {r["loss_vs_oracle_pct"]:12.3f}%'
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

