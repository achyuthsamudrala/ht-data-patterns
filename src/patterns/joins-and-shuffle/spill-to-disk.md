# Spill to Disk

> **One-liner:** When a shuffle or aggregation exceeds its memory budget, spilling to disk trades a memory error for a latency cliff.

## Symptom

- Task duration for a stage increases sharply and non-linearly as input size grows past
  some point, rather than scaling smoothly.
- Execution UI shows non-trivial "shuffle spill (memory)" and "shuffle spill (disk)"
  metrics for a stage that previously showed none.
- Disk I/O and local disk usage on executors spikes during a stage that doesn't
  otherwise look I/O-heavy.
- A job that used to fail with an out-of-memory error, after a memory-budget tuning
  change, now succeeds but takes an order of magnitude longer.

## Mechanism

Shuffle, sort, and hash-based aggregation operators all need working memory
proportional to the data they're processing — a sort needs to hold (or partially hold)
the data being sorted, a hash aggregation needs a hash table sized to the number of
distinct groups. Executors allocate a bounded memory budget to these operators (see
[Memory Management](../spark-internals/memory-management.md)); when an operator's
working set exceeds that budget, it has two choices: fail, or spill the excess to local
disk and continue.

Modern engines default to spilling rather than failing, which is usually the right
default — a slow job that completes is almost always preferable to a fast job that
crashes — but spilling is not a free safety valve. Per the
[shuffle cost model](../../foundations/shuffle-cost-model.md), the spilled portion of
the data now pays for: a write to local disk, a sort or merge pass to keep spilled runs
combinable, and a subsequent read back from disk when the operator resumes. None of
that cost exists for data that stayed within the memory budget. This produces the
characteristic non-linear symptom above: performance is flat (memory-bound) up to the
spill threshold and then degrades sharply once it's crossed, because every additional
byte past the threshold now costs several times what a byte under the threshold costs.

Spilling also compounds with skew (see
[Data Skew & Salting](data-skew-and-salting.md)): a single oversized partition is far
more likely to individually exceed the per-task memory budget even when the job's
*average* partition comfortably fits, because the memory budget is typically enforced
per-task, not job-wide.

## Real-world sightings

Spill-related performance cliffs are among the most commonly discussed Spark tuning
topics in vendor documentation (Databricks, AWS EMR, Google Cloud Dataproc) and
conference talks (Spark Summit / Data + AI Summit sessions on memory tuning), typically
framed as "why did my job get 10x slower after a small data increase" — the answer is
almost always a spill threshold crossed, not a proportional cost increase.

The distinction between `spark.memory.fraction` (unified memory available to execution
and storage) and the point at which execution memory pressure forces eviction and
spill is a standard topic in Spark's own tuning guide, reflecting how often the
symptom is misdiagnosed as a general "increase memory" problem rather than a specific
"increase execution memory allocation, or reduce partition size" problem.

## Mitigations

### Increasing executor memory

**What it is:** Raise the memory allocated per executor so more data fits before
spilling.

**Cost:** Larger executors are often less efficient to schedule (fewer, bigger units
mean less flexible bin-packing across the cluster) and cost proportionally more per
executor-hour.

**How it backfires:** Data volume grows faster than memory budgets are re-tuned, so
this mitigation reliably becomes insufficient again — it delays the spill cliff without
addressing why the cliff exists (usually skew or an undersized partition count).

### Increasing shuffle partition count

**What it is:** Repartition so each task handles less data, keeping individual
partitions under the spill threshold. See
[Shuffle Partitioning Strategy](shuffle-partitioning-strategy.md).

**Cost:** More, smaller partitions increase per-partition fixed overhead
(scheduling, serialization headers, small-file effects downstream).

**How it backfires:** Does nothing for skew — a hot key's partition doesn't shrink just
because the *partition count* increased, since that key still hashes to one partition.

### Adaptive partition coalescing

**What it is:** Let the engine (via AQE) size partitions at runtime based on actual
shuffle output, rather than a static partition count — merging small partitions and
avoiding oversized ones where possible. See
[Adaptive Query Execution (AQE)](../spark-internals/adaptive-query-execution.md).

**Cost:** Requires materializing shuffle output before sizing decisions can be made,
so the first-stage cost isn't reduced, only downstream stages benefit.

**How it backfires:** Coalescing merges *small* partitions effectively but has limited
ability to split an already-oversized single-key partition — that's a separate,
skew-specific optimization, not a byproduct of general coalescing.

## Interactions

- [Data Skew & Salting](data-skew-and-salting.md) — skewed keys are the most common
  root cause of a single task spilling heavily while its neighbors don't.
- [Memory Management](../spark-internals/memory-management.md) — the execution/storage
  memory split directly sets the threshold at which spill begins.
- [Sort-Merge vs. Shuffle-Hash Join](sort-merge-vs-shuffle-hash-join.md) — a spilled
  hash table (shuffle-hash join) degrades far worse than a spilled sorted stream
  (sort-merge join) for the same excess data volume.

## References

- Apache Spark Documentation. *Tuning Spark — Memory Management Overview*. Describes
  `spark.memory.fraction`, execution vs. storage memory, and spill behavior.
- Databricks Engineering Blog. *Tuning Java Garbage Collection for Apache Spark
  Applications* and related memory-tuning posts. Cover the practical diagnosis of spill
  as distinct from GC pressure.
- Graefe, G. *Query Evaluation Techniques for Large Databases*. ACM Computing Surveys,
  1993. Classical external sort/merge cost analysis underlying why spilled operators
  scale the way they do.
