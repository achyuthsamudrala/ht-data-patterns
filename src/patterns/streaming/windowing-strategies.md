# Windowing Strategies

> **One-liner:** Tumbling, sliding, and session windows each make different assumptions about event arrival that determine memory and correctness behavior.

## Symptom

- A sliding-window aggregation's memory footprint grows far beyond what a tumbling
  window over the same data would require, for reasons not obvious from the business
  logic alone.
- Session windows for a bursty, low-traffic key stay open far longer than expected,
  each held-open session consuming state until its inactivity gap elapses.
- Switching from a tumbling to a sliding window (to get more frequent updates) changes
  the compute cost per event by more than the naive "just recompute more often" mental
  model would predict.
- A large number of tiny, rarely-updated windows (one per low-traffic key) accumulate in
  state, and cleanup of expired windows becomes a measurable operational cost of its
  own.

## Mechanism

A window groups events by time for aggregation, and the three common strategies make
different tradeoffs between memory, update frequency, and semantic fit to the
underlying question being asked.

**Tumbling windows** are fixed-size, non-overlapping intervals (every 5 minutes, say).
Each event belongs to exactly one window, which keeps per-event state cost minimal —
one window's aggregate state is touched per event. This is the cheapest strategy but
produces output only once per window boundary, which can be too coarse for use cases
needing more frequent updates.

**Sliding windows** are fixed-size but overlapping, advancing by a step smaller than
the window's total size (a 5-minute window advancing every 1 minute, for instance).
Every event now belongs to multiple overlapping windows simultaneously — for a window
size to step-size ratio of 5:1, each event contributes to five windows' worth of state
rather than one. This multiplies per-event state update cost roughly by that ratio,
which is the source of the disproportionate memory and compute growth described above:
it isn't "the same aggregation, just more often," it's "the same aggregation replicated
across every overlapping window an event now belongs to."

**Session windows** have no fixed size at all — a session groups events by activity,
closing only after a configured gap of inactivity for that key. This fits use cases
where the natural unit of analysis is "a burst of related activity" rather than a fixed
clock interval, but it means the number of concurrently open windows is a function of
how many distinct keys are simultaneously active, and a key with sparse, irregular
activity keeps its session open (consuming state) for as long as its inactivity gap
allows, even between genuinely related bursts of events.

All three strategies depend on [Watermarks & Late Data](watermarks-and-late-data.md) to
decide when a window is actually closed and safe to emit and clean up — a window
strategy choice doesn't remove the completeness/latency tradeoff watermarking encodes,
it just determines the *shape* of the state that tradeoff is applied to.

## Real-world sightings

The Dataflow Model paper (Akidau et al., VLDB 2015) formalizes tumbling, sliding, and
session windows as the standard windowing vocabulary now used across Beam, Flink, and
Spark Structured Streaming, explicitly noting session windows as "data-driven" windows
(their boundaries depend on the data itself, unlike the other two, which are purely
time-driven), a distinction the paper uses to explain why session window state
management requires different mechanics (merging adjacent windows as new events extend
a session) than the other two strategies.

The memory cost multiplier of sliding windows relative to their step-to-size ratio is a
widely discussed practical tuning consideration in Flink and Spark Structured Streaming
documentation and engineering guidance, generally framed as a direct tradeoff engineers
should explicitly reason about (how much more frequent output is actually needed)
rather than defaulting to fine-grained sliding windows for output-frequency reasons
alone.

## Mitigations

### Choosing the coarsest window strategy that meets the actual requirement

**What it is:** Default to tumbling windows unless a genuine business requirement
needs overlapping (sliding) or activity-based (session) semantics, since tumbling
windows are the cheapest in both memory and compute.

**Cost:** Requires distinguishing "we want more frequent updates because it's nice to
have" from "the use case genuinely requires overlapping window semantics" — a judgment
call that's easy to get wrong toward over-provisioning update frequency.

**How it backfires:** None specific to this mitigation itself — the risk is the
opposite direction, choosing tumbling windows for a use case that genuinely needed
sliding semantics and then working around the mismatch with awkward downstream logic.

### Bounding session window duration explicitly

**What it is:** Set a maximum session duration (in addition to the inactivity gap) so
a pathologically long-running session (a key that never truly goes inactive) doesn't
hold state open indefinitely.

**Cost:** A maximum duration cap can split a genuinely continuous, related session into
multiple emitted windows, which may or may not match the intended semantics for that
use case.

**How it backfires:** A cap set too aggressively for a legitimately long-running
activity (a long user session, an extended IoT device event) fragments what should be
one logical session into several, changing aggregation results in a way that isn't
obviously wrong until someone investigates a specific case.

### Monitoring open-window / open-session count as an operational metric

**What it is:** Track the number of concurrently open windows or sessions as a
first-class operational metric, since it's a leading indicator of both memory pressure
and potential state-cleanup issues.

**Cost:** Requires instrumenting the streaming engine's internal state to expose this,
which not all engines do by default.

**How it backfires:** None specific — the absence of this monitoring is itself the
failure mode: without it, window/session count growth is invisible until it manifests
as a memory or performance problem with no earlier warning.

## Interactions

- [Watermarks & Late Data](watermarks-and-late-data.md) — the completeness mechanism
  that determines when any window strategy considers itself closed.
- [Stateful Processing & State Stores](stateful-processing-and-state-stores.md) — window
  state (for any of the three strategies) is exactly the kind of state this pattern's
  state-store mechanics apply to.
- [Batch vs. Streaming Spectrum](../../foundations/batch-vs-streaming-spectrum.md) — the
  window-strategy choice is one concrete manifestation of the latency/throughput/
  completeness tradeoff described at the foundations level.

## References

- Akidau, T. et al. *The Dataflow Model: A Practical Approach to Balancing Correctness,
  Latency, and Cost in Massive-Scale, Unbounded, Out-of-Order Data Processing*. VLDB
  2015. Formalizes tumbling, sliding, and session window semantics.
- Apache Flink Documentation. *Windows*. Practical configuration reference for all
  three window types and their state management implications.
- Apache Beam Programming Guide. *Windowing*. Cross-engine conceptual reference for
  window strategy selection.
