#!/usr/bin/env python3
"""
Execution memory pressure vs. spill time cost, under storage-memory borrowing.

Shows how cached (storage-memory) data reduces the effective execution memory
budget available to a shuffle/aggregation operator, and how task time responds
once that reduced budget is exceeded and spilling begins.

Usage:
    python sim.py --out ../../src/figures/spill_memory_curve

Output:
    spill_memory_curve.svg — task time vs. data size, at two storage-memory levels
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


def task_time_ms(data_mb, budget_mb, base_rate=0.2, spill_rate=1.6):
    """Task time: linear in-memory cost up to budget, steep spill cost past it."""
    in_memory = np.minimum(data_mb, budget_mb) * base_rate
    excess = np.clip(data_mb - budget_mb, 0, None)
    spill = excess * spill_rate
    return in_memory + spill


def main():
    parser = argparse.ArgumentParser(description="Spill vs. memory pressure")
    parser.add_argument("--out", type=Path, default=Path("../../src/figures/spill_memory_curve"))
    parser.add_argument("--total-memory-mb", type=float, default=400.0)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    style = Path(__file__).parent.parent / "style.mplstyle"
    plt.style.use(style)

    total = args.total_memory_mb
    data_mb = np.linspace(1, 700, 400)

    # Two scenarios: light caching (storage borrows little) vs heavy caching
    # (storage holds a large chunk of the unified memory pool, shrinking the
    # effective budget available to execution).
    budget_light_cache = total * 0.9   # storage using ~10%
    budget_heavy_cache = total * 0.4   # storage using ~60%

    time_light = task_time_ms(data_mb, budget_light_cache)
    time_heavy = task_time_ms(data_mb, budget_heavy_cache)

    fig, ax = plt.subplots()

    ax.plot(data_mb, time_light, color="#0072B2", linewidth=2.2,
             label=f"Light caching (execution budget: {budget_light_cache:.0f} MB)")
    ax.plot(data_mb, time_heavy, color="#D55E00", linewidth=2.2,
             label=f"Heavy caching (execution budget: {budget_heavy_cache:.0f} MB)")

    ax.axvline(budget_light_cache, color="#0072B2", linestyle=":", linewidth=1.0, alpha=0.7)
    ax.axvline(budget_heavy_cache, color="#D55E00", linestyle=":", linewidth=1.0, alpha=0.7)

    ax.annotate(
        "Same task, same data volume:\nheavy caching leaves less execution\nmemory, so spill starts sooner",
        xy=(budget_heavy_cache, time_heavy[np.searchsorted(data_mb, budget_heavy_cache)]),
        xytext=(budget_heavy_cache + 60, task_time_ms(np.array([700]), budget_heavy_cache)[0] * 0.55),
        fontsize=9,
        arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
    )

    ax.set_xlabel("Partition Data Size (MB)")
    ax.set_ylabel("Task Time (ms, relative)")
    ax.set_title("Effective Execution Memory Sets Where Spill Begins")
    ax.set_xlim(0, 700)
    ax.legend(loc="upper left")

    out_path = args.out / "spill_memory_curve.svg"
    fig.savefig(out_path, format="svg")
    print(f"Wrote {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
