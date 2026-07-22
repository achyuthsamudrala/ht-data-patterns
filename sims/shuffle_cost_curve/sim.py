#!/usr/bin/env python3
"""
Shuffle cost model: where time goes as partition size grows.

Shows how serialization, network transfer, and disk spill contribute to total
shuffle time per partition as partition size increases past the point where it
fits in the reduce-side memory buffer.

Usage:
    python sim.py --out ../../src/figures/shuffle_cost_curve

Output:
    shuffle_cost_curve.svg — stacked cost breakdown vs. partition size
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description="Shuffle cost model")
    parser.add_argument("--out", type=Path, default=Path("../../src/figures/shuffle_cost_curve"))
    parser.add_argument("--memory-buffer-mb", type=float, default=200.0,
                        help="Reduce-side memory buffer before spill starts (MB)")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    style = Path(__file__).parent.parent / "style.mplstyle"
    plt.style.use(style)

    partition_mb = np.linspace(1, 800, 400)
    buf = args.memory_buffer_mb

    # Serialization + deserialization: linear in data size, CPU-bound.
    ser_deser_ms = partition_mb * 0.15

    # Network transfer: linear in data size, roughly constant per-MB cost.
    network_ms = partition_mb * 0.25

    # Disk spill: zero until partition exceeds the memory buffer, then grows
    # steeply (sort + merge pass over the excess, plus the write and re-read).
    excess = np.clip(partition_mb - buf, 0, None)
    spill_ms = excess * 1.8

    total_ms = ser_deser_ms + network_ms + spill_ms

    fig, ax = plt.subplots()

    ax.stackplot(
        partition_mb,
        ser_deser_ms, network_ms, spill_ms,
        labels=["Serialization + deserialization", "Network transfer", "Disk spill"],
        colors=["#0072B2", "#56B4E9", "#D55E00"],
        alpha=0.85,
    )

    ax.axvline(buf, color="gray", linestyle=":", linewidth=1.2)
    ax.annotate(
        f"Memory buffer\n({buf:.0f} MB/partition)",
        xy=(buf, 0), xytext=(buf + 25, total_ms.max() * 0.55),
        fontsize=9, color="gray",
        arrowprops=dict(arrowstyle="->", color="gray", lw=0.8),
    )

    below_idx = np.searchsorted(partition_mb, buf)
    above_idx = min(len(partition_mb) - 1, below_idx + 150)
    ax.annotate(
        "Below buffer: cost scales\nlinearly with data volume",
        xy=(partition_mb[below_idx // 2], total_ms[below_idx // 2]),
        xytext=(60, total_ms.max() * 0.15),
        fontsize=9,
        arrowprops=dict(arrowstyle="->", color="black", lw=0.7),
    )
    ax.annotate(
        "Past buffer: spill dominates,\nslope steepens sharply",
        xy=(partition_mb[above_idx], total_ms[above_idx]),
        xytext=(buf + 120, total_ms.max() * 0.85),
        fontsize=9,
        arrowprops=dict(arrowstyle="->", color="black", lw=0.7),
    )

    ax.set_xlabel("Partition Size (MB)")
    ax.set_ylabel("Shuffle Time per Partition (ms, relative)")
    ax.set_title("Shuffle Cost Model: Where Time Goes as Partition Size Grows")
    ax.set_xlim(0, 800)
    ax.set_ylim(0, total_ms.max() * 1.05)
    ax.legend(loc="upper left")

    out_path = args.out / "shuffle_cost_curve.svg"
    fig.savefig(out_path, format="svg")
    print(f"Wrote {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()


