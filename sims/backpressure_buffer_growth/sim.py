#!/usr/bin/env python3
"""
Backpressure buffer growth: bounded/visible vs. unbounded/invisible.

Shows buffer occupancy over time when a producer briefly outpaces a consumer,
contrasting a durable, bounded queue (lag rises and recovers, visibly) with
an unbounded in-memory buffer (grows without limit until a crash).

Usage:
    python sim.py --out ../../src/figures/backpressure_buffer_growth

Output:
    backpressure_buffer_growth.svg — buffer size over time, two scenarios
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description="Backpressure buffer growth")
    parser.add_argument("--out", type=Path, default=Path("../../src/figures/backpressure_buffer_growth"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    style = Path(__file__).parent.parent / "style.mplstyle"
    plt.style.use(style)

    t = np.linspace(0, 60, 600)  # minutes

    # Producer rate: baseline, with a load spike between t=15 and t=35.
    produce_rate = np.where((t >= 15) & (t <= 35), 180.0, 100.0)
    # Consumer sustains 100/s baseline; can't keep up during the spike.
    consume_rate = np.full_like(t, 100.0)

    dt = t[1] - t[0]
    net_rate = produce_rate - consume_rate

    # Bounded scenario: consumer capacity effectively caps growth via
    # backpressure once buffer crosses a threshold (producer throttled).
    bounded = np.zeros_like(t)
    unbounded = np.zeros_like(t)
    threshold = 800.0
    max_memory = 3000.0

    for i in range(1, len(t)):
        # Unbounded: no limit, grows purely from net rate, never recovers
        # capacity signal until spike ends.
        unbounded[i] = max(0.0, unbounded[i - 1] + net_rate[i] * dt * 10)

        # Bounded: once buffer crosses threshold, effective produce rate is
        # throttled to match consume rate (backpressure kicks in).
        effective_net = net_rate[i]
        if bounded[i - 1] >= threshold and effective_net > 0:
            effective_net = 0.0
        bounded[i] = max(0.0, bounded[i - 1] + effective_net * dt * 10)

    fig, ax = plt.subplots()

    ax.plot(t, bounded, color="#0072B2", linewidth=2.2,
            label="Durable, bounded queue (backpressure applied)")
    ax.plot(t, unbounded, color="#D55E00", linewidth=2.2,
            label="Unbounded in-memory buffer")

    ax.axhline(max_memory, color="#D55E00", linestyle="--", linewidth=1.2, alpha=0.7)
    ax.annotate("Available memory\n(OOM at this line)",
                xy=(58, max_memory), xytext=(38, max_memory * 1.03),
                fontsize=9, color="#D55E00")

    ax.axvspan(15, 35, color="gray", alpha=0.12)
    ax.annotate("Load spike\n(producer > consumer)", xy=(25, ax.get_ylim()[1] * 0.05 if False else bounded.max()*0.02),
                xytext=(16, unbounded.max() * 0.15), fontsize=9, color="gray")

    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Buffer Occupancy (events, relative)")
    ax.set_title("Backpressure: Bounded/Visible vs. Unbounded/Invisible Buffer Growth")
    ax.set_ylim(0, max_memory * 1.15)
    ax.legend(loc="upper left", fontsize=9)

    out_path = args.out / "backpressure_buffer_growth.svg"
    fig.savefig(out_path, format="svg")
    print(f"Wrote {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
