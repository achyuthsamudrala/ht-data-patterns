#!/usr/bin/env python3
"""
Query queue wait time vs. admission control threshold.

Shows how a stricter (lower) admission threshold reduces catastrophic
cluster-wide slowdowns under a demand burst, at the cost of queuing more
queries during normal load.

Usage:
    python sim.py --out ../../src/figures/query_admission_wait

Output:
    query_admission_wait.svg — wait time vs. concurrent query demand, by threshold
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


def wait_time(demand, capacity, admission_threshold):
    """
    Approximate M/M/1-style queue wait time, but with admission control that
    caps concurrently admitted queries at `admission_threshold` x capacity.
    Beyond that, excess demand queues rather than degrading service for all.
    """
    effective_demand = np.minimum(demand, admission_threshold * capacity)
    rho = np.clip(effective_demand / capacity, 0, 0.98)
    base_wait = rho / (1 - rho)

    # Demand beyond the admission threshold queues linearly (bounded, visible)
    # rather than degrading every running query's throughput.
    excess = np.clip(demand - admission_threshold * capacity, 0, None)
    queue_wait = excess / capacity

    return base_wait + queue_wait


def main():
    parser = argparse.ArgumentParser(description="Query admission control wait time")
    parser.add_argument("--out", type=Path, default=Path("../../src/figures/query_admission_wait"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    style = Path(__file__).parent.parent / "style.mplstyle"
    plt.style.use(style)

    capacity = 100.0
    demand = np.linspace(1, 250, 400)

    no_admission = wait_time(demand, capacity, admission_threshold=999)  # effectively no cap
    loose_threshold = wait_time(demand, capacity, admission_threshold=1.5)
    strict_threshold = wait_time(demand, capacity, admission_threshold=1.05)

    fig, ax = plt.subplots()

    ax.plot(demand, no_admission, color="#D55E00", linewidth=2.2,
            label="No admission control")
    ax.plot(demand, loose_threshold, color="#E69F00", linewidth=2.2,
            label="Loose threshold (1.5x capacity)")
    ax.plot(demand, strict_threshold, color="#0072B2", linewidth=2.2,
            label="Strict threshold (1.05x capacity)")

    ax.axvline(capacity, color="gray", linestyle=":", linewidth=1.0, alpha=0.6)
    ax.annotate("Nominal capacity", xy=(capacity, 0), xytext=(capacity + 8, ax.get_ylim()[1]*0.02 if False else 1),
                fontsize=9, color="gray")

    ax.annotate(
        "No admission control: wait time\nexplodes non-linearly near saturation",
        xy=(140, no_admission[np.searchsorted(demand, 140)]),
        xytext=(150, 15),
        fontsize=9, arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
    )
    ax.annotate(
        "Strict admission: excess demand queues\npredictably instead of degrading everyone",
        xy=(200, strict_threshold[np.searchsorted(demand, 200)]),
        xytext=(40, 8),
        fontsize=9, arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
    )

    ax.set_xlabel("Concurrent Query Demand (relative)")
    ax.set_ylabel("Wait Time (relative units)")
    ax.set_title("Admission Control Threshold: Bounded Queuing vs. Cluster-Wide Collapse")
    ax.set_ylim(0, 25)
    ax.legend(loc="upper left", fontsize=9)

    out_path = args.out / "query_admission_wait.svg"
    fig.savefig(out_path, format="svg")
    print(f"Wrote {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
