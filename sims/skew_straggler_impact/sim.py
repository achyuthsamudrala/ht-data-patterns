#!/usr/bin/env python3
"""
Data skew straggler impact: task duration distribution, skewed vs. salted.

Shows how a single hot key produces one straggler task that dominates stage
wall-clock time, and how salting redistributes that key's rows across more
tasks to restore parallelism.

Usage:
    python sim.py --out ../../src/figures/skew_straggler_impact

Output:
    skew_straggler_impact.svg — task duration distribution, skewed vs. salted
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description="Skew straggler impact")
    parser.add_argument("--out", type=Path, default=Path("../../src/figures/skew_straggler_impact"))
    parser.add_argument("--num-tasks", type=int, default=40)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    style = Path(__file__).parent.parent / "style.mplstyle"
    plt.style.use(style)

    rng = np.random.default_rng(7)
    n = args.num_tasks

    # Skewed: most tasks process a normal share; one hot-key task processes
    # a disproportionate share (e.g. 40% of total rows in a single partition).
    baseline = rng.normal(loc=12, scale=1.5, size=n)
    skewed = baseline.copy()
    hot_idx = n // 2
    skewed[hot_idx] = 95  # the hot-key straggler

    # Salted: the hot key's rows are split across `salt_buckets` partitions,
    # so the extra work is spread rather than concentrated.
    salt_buckets = 8
    salted = baseline.copy()
    extra_per_bucket = (skewed[hot_idx] - baseline[hot_idx]) / salt_buckets
    salted_task_ids = rng.choice(n, size=salt_buckets, replace=False)
    for idx in salted_task_ids:
        salted[idx] += extra_per_bucket

    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharey=True)

    task_ids = np.arange(n)

    axes[0].bar(task_ids, skewed, color="#D55E00", width=0.8)
    axes[0].axhline(skewed.mean(), color="gray", linestyle="--", linewidth=1.2,
                     label=f"Mean: {skewed.mean():.1f}s")
    axes[0].annotate(
        f"Straggler task:\n{skewed[hot_idx]:.0f}s\n(~{skewed[hot_idx]/baseline.mean():.0f}x neighbors)",
        xy=(hot_idx, skewed[hot_idx]), xytext=(hot_idx - 14, skewed[hot_idx] - 15),
        fontsize=9, arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
    )
    axes[0].set_title("Skewed Key (no salting)")
    axes[0].set_xlabel("Task ID")
    axes[0].set_ylabel("Task Duration (s)")
    axes[0].legend(loc="upper right", fontsize=9)

    axes[1].bar(task_ids, salted, color="#0072B2", width=0.8)
    axes[1].axhline(salted.mean(), color="gray", linestyle="--", linewidth=1.2,
                     label=f"Mean: {salted.mean():.1f}s")
    axes[1].set_title(f"Salted Key ({salt_buckets} buckets)")
    axes[1].set_xlabel("Task ID")
    axes[1].legend(loc="upper right", fontsize=9)

    stage_time_skewed = skewed.max()
    stage_time_salted = salted.max()
    fig.suptitle(
        f"Data Skew: Stage Wall-Clock Time = Slowest Task "
        f"({stage_time_skewed:.0f}s skewed vs. {stage_time_salted:.0f}s salted)",
        fontsize=12,
    )

    fig.tight_layout(rect=[0, 0, 1, 0.94])

    out_path = args.out / "skew_straggler_impact.svg"
    fig.savefig(out_path, format="svg")
    print(f"Wrote {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
