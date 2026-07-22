#!/usr/bin/env python3
"""
Watermark tradeoff: completeness vs. latency as allowed lateness increases.

Shows the fraction of data captured before a window closes (completeness)
rising with allowed lateness, against the corresponding growth in emission
latency for every window, not just the late-arriving fraction.

Usage:
    python sim.py --out ../../src/figures/watermark_lateness_completeness

Output:
    watermark_lateness_completeness.svg — completeness and latency vs. allowed lateness
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description="Watermark lateness vs. completeness")
    parser.add_argument("--out", type=Path, default=Path("../../src/figures/watermark_lateness_completeness"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    style = Path(__file__).parent.parent / "style.mplstyle"
    plt.style.use(style)

    allowed_lateness_s = np.linspace(0, 300, 300)  # seconds of allowed lateness

    # Completeness: modeled as a CDF of event arrival delay (most data arrives
    # promptly, a long tail arrives late — e.g. mobile clients buffering
    # offline). Using a log-normal-shaped CDF as a stand-in for a realistic
    # arrival-delay distribution.
    median_delay = 20.0
    spread = 1.3
    completeness = 0.5 * (1 + np.tanh((np.log(allowed_lateness_s + 1) - np.log(median_delay)) / spread))
    completeness = completeness / completeness[-1] * 0.995  # normalize, cap near-100%

    # Emission latency for every window = window close delay = allowed lateness itself.
    emission_latency_s = allowed_lateness_s

    fig, ax1 = plt.subplots()

    ax1.plot(allowed_lateness_s, completeness * 100, color="#0072B2", linewidth=2.2,
             label="Completeness (% of data captured)")
    ax1.set_xlabel("Allowed Lateness (seconds)")
    ax1.set_ylabel("Completeness (%)", color="#0072B2")
    ax1.tick_params(axis="y", labelcolor="#0072B2")
    ax1.set_ylim(0, 105)

    ax2 = ax1.twinx()
    ax2.plot(allowed_lateness_s, emission_latency_s, color="#D55E00", linewidth=2.2,
             linestyle="--", label="Emission latency (every window)")
    ax2.set_ylabel("Emission Latency Added (seconds)", color="#D55E00")
    ax2.tick_params(axis="y", labelcolor="#D55E00")
    ax2.grid(False)

    # Annotate a reasonable operating point.
    op_idx = np.searchsorted(allowed_lateness_s, 60)
    ax1.axvline(60, color="gray", linestyle=":", linewidth=1.0)
    ax1.annotate(
        f"At 60s allowed lateness:\n{completeness[op_idx]*100:.1f}% complete,\n"
        f"every window delayed 60s",
        xy=(60, completeness[op_idx] * 100), xytext=(90, 40),
        fontsize=9, arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
    )

    ax1.set_title("Watermark Tradeoff: Completeness Gained vs. Latency Paid by Every Window")
    fig.tight_layout()

    out_path = args.out / "watermark_lateness_completeness.svg"
    fig.savefig(out_path, format="svg")
    print(f"Wrote {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
