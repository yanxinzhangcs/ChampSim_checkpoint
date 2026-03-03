#!/usr/bin/env python3
"""
Sanity-check feature/target variety by plotting per-column value distributions.

Inputs:
  - input.npy  : shape (N, D) int/float
  - output.npy : shape (N,) or (N, 1) int/float

Outputs:
  - out_dir/*.png      : one plot per feature + one for target
  - out_dir/summary.json : basic stats per column
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


def _parse_csv_list(x: str) -> list[str]:
    return [p.strip() for p in str(x).split(",") if p.strip()]


def _sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name or "col"


def _as_1d(a):
    import numpy as np

    a = np.asarray(a)
    if a.ndim == 0:
        return a.reshape((1,))
    if a.ndim == 1:
        return a
    if a.ndim == 2 and a.shape[1] == 1:
        return a.reshape((-1,))
    raise SystemExit(f"expected 1D or (N,1) array, got shape={a.shape}")


def _as_2d(a):
    import numpy as np

    a = np.asarray(a)
    if a.ndim == 1:
        return a.reshape((-1, 1))
    if a.ndim == 2:
        return a
    raise SystemExit(f"expected 1D or 2D array, got shape={a.shape}")


def _maybe_sample_rows(x, y, sample: int | None, seed: int):
    import numpy as np

    n = int(x.shape[0])
    if n == 0:
        return x, y, {"sampled": False, "n_total": 0, "n_used": 0}

    if sample is None:
        # Auto: cap plot/stats cost without hiding obvious pathologies (all-zeros, constant columns, etc.)
        sample = min(n, 1_000_000)
    if sample <= 0 or sample >= n:
        return x, y, {"sampled": False, "n_total": n, "n_used": n}

    rng = np.random.default_rng(seed)
    idx = rng.choice(n, size=int(sample), replace=False)
    idx.sort()
    return x[idx], y[idx], {"sampled": True, "n_total": n, "n_used": int(sample)}


def _compute_stats(values, max_topk: int = 20) -> dict[str, Any]:
    import numpy as np

    v = np.asarray(values)
    if v.size == 0:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "unique": 0,
            "zero_fraction": None,
            "percentiles": {},
            "top_values": [],
        }

    if np.issubdtype(v.dtype, np.bool_):
        v = v.astype(np.int64)

    # Avoid propagating NaNs in summaries.
    if np.issubdtype(v.dtype, np.floating):
        v = v[np.isfinite(v)]
        if v.size == 0:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "mean": None,
                "std": None,
                "unique": 0,
                "zero_fraction": None,
                "percentiles": {},
                "top_values": [],
            }

    count = int(v.size)
    v_min = float(np.min(v))
    v_max = float(np.max(v))
    mean = float(np.mean(v))
    std = float(np.std(v))
    zero_fraction = float(np.mean(v == 0))

    # Unique + top-k can be expensive if values are almost all unique. We still compute it,
    # but cap top-k extraction by sorting counts only when unique is not too large.
    uniq, counts = np.unique(v, return_counts=True)
    unique_count = int(uniq.size)

    top_values: list[list[float]] = []
    if unique_count > 0:
        k = min(max_topk, unique_count)
        # argpartition is O(n) and doesn't fully sort.
        top_idx = np.argpartition(counts, -k)[-k:]
        order = top_idx[np.argsort(counts[top_idx])[::-1]]
        top_values = [[float(uniq[i]), int(counts[i])] for i in order]

    # Percentiles (use sample anyway; this script is for sanity checking)
    pct_points = [0, 1, 5, 25, 50, 75, 95, 99, 100]
    pct_vals = np.percentile(v.astype(np.float64, copy=False), pct_points).tolist()
    percentiles = {str(p): float(val) for p, val in zip(pct_points, pct_vals)}

    return {
        "count": count,
        "min": v_min,
        "max": v_max,
        "mean": mean,
        "std": std,
        "unique": unique_count,
        "zero_fraction": zero_fraction,
        "percentiles": percentiles,
        "top_values": top_values,
    }


def _plot_distribution(values, name: str, out_path: Path, bins: int, log_y: bool):
    import numpy as np

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    v = np.asarray(values)
    v = v.reshape((-1,))

    fig, ax = plt.subplots(figsize=(9, 4.8), constrained_layout=True)
    if v.size == 0:
        ax.text(0.5, 0.5, "empty", ha="center", va="center")
        ax.set_axis_off()
        fig.savefig(out_path, dpi=200)
        plt.close(fig)
        return

    is_int = np.issubdtype(v.dtype, np.integer) or np.issubdtype(v.dtype, np.bool_)
    if is_int:
        v_int = v.astype(np.int64, copy=False)
        v_min = int(v_int.min())
        v_max = int(v_int.max())
        value_range = v_max - v_min
        # Treat as categorical if the range is reasonably small.
        if 0 <= value_range <= 256:
            offsets = v_int - v_min
            counts = np.bincount(offsets, minlength=value_range + 1)
            xs = np.arange(v_min, v_max + 1, dtype=np.int64)
            ax.bar(xs, counts, width=0.9, color="#4C78A8")
            ax.set_xlim(v_min - 1, v_max + 1)
            ax.set_xlabel(name)
            ax.set_ylabel("count")
            if log_y:
                ax.set_yscale("log")
            ax.set_title(f"{name} (categorical-ish, n={v.size})")
            fig.savefig(out_path, dpi=200)
            plt.close(fig)
            return

    # Numeric histogram.
    # Convert to float64 for percentile/bucket calculations; plot still represents the values.
    v_num = v.astype(np.float64, copy=False)
    if not np.all(np.isfinite(v_num)):
        v_num = v_num[np.isfinite(v_num)]
    if v_num.size == 0:
        ax.text(0.5, 0.5, "all non-finite", ha="center", va="center")
        ax.set_axis_off()
        fig.savefig(out_path, dpi=200)
        plt.close(fig)
        return

    ax.hist(v_num, bins=int(bins), color="#4C78A8", alpha=0.9)
    ax.set_xlabel(name)
    ax.set_ylabel("count")
    if log_y:
        ax.set_yscale("log")
    ax.set_title(f"{name} (hist, bins={bins}, n={v_num.size})")
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Plot per-feature distributions from input.npy/output.npy"
    )
    p.add_argument(
        "--input-npy",
        type=Path,
        default=Path("input.npy"),
        help="Path to input.npy (default: ./input.npy)",
    )
    p.add_argument(
        "--output-npy",
        type=Path,
        default=Path("output.npy"),
        help="Path to output.npy (default: ./output.npy)",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("sanity_plots"),
        help="Output directory for plots + summary.json",
    )
    p.add_argument(
        "--feature-names",
        default="pc,memory_address,opcode,source_register1,source_register2,destination_register1",
        help="Comma-separated feature names (used for labeling plots)",
    )
    p.add_argument(
        "--target-name",
        default="delta_cycles",
        help="Target name (used for labeling plots)",
    )
    p.add_argument(
        "--bins",
        type=int,
        default=100,
        help="Number of histogram bins for numeric columns",
    )
    p.add_argument(
        "--log-y",
        action="store_true",
        default=False,
        help="Use log scale for histogram y-axis",
    )
    p.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Randomly sample N rows for plotting/stats (default: auto cap at 1,000,000)",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for sampling",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    try:
        import numpy as np
    except Exception as e:  # pragma: no cover
        raise SystemExit(f"failed to import numpy: {e}") from e

    x = np.load(args.input_npy)
    y = np.load(args.output_npy)

    x2 = _as_2d(x)
    y1 = _as_1d(y)

    if x2.shape[0] != y1.shape[0]:
        raise SystemExit(
            f"row count mismatch: input.npy has {x2.shape[0]} rows, output.npy has {y1.shape[0]} rows"
        )

    x_used, y_used, sample_info = _maybe_sample_rows(
        x2, y1.reshape((-1, 1)), args.sample, args.seed
    )
    y_used = y_used.reshape((-1,))

    feature_names = _parse_csv_list(args.feature_names)
    if len(feature_names) != x_used.shape[1]:
        feature_names = [f"f{i}" for i in range(x_used.shape[1])]

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {"sample_info": sample_info, "features": {}, "target": {}}

    for i, name in enumerate(feature_names):
        col = x_used[:, i]
        stats = _compute_stats(col)
        summary["features"][name] = stats

        fname = f"feature_{i:02d}_{_sanitize_filename(name)}.png"
        _plot_distribution(
            col,
            name=name,
            out_path=out_dir / fname,
            bins=args.bins,
            log_y=args.log_y,
        )

    target_stats = _compute_stats(y_used)
    summary["target"][args.target_name] = target_stats
    _plot_distribution(
        y_used,
        name=args.target_name,
        out_path=out_dir / f"target_{_sanitize_filename(args.target_name)}.png",
        bins=args.bins,
        log_y=args.log_y,
    )

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(f"wrote plots + summary to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

