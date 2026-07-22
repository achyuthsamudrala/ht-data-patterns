# Checkpointing & Fault Tolerance

> **One-liner:** Checkpoint frequency sets the replay window after a failure — too infrequent and recovery is slow, too frequent and it competes with throughput.

## Symptom

- After a failure, a streaming job takes far longer to recover than the outage itself
  lasted, traceable to replaying a large window of data since the last checkpoint.
- Steady-state throughput is measurably lower than expected, and profiling attributes a
  meaningful fraction of processing time to checkpoint I/O rather than to actual event
  processing.
- Checkpoint duration itself grows over time as state size grows, eventually
  approaching or exceeding the interval between checkpoints.
- A checkpoint interval tuned for one workload's state size becomes inadequate (too slow
  to complete, or too infrequent for acceptable recovery time) after the workload's
  state grows.

## Mechanism

Checkpointing periodically records enough information — processed offsets, operator
state, in-flight computation position — to allow a streaming pipeline to resume from a
consistent point after a failure, rather than either losing data or having to reprocess
from the very beginning of the stream. The checkpoint interval directly sets the
**replay window**: the amount of data that must be reprocessed after a failure is
bounded by however much arrived between the last successful checkpoint and the
failure.

This creates a direct tension. A longer checkpoint interval means less frequent
checkpoint overhead during normal operation (checkpointing costs I/O and, depending on
mechanism, can briefly pause or slow processing), but a larger replay window and
therefore slower recovery after any failure. A shorter interval bounds recovery time
more tightly but pays checkpoint overhead more often, competing directly with the
pipeline's steady-state throughput for the same I/O and CPU resources.

Distributed checkpointing (as opposed to a single-node snapshot) has an additional
mechanical requirement: the checkpoint must capture a *consistent* global state across
all of a pipeline's parallel operators simultaneously, even though those operators are
processing independently and asynchronously. The Chandy-Lamport-derived barrier-based
checkpointing used by systems like Flink solves this by injecting a checkpoint barrier
into the data stream itself — the barrier flows through the pipeline alongside regular
data, and each operator checkpoints its own state exactly when the barrier passes
through it, guaranteeing the resulting set of per-operator checkpoints together
represents one consistent global snapshot, without requiring the entire pipeline to
pause simultaneously.

State size directly compounds this tradeoff (see
[Stateful Processing & State Stores](stateful-processing-and-state-stores.md)):
checkpoint duration scales with how much state has to be captured, and if state grows
large enough that a full checkpoint takes longer than the configured interval, the
pipeline can never actually complete one checkpoint before the next is due — a genuine
operational failure mode, not just a performance degradation. Incremental checkpointing
(capturing only state that changed since the last checkpoint) directly addresses this by
decoupling checkpoint cost from total state size, tying it instead to the rate of
state change.

## Real-world sightings

Flink's checkpointing mechanism, described in Carbone et al.'s "Lightweight
Asynchronous Snapshots for Distributed Dataflows," implements exactly the
barrier-based, Chandy-Lamport-derived approach described above, explicitly designed to
take consistent snapshots of a running distributed dataflow without requiring a global
pause — the paper frames this as a direct requirement for making checkpointing
practical at low overhead for continuously running, low-latency stream processing (see
[Micro-batch vs. Continuous Processing](microbatch-vs-continuous.md) for why a
pause-based approach would be unacceptable for that processing model).

The relationship between state size, checkpoint duration, and the resulting risk of
checkpoints "falling behind" their configured interval is a widely discussed
operational topic in Flink's own tuning documentation and production engineering posts
from companies running Flink at scale, generally recommending incremental
checkpointing and RocksDB-backed state specifically to keep checkpoint duration
decoupled from total accumulated state size.

## Mitigations

### Tuning checkpoint interval against measured recovery time requirements

**What it is:** Set checkpoint interval based on an explicit recovery-time objective
(how much replay is acceptable after a failure) rather than an arbitrary or default
value.

**Cost:** Requires knowing and periodically re-validating the acceptable recovery-time
objective, which can shift as the pipeline's downstream consumers' tolerance for
staleness changes.

**How it backfires:** An interval tuned for a recovery objective at one state size
becomes miscalibrated as state grows, since checkpoint duration itself grows with state
— the same interval that was safely shorter than checkpoint duration can, over time,
approach or exceed it.

### Incremental checkpointing

**What it is:** Checkpoint only state that changed since the last checkpoint, keeping
checkpoint cost proportional to the rate of state change rather than total state size.
See [Stateful Processing & State Stores](stateful-processing-and-state-stores.md).

**Cost:** Recovery from an incremental checkpoint chain requires replaying the chain of
increments back to a full baseline, which can be slower than a single full-snapshot
restore if the chain has grown very long.

**How it backfires:** Without periodic full checkpoints interspersed in the incremental
chain, the chain can grow long enough that recovery time creeps back up even though
each individual checkpoint remained cheap — the tradeoff is deferred, not eliminated.

### Monitoring checkpoint duration as a leading indicator

**What it is:** Track checkpoint duration over time as an explicit metric, treating a
trend toward the configured interval (not just an outright checkpoint failure) as an
actionable warning.

**Cost:** Requires instrumentation and alerting specifically on this trend, which is
easy to omit if checkpointing is treated as a background concern rather than a
first-class operational metric.

**How it backfires:** None specific — the absence of this monitoring is the failure
mode itself: without it, checkpoint duration approaching the interval is discovered
only when checkpoints actually start failing to complete in time.

## Interactions

- [Stateful Processing & State Stores](stateful-processing-and-state-stores.md) — state
  size is the direct driver of checkpoint cost and duration.
- [Micro-batch vs. Continuous Processing](microbatch-vs-continuous.md) — the two
  processing models require structurally different checkpointing mechanisms (batch-
  boundary-aligned vs. barrier-based distributed snapshots).
- [Backpressure in Streaming](backpressure-in-streaming.md) — a pipeline under
  sustained backpressure has a growing amount of unprocessed data at any point in time,
  directly increasing the effective replay window after a failure.

## References

- Carbone, P. et al. *Lightweight Asynchronous Snapshots for Distributed Dataflows*.
  2015. Describes Flink's barrier-based checkpointing mechanism.
- Chandy, K. M. and Lamport, L. *Distributed Snapshots: Determining Global States of
  Distributed Systems*. ACM TOCS, 1985. The foundational distributed snapshot
  algorithm underlying barrier-based checkpointing.
- Apache Flink Documentation. *Checkpointing* and *State Backends*. Practical
  configuration reference for checkpoint interval, incremental checkpointing, and
  state backend selection.
