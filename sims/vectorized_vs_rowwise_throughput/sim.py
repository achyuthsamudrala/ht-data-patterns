#!/usr/bin/env python3
"""
Vectorized vs. row-at-a-time execution throughput.

Shows rows/sec processed as a function of batch size, contrasting fixed
per-row dispatch overhead (row-at-a-time) against overhead amortized across
a batch (vectorized), including the effect of a UDF forcing fallback for a
fraction of rows.

Usage:
    python sim.py --out ../../src/figures/vectorized_vs_rowwise_throughput

Output:
    vectorized_vs_rowwise_throughput.svg — throughput vs. batch size
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description="Vectorized vs. row-wise throughput")
    parser.add_argument("--out", type=Path, default=Path("../../src/figures/vectorized_vs_rowwise_throughput"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    style = Path(__file__).parent.parent / "style.mplstyle"
    plt.style.use(style)

    batch_sizes = np.array([1, 4, 16, 64, 256, 1024, 4096, 16384])

    # Row-at-a-time: fixed per-row dispatch cost, independent of batch size —
    # throughput is flat regardless of batching.
    per_row_dispatch_ns = 150
    rowwise_throughput = 1e9 / per_row_dispatch_ns * np.ones_like(batch_sizes, dtype=float)

    # Vectorized: fixed per-batch overhead amortized across batch size, plus a
    # small per-row cost once in the vectorized loop — throughput rises with
    # batch size and plateaus once per-batch overhead is fully amortized.
    per_batch_overhead_ns = 2000
    per_row_vector_ns = 8
    time_per_batch = per_batch_overhead_ns + per_row_vector_ns * batch_sizes
    vectorized_throughput = batch_sizes / (time_per_batch / 1e9)

    # A UDF present on ~15% of rows forces those rows through the row-wise
    # fallback path even in an otherwise-vectorized pipeline.
    udf_fraction = 0.15
    mixed_throughput = 1.0 / (
        udf_fraction / rowwise_throughput + (1 - udf_fraction) / vectorized_throughput
    )

    fig, ax = plt.subplots()

    ax.plot(batch_sizes, rowwise_throughput, color="#D55E00", marker="o",
            label="Row-at-a-time (fixed per-row dispatch)")
    ax.plot(batch_sizes, vectorized_throughput, color="#0072B2", marker="o",
            label="Fully vectorized")
    ax.plot(batch_sizes, mixed_throughput, color="#009E73", marker="o", linestyle="--",
            label=f"Vectorized + UDF on {udf_fraction:.0%} of rows")

    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("Batch Size (rows)")
    ax.set_ylabel("Throughput (rows/sec, log scale)")
    ax.set_title("Vectorized vs. Row-at-a-Time Execution Throughput")
    ax.legend(loc="lower right", fontsize=9)

    out_path = args.out / "vectorized_vs_rowwise_throughput.svg"
    fig.savefig(out_path, format="svg")
    print(f"Wrote {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
