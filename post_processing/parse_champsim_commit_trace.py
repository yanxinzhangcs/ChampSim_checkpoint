#!/usr/bin/env python3
"""
Parse ChampSim commit-trace CSV (produced by --commit-trace) into input.npy/output.npy.

Default columns match the NeuroScalar-style feature set:
  inputs: pc, memory_address, opcode, source_register1, source_register2, destination_register1
  target: delta_cycles

The CSV values are written as decimal integers by ChampSim, but this parser also accepts
hex strings like "0x400123" (via int(x, 0)).
"""

from __future__ import annotations

import argparse
import csv
import glob
from pathlib import Path
from typing import Iterable


def _parse_int(x: str) -> int:
    x = x.strip()
    if x == "":
        return 0
    return int(x, 0)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Convert ChampSim --commit-trace CSV into input.npy/output.npy"
    )
    p.add_argument(
        "trace_csv",
        type=str,
        help="CSV path or glob pattern from ChampSim --commit-trace (e.g., commit_trace*.csv)",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: alongside trace_csv)",
    )
    p.add_argument(
        "--inputs",
        default="pc,memory_address,opcode,source_register1,source_register2,destination_register1",
        help="Comma-separated input column names",
    )
    p.add_argument(
        "--target",
        default="delta_cycles",
        help="Target column name",
    )
    p.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional cap on number of rows to parse (for quick experiments)",
    )
    return p.parse_args()


def _iter_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise SystemExit(f"missing CSV header in {path}")
        yield from reader


def main() -> int:
    args = _parse_args()
    matched = [Path(p) for p in sorted(glob.glob(args.trace_csv))]
    if not matched:
        raise SystemExit(f"no files matched: {args.trace_csv}")

    out_dir: Path = args.out_dir if args.out_dir is not None else matched[0].parent
    out_dir.mkdir(parents=True, exist_ok=True)

    input_cols = [c.strip() for c in str(args.inputs).split(",") if c.strip()]
    if not input_cols:
        raise SystemExit("--inputs is empty")

    max_rows = args.max_rows

    # Import numpy lazily so a quick `--help` doesn't need it installed.
    try:
        import numpy as np
    except Exception as e:  # pragma: no cover
        raise SystemExit(f"failed to import numpy: {e}") from e

    xs: list[list[int]] = []
    ys: list[int] = []

    row_count = 0
    for trace_csv in matched:
        for row in _iter_rows(trace_csv):
            if max_rows is not None and row_count >= max_rows:
                break
            try:
                xs.append([_parse_int(row[c]) for c in input_cols])
                ys.append(_parse_int(row[str(args.target)]))
            except KeyError as e:
                raise SystemExit(
                    f"missing column {e} in {trace_csv}; available={sorted(row.keys())}"
                ) from e
            row_count += 1
        if max_rows is not None and row_count >= max_rows:
            break

    x = np.asarray(xs, dtype=np.int64).reshape((-1, len(input_cols)))
    y = np.asarray(ys, dtype=np.int64).reshape((-1, 1))

    np.save(out_dir / "input.npy", x)
    np.save(out_dir / "output.npy", y)

    print(
        f"parsed {row_count} rows from {len(matched)} file(s), wrote {out_dir / 'input.npy'} shape={tuple(x.shape)} dtype={x.dtype}"
    )
    print(
        f"wrote {out_dir / 'output.npy'} shape={tuple(y.shape)} dtype={y.dtype}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
