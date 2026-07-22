# Shuffle Partitioning Strategy

> **One-liner:** The number and sizing of shuffle partitions controls the tradeoff between per-task overhead and per-task memory pressure.

## Symptom

- A job configured with a fixed shuffle partition count (commonly the default of 200)
  performs well on one dataset size and poorly — either from spill or from scheduling
  overhead — on another.
- The execution UI shows either thousands of tiny, sub-second tasks (overhead-bound) or
  a handful of very large tasks (memory-bound) for the same shuffle stage across
  different runs.
- Total job wall-clock time is dominated by task scheduling and coordination overhead
  rather than by useful compute, visible as many short tasks with a large gap between
  total CPU time and total wall-clock time.
- Downstream jobs reading this job's output complain about "too many small files,"
  traceable back to an oversized shuffle partition count on the upstream write.

## Mechanism

Shuffle partition count is the single configuration value with the widest-reaching
effect on a batch job's performance, because it directly sets the size of the unit that
every downstream cost in the [shuffle cost model](../../foundations/shuffle-cost-model.md)
scales against.

**Too few partitions** means each partition is large. Large partitions are more likely
to exceed the per-task memory budget and spill (see [Spill to Disk](spill-to-disk.md)),
and they reduce parallelism — a fixed number of large units of work can't be spread
across more cores than there are units, leaving cluster capacity idle even under heavy
load.

**Too many partitions** means each partition is small, which avoids spill, but shifts
the bottleneck to fixed per-partition overhead: task scheduling, serialization headers,
network connection setup, and (if writing output) small-file proliferation in the
target storage system (see [Compaction Strategies](../storage/compaction-strategies.md)
for the read-side cost of that proliferation). At the extreme, the overhead of
scheduling and coordinating a task can exceed the task's actual compute time, and total
wall-clock time increases even though no individual task is doing more work.

A single static partition count cannot be simultaneously right for a job's small daily
runs and its large monthly runs, because the "right" count is a function of total
shuffle volume divided by a target per-partition size — not a fixed number. This is
precisely the argument for adaptive partition sizing: rather than have an engineer
guess a number that will be wrong at some data volume, let the engine measure actual
shuffle output at runtime and merge or split accordingly.

## Real-world sightings

Spark's historical default of 200 shuffle partitions
(`spark.sql.shuffle.partitions`) is one of the most frequently cited "gotcha" defaults
in Spark tuning literature and vendor blog posts, because it was chosen as a reasonable
default for moderate-sized clusters and datasets circa Spark's early adoption, and
scales poorly in both directions — too many partitions for small jobs (dominated by
per-task overhead) and too few for genuinely large jobs (dominated by spill and reduced
parallelism). Adaptive Query Execution's partition-coalescing feature was motivated
directly by this problem: rather than requiring every job to hand-tune this value,
Spark added the ability to merge small post-shuffle partitions automatically based on
target size thresholds, described extensively in Databricks' AQE engineering posts.

## Mitigations

### Hand-tuning partition count per job

**What it is:** Set `spark.sql.shuffle.partitions` (or equivalent) explicitly per
workload based on known, stable data volume.

**Cost:** Requires re-tuning whenever data volume shifts meaningfully, and is easy to
leave stale after a workload's scale changes gradually rather than in one visible step.

**How it backfires:** A value tuned for a job's typical run silently stops being
correct as data grows organically — nothing alerts on this, because the job still
succeeds, just slower or spilling more than it needs to.

### Adaptive partition coalescing

**What it is:** Let the engine merge small post-shuffle partitions at runtime, sizing
toward a target partition size rather than a fixed count. See
[Adaptive Query Execution (AQE)](../spark-internals/adaptive-query-execution.md).

**Cost:** Coalescing decisions happen at shuffle-stage boundaries and can't retroactively
resize partitions from an already-scheduled stage.

**How it backfires:** Coalescing is effective at merging oversupplied small partitions,
but is a separate mechanism from skew-based splitting (see
[Data Skew & Salting](data-skew-and-salting.md)) — a single hot-key partition isn't
"fixed" by a coalescing pass tuned for the average case.

### Partitioning by target output file size (write-side)

**What it is:** For jobs that write output, size partitions to target a specific output
file size (e.g., a few hundred MB per file) rather than an arbitrary partition count, to
avoid downstream small-file problems.

**Cost:** Requires a repartition or coalesce step specifically for the write, which can
add a shuffle that wouldn't otherwise be necessary if the in-job partition count was
already reasonable for compute.

**How it backfires:** Optimizing purely for output file size can under-partition for
the compute stages that precede the write, reintroducing spill risk in exchange for
clean output files.

## Interactions

- [Spill to Disk](spill-to-disk.md) — undersized partition count is the most direct
  cause of spill that isn't rooted in skew.
- [Compaction Strategies](../storage/compaction-strategies.md) — oversized partition
  count on a write-heavy job is a direct cause of the small-file problem downstream
  readers then have to compact away.
- [Data Skew & Salting](data-skew-and-salting.md) — partition count tuning addresses
  average partition size; it does not address a single skewed key, which requires a
  separate mitigation regardless of how well the overall count is tuned.

## References

- Apache Spark Documentation. *Performance Tuning — Adaptive Query Execution*. Covers
  `spark.sql.adaptive.coalescePartitions` and the target-size-based merging logic.
- Databricks Engineering Blog. *Adaptive Query Execution: Speeding Up Spark SQL at
  Runtime*. Explains the historical problems with a fixed shuffle partition count and
  the motivation for adaptive coalescing.
- Zaharia, M. et al. *Resilient Distributed Datasets: A Fault-Tolerant Abstraction for
  In-Memory Cluster Computing*. NSDI 2012. Foundational description of Spark's
  partition-based execution model.
