# Micro-batch vs. Continuous Processing

> **One-liner:** Micro-batching trades latency for throughput and simpler fault tolerance; continuous processing inverts that tradeoff.

## Symptom

- A pipeline's minimum achievable end-to-end latency has a hard floor equal to its
  batch interval, no matter how much the per-batch processing itself is optimized.
- Reducing the micro-batch interval to improve latency increases per-batch scheduling
  and coordination overhead disproportionately, producing diminishing or negative
  returns below some interval size.
- A continuous-processing pipeline achieves lower latency than an equivalent
  micro-batch one but shows a different, more complex failure-recovery profile after an
  outage.
- Migrating a pipeline from micro-batch to continuous processing (or the reverse)
  requires reworking fault-tolerance assumptions the original implementation depended
  on, not just a configuration change.

## Mechanism

Micro-batch processing (Spark Structured Streaming's default execution mode being the
canonical example) processes the stream as a sequence of small, discrete batches on a
fixed interval — each interval's worth of new data is collected, then processed as a
self-contained bounded job, much like a small batch job run repeatedly. This inherits
batch processing's simpler fault-tolerance model directly: because each micro-batch is
a bounded unit of work, a failure partway through a batch can typically be retried by
re-running that batch from its starting offset, using the same lineage-based recomputation
model batch systems already rely on (see
[Stages, Tasks & the DAG Scheduler](../spark-internals/stages-tasks-and-the-dag-scheduler.md)).
The cost is a hard latency floor: no result can be emitted faster than the batch
interval, regardless of how quickly the actual computation completes within that
interval.

Continuous (record-at-a-time) processing removes this floor by processing each record
as it arrives, without waiting for a batch boundary — but this removes the natural
retry unit that made micro-batch fault tolerance simple. There's no obvious "batch" to
re-run after a failure; instead, continuous processing systems typically rely on a
distributed snapshot mechanism (rooted in the Chandy-Lamport algorithm for consistent
global snapshots of a distributed computation) that periodically records a consistent
point-in-time state across the entire pipeline, without pausing processing to do so,
which recovery can then roll back to. This is a fundamentally different (and more
mechanically complex) recovery model than "re-run the batch," trading fault-tolerance
simplicity for the ability to achieve latency below any fixed batch interval.

Reducing micro-batch interval to approach continuous processing's latency runs into
diminishing returns because per-batch fixed costs (scheduling the batch, coordinating
its start and completion, committing offsets) don't shrink proportionally with the
interval — at a sufficiently small interval, that fixed overhead can exceed the actual
useful processing time within the interval, which is the same fixed-overhead-dominance
pattern seen in undersized shuffle partitions (see
[Shuffle Partitioning Strategy](../joins-and-shuffle/shuffle-partitioning-strategy.md)).

## Real-world sightings

Spark's own documentation for its Continuous Processing mode (introduced as an
experimental alternative to the default micro-batch engine in Structured Streaming)
explicitly frames the tradeoff in these terms: continuous processing targets
millisecond-scale latency at the cost of different, more limited fault-tolerance and
operator support compared to the mature micro-batch engine, and explicitly recommends
micro-batch as the default choice unless the specific latency requirement justifies the
tradeoff.

The Chandy-Lamport snapshot algorithm underlying Flink's checkpointing (and, by
extension, its ability to support low-latency continuous processing with fault
tolerance) is described in Carbone et al.'s "Lightweight Asynchronous Snapshots for
Distributed Dataflows," which explicitly credits the original Chandy-Lamport
distributed snapshot algorithm (Chandy and Lamport, 1985) as the theoretical basis for
taking consistent, non-blocking snapshots of an actively running distributed
computation — precisely the mechanism needed to make continuous processing
recoverable without reintroducing the batch-boundary retry unit.

## Mitigations

### Defaulting to micro-batch unless latency requirements demand otherwise

**What it is:** Use micro-batch processing as the default architecture, reserving
continuous processing for use cases with a genuine, specific sub-second latency
requirement.

**Cost:** Micro-batch's latency floor may not meet requirements that emerge later even
if they weren't present at initial design time.

**How it backfires:** None specific to choosing this default — the risk is
under-provisioning for a latency requirement that appears after the architecture is
already committed, which then requires the more disruptive continuous-processing
migration described above.

### Tuning batch interval to the point of diminishing returns, not below it

**What it is:** Reduce micro-batch interval only as far as the point where per-batch
fixed overhead remains small relative to useful processing time, rather than chasing
latency reduction past that point.

**Cost:** Requires profiling to find the actual diminishing-returns point for a
specific workload, rather than applying a rule of thumb.

**How it backfires:** A batch interval tuned for today's per-batch overhead can need
re-tuning if the pipeline's operator mix changes (more or fewer stages, different
coordination overhead), since the diminishing-returns point is workload-specific, not
fixed.

### Explicit fault-tolerance redesign when migrating processing models

**What it is:** Treat a migration between micro-batch and continuous processing as a
fault-tolerance redesign, not a configuration toggle — verifying recovery behavior
under the new model rather than assuming it inherits the old model's guarantees.

**Cost:** Requires dedicated testing of failure and recovery scenarios specifically for
the new processing model, adding migration effort beyond the processing logic itself.

**How it backfires:** Skipping this step and treating the migration as "just a
config change" is precisely how continuous processing's different, more complex
recovery characteristics go undiscovered until an actual production failure exposes
them.

## Interactions

- [Batch vs. Streaming Spectrum](../../foundations/batch-vs-streaming-spectrum.md) — the
  foundational latency/throughput/consistency tradeoff this pattern applies specifically
  to the batch-interval decision within streaming.
- [Checkpointing & Fault Tolerance](checkpointing-and-fault-tolerance.md) — the
  distributed snapshot mechanism that makes continuous processing's fault tolerance
  possible at all.
- [Shuffle Partitioning Strategy](../joins-and-shuffle/shuffle-partitioning-strategy.md) —
  the same fixed-overhead-versus-unit-size tradeoff pattern, applied to shuffle
  partitions instead of batch intervals.

## References

- Apache Spark Documentation. *Structured Streaming Programming Guide — Continuous
  Processing*. Describes the experimental continuous processing mode and its tradeoffs
  relative to micro-batch.
- Chandy, K. M. and Lamport, L. *Distributed Snapshots: Determining Global States of
  Distributed Systems*. ACM TOCS, 1985. The original distributed snapshot algorithm.
- Carbone, P. et al. *Lightweight Asynchronous Snapshots for Distributed Dataflows*.
  2015. Describes Flink's checkpointing mechanism built on Chandy-Lamport snapshots.
