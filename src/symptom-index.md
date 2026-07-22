# Symptom Index

The incident-mode entry point. Find your observable below, then follow the discriminators
to the most likely candidate patterns.

> **Status:** skeleton only — categories are laid out, entries get filled in as each
> pattern family's pages are written (see the family phases). Run `make check-symptoms`
> to see which pattern pages aren't linked here yet.

---

## Batch job is slow

### One task takes far longer than the rest

- Single key dominates a partition → [Data Skew & Salting](patterns/joins-and-shuffle/data-skew-and-salting.md)
- One executor/node is consistently slow, others fine → [Speculative Execution & Stragglers](patterns/spark-internals/speculative-execution-and-stragglers.md)

### Job spends most of its time in shuffle

- Large shuffle write/read relative to input size → [Shuffle Partitioning Strategy](patterns/joins-and-shuffle/shuffle-partitioning-strategy.md)
- Disk spill visible in stage metrics → [Spill to Disk](patterns/joins-and-shuffle/spill-to-disk.md)
- Many small, scattered shuffle reads rather than fewer large ones → [Shuffle Service Internals](patterns/joins-and-shuffle/shuffle-service-internals.md)

### Job is slow after a schema or data-volume change

- Join strategy flipped from broadcast to shuffle → [Broadcast vs. Shuffle Join](patterns/joins-and-shuffle/broadcast-vs-shuffle-join.md)
- Plan looks the same but runs slower → [Statistics & Cardinality Estimation](patterns/sql-execution/statistics-and-cardinality-estimation.md)
- A previously shuffle-free join now shuffles → [Bucketing & Co-partitioning](patterns/joins-and-shuffle/bucketing-and-co-partitioning.md)
- Hash join spills where it used to fit in memory → [Sort-Merge vs. Shuffle-Hash Join](patterns/joins-and-shuffle/sort-merge-vs-shuffle-hash-join.md)

---

## Batch job fails

### Executor OOM during shuffle or join

- Large partition, single key → [Data Skew & Salting](patterns/joins-and-shuffle/data-skew-and-salting.md)
- Memory fraction misconfigured relative to spill threshold → [Memory Management](patterns/spark-internals/memory-management.md)
- Caching an unrelated DataFrame destabilizes a shuffle stage elsewhere → [Memory Management](patterns/spark-internals/memory-management.md)

### Job fails only on full production data, not in staging

- Cardinality-dependent join strategy chosen at small scale doesn't hold at full scale → [Physical Plan Selection](patterns/spark-internals/physical-plan-selection.md)

### Job hangs with no visible task activity

- Waiting on a single straggler task before the next stage can start → [Stages, Tasks & the DAG Scheduler](patterns/spark-internals/stages-tasks-and-the-dag-scheduler.md)
- One slow task, duplicated elsewhere in the cluster → [Speculative Execution & Stragglers](patterns/spark-internals/speculative-execution-and-stragglers.md)

### Query plan looks reasonable but the job is still slow

- Physical plan differs between `explain()` and the execution UI's reported plan → [Adaptive Query Execution (AQE)](patterns/spark-internals/adaptive-query-execution.md)
- A UDF disables pushdown for everything downstream of it → [Catalyst Optimizer & Logical Plans](patterns/spark-internals/catalyst-optimizer.md)
- Fact table scan reads partitions that can't match the join filter → [Dynamic Partition Pruning](patterns/spark-internals/dynamic-partition-pruning.md)
- Significant CPU time in (de)serialization rather than computation → [Serialization & Tungsten](patterns/spark-internals/serialization-and-tungsten.md)

---

## Query plan chooses badly

### Query is correct but far slower than expected

- Wrong join order chosen, one intermediate result far larger than expected → [Join Ordering](patterns/sql-execution/join-ordering.md)
- Full scan where a filter should prune → [Predicate & Projection Pushdown](patterns/sql-execution/predicate-and-projection-pushdown.md)
- Row-at-a-time execution on a large scan → [Vectorized Execution](patterns/sql-execution/vectorized-execution.md)
- Selecting fewer columns doesn't reduce scan time → [Columnar Storage Formats](patterns/sql-execution/columnar-storage-formats.md)
- Cost-based plan choice looks reasonable but is based on wrong row-count estimates → [Query Planning & Cost-Based Optimization](patterns/sql-execution/query-planning-and-cbo.md)
- Estimated and actual row counts diverge sharply for correlated columns → [Statistics & Cardinality Estimation](patterns/sql-execution/statistics-and-cardinality-estimation.md)

### Plan changes after a routine data refresh

- Table statistics stale or not recomputed → statistics and cardinality estimation

---

## Streaming job falls behind

### Consumer lag growing steadily

- Backpressure not applied, buffers filling → backpressure in streaming
- Partition count too low for throughput → Kafka partitioning

### State size grows without bound

- Window or state TTL not configured → stateful processing and state stores

### Late-arriving data is silently dropped or double-counted

- Watermark too aggressive or too lax → watermarks and late data
- Delivery semantics assumed but not actually exactly-once → exactly-once semantics

---

## Storage layer is unhealthy

### Small-file problem: too many tiny files, listing is slow

- Compaction not keeping up with ingest rate → compaction strategies
- Object store listing cost dominating → object store characteristics

### Query touches far more data than it should

- Partition layout doesn't match query filters → partition layout and pruning

---

## Serving layer is slow or stale

### Point lookups are slow despite an OLAP-shaped backend

- Analytical engine used for a serving workload → point lookups vs. analytical scans

### Read replicas return stale data under load

- Replication lag not surfaced to callers → read replicas and staleness

---

## Query system is congested

### Queries queue for a long time before running

- No admission control or workload isolation → query admission control
- One tenant's queries starve others → query queueing and fair scheduling
