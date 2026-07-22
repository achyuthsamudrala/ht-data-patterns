#!/usr/bin/env python3
"""
B-tree vs. LSM-tree point-lookup latency under increasing write load.

Shows how B-tree lookup latency stays flat but degrades under write-induced
page fragmentation, while LSM-tree lookup latency depends on how many
sstable levels a read must check, which grows between compactions.

Usage:
    python sim.py --out ../../src/figures/index_lookup_latency

Output:
    index_lookup_latency.svg — point-lookup latency vs. write load
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description="Index lookup latency vs. write load")
    parser.add_argument("--out", type=Path, default=Path("../../src/figures/index_lookup_latency"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    style = Path(__file__).parent.parent / "style.mplstyle"
    plt.style.use(style)

    write_rate = np.linspace(0, 100, 400)  # relative write ops/sec

    # B-tree: lookup latency mostly flat, but rises as random-write page
    # fragmentation increases under sustained high write load.
    btree_latency = 0.08 + 0.0009 * write_rate**1.5

    # LSM-tree: lookup latency depends on number of unmerged sstables a read
    # must check; more write load produces more memtable flushes between
    # compactions, so more sstables accumulate before the next compaction pass.
    lsm_latency_pre_compaction = 0.05 + 0.006 * write_rate
    lsm_latency_post_compaction = np.full_like(write_rate, 0.06)

    fig, ax = plt.subplots()

    ax.plot(write_rate, btree_latency, color="#0072B2", linewidth=2.2,
            label="B-tree (in-place updates)")
    ax.plot(write_rate, lsm_latency_pre_compaction, color="#D55E00", linewidth=2.2,
            label="LSM-tree, just before compaction")
    ax.plot(write_rate, lsm_latency_post_compaction, color="#D55E00", linewidth=2.0,
            linestyle="--", label="LSM-tree, just after compaction")

    ax.annotate(
        "LSM read latency varies with\nsstable count between compactions",
        xy=(70, lsm_latency_pre_compaction[np.searchsorted(write_rate, 70)]),
        xytext=(20, 0.75),
        fontsize=9, arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
    )
    ax.annotate(
        "B-tree stays low-variance,\ndegrades gradually under\nheavy random writes",
        xy=(90, btree_latency[np.searchsorted(write_rate, 90)]),
        xytext=(45, 0.15),
        fontsize=9, arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
    )

    ax.set_xlabel("Write Load (relative ops/sec)")
    ax.set_ylabel("Point-Lookup Latency (ms, relative)")
    ax.set_title("Point-Lookup Latency vs. Write Load: B-Tree vs. LSM-Tree")
    ax.legend(loc="upper left", fontsize=9)

    out_path = args.out / "index_lookup_latency.svg"
    fig.savefig(out_path, format="svg")
    print(f"Wrote {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
