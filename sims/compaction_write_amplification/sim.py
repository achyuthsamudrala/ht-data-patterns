#!/usr/bin/env python3
"""
Compaction: write amplification vs. read amplification tradeoff.

Shows how size-tiered and leveled compaction strategies trade write
amplification against read amplification (number of files/sstables
potentially touched per read) as the number of LSM levels increases.

Usage:
    python sim.py --out ../../src/figures/compaction_write_amplification

Output:
    compaction_write_amplification.svg — write/read amplification vs. levels
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description="Compaction amplification tradeoff")
    parser.add_argument("--out", type=Path, default=Path("../../src/figures/compaction_write_amplification"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    style = Path(__file__).parent.parent / "style.mplstyle"
    plt.style.use(style)

    levels = np.arange(1, 8)

    # Leveled compaction: write amplification grows roughly linearly with
    # level count (each level re-merges data down), but read amplification
    # stays low and roughly flat (bounded sstables per level to check).
    leveled_write_amp = 2 + levels * 3.2
    leveled_read_amp = np.full_like(levels, 1.5, dtype=float) + levels * 0.05

    # Size-tiered compaction: write amplification stays low (data merged
    # less often), but read amplification grows with level count (more
    # overlapping sstables may need to be checked per read).
    tiered_write_amp = np.full_like(levels, 3.0, dtype=float) + levels * 0.3
    tiered_read_amp = 1.5 + levels * 1.4

    fig, axes = plt.subplots(1, 2, figsize=(11, 5))

    axes[0].plot(levels, leveled_write_amp, color="#0072B2", marker="o", label="Leveled compaction")
    axes[0].plot(levels, tiered_write_amp, color="#D55E00", marker="o", label="Size-tiered compaction")
    axes[0].set_xlabel("Number of LSM Levels")
    axes[0].set_ylabel("Write Amplification (x)")
    axes[0].set_title("Write Amplification")
    axes[0].legend(fontsize=9)

    axes[1].plot(levels, leveled_read_amp, color="#0072B2", marker="o", label="Leveled compaction")
    axes[1].plot(levels, tiered_read_amp, color="#D55E00", marker="o", label="Size-tiered compaction")
    axes[1].set_xlabel("Number of LSM Levels")
    axes[1].set_ylabel("Read Amplification (sstables checked)")
    axes[1].set_title("Read Amplification")
    axes[1].legend(fontsize=9)

    fig.suptitle("Compaction Strategy Tradeoff: Write vs. Read Amplification", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.94])

    out_path = args.out / "compaction_write_amplification.svg"
    fig.savefig(out_path, format="svg")
    print(f"Wrote {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
