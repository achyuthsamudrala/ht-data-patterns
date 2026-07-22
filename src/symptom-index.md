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

- Backpressure not applied, buffers filling → [Backpressure in Streaming](patterns/streaming/backpressure-in-streaming.md)
- Partition count too low for throughput → [Kafka Partitioning & Consumer Groups](patterns/streaming/kafka-partitioning-and-consumer-groups.md)
- Rebalance pauses the entire consumer group, not just affected partitions → [Kafka Partitioning & Consumer Groups](patterns/streaming/kafka-partitioning-and-consumer-groups.md)

### State size grows without bound

- Window or state TTL not configured → [Stateful Processing & State Stores](patterns/streaming/stateful-processing-and-state-stores.md)
- Sliding or session windows accumulating more state than expected → [Windowing Strategies](patterns/streaming/windowing-strategies.md)

### Late-arriving data is silently dropped or double-counted

- Watermark too aggressive or too lax → [Watermarks & Late Data](patterns/streaming/watermarks-and-late-data.md)
- Delivery semantics assumed but not actually exactly-once → [Exactly-Once Semantics](patterns/streaming/exactly-once-semantics.md)

### Recovery after a failure is much slower than the outage itself

- Large replay window since the last checkpoint → [Checkpointing & Fault Tolerance](patterns/streaming/checkpointing-and-fault-tolerance.md)
- Latency floor that won't go below the batch interval → [Micro-batch vs. Continuous Processing](patterns/streaming/microbatch-vs-continuous.md)

---

## Storage layer is unhealthy

### Small-file problem: too many tiny files, listing is slow

- Compaction not keeping up with ingest rate → [Compaction Strategies](patterns/storage/compaction-strategies.md)
- Object store listing cost dominating → [Object Store Characteristics](patterns/storage/object-store-characteristics.md)
- High-cardinality partition column producing tiny partitions → [Partition Layout & Pruning](patterns/storage/partition-layout-and-pruning.md)
- Write-heavy streaming ingestion into a columnar sink → [Row vs. Columnar File Formats](patterns/storage/row-vs-columnar-file-formats.md)

### Query touches far more data than it should

- Partition layout doesn't match query filters → [Partition Layout & Pruning](patterns/storage/partition-layout-and-pruning.md)

### Query planning itself is slow, before any data is scanned

- Table has accumulated many snapshots or transaction log entries → [Table Formats & Metadata Layers](patterns/storage/table-formats-and-metadata-layers.md)

### A previously-fast query against historical data becomes slow

- Data aged into a colder storage tier → [Storage Tiering](patterns/storage/storage-tiering.md)

### Data loss or unavailability despite a redundancy factor that should have covered it

- Correlated failure (rack, zone) violated the independence assumption behind replication or erasure coding → [Replication & Erasure Coding](patterns/storage/replication-and-erasure-coding.md)

---

## Serving layer is slow or stale

### Point lookups are slow despite an OLAP-shaped backend

- Analytical engine used for a serving workload → [Point Lookups vs. Analytical Scans](patterns/serving/point-lookups-vs-analytical-scans.md)

### Read replicas return stale data under load

- Replication lag not surfaced to callers → [Read Replicas & Staleness](patterns/serving/read-replicas-and-staleness.md)

### Dashboard value looks wrong or lags recent updates

- Rollup/materialized view refresh lag → [OLAP Serving Layer](patterns/serving/olap-serving-layer.md)
- Stale cache hit after a write → [Result/Query Caching](patterns/serving/result-and-query-caching.md)

### Model performs worse in production than offline evaluation suggested

- Online and offline feature computation diverge → [Feature Store Serving](patterns/serving/feature-store-serving.md)

### One partition or shard is disproportionately slow under otherwise-healthy aggregate load

- A single hot key concentrated on one partition → [Hot Partition Handling in Serving](patterns/serving/hot-partition-handling.md)

---

## Index or write path is unhealthy

### Write throughput degrades after adding an index

- Every secondary index doubles (or more) the writes per mutation → [Secondary Indexes & Write Amplification](patterns/indexing/secondary-indexes-and-write-amplification.md)

### Point-lookup latency is high and variable

- LSM-tree read path checking many unmerged sstables → [B-Tree vs. LSM-Tree Tradeoffs](patterns/indexing/btree-vs-lsm-tree.md)

### Pruning stops working for a specific column's filters

- Data isn't clustered by that column → [Sort Keys & Z-Ordering](patterns/indexing/sort-keys-and-z-ordering.md)
- Bloom filter false-positive rate has crept up past its sized capacity → [Bloom Filters & Zone Maps](patterns/indexing/bloom-filters-and-zone-maps.md)

### Search/log index size is disproportionate to source data

- High lexical diversity or per-posting metadata overhead → [Inverted Indexes for Search/Log Data](patterns/indexing/inverted-indexes.md)

### Maintenance jobs interfere with each other

- Compaction and index rebuild competing for the same I/O → [Index Maintenance vs. Compaction Interplay](patterns/indexing/index-maintenance-vs-compaction.md)

---

## Query system is congested

### Queries queue for a long time before running

- No admission control or workload isolation → [Query Admission Control & Workload Management](patterns/query-systems/query-admission-control.md)
- One tenant's queries starve others → [Query Queueing & Fair Scheduling](patterns/query-systems/query-queueing-and-fair-scheduling.md)

### Cluster-wide slowdown traced to a single node or single query

- Coordinator saturated even though workers are healthy → [Distributed Query Coordination](patterns/query-systems/distributed-query-coordination.md)
- One badly-planned or skewed query crowding out all others → [Straggler Queries & Resource Isolation](patterns/query-systems/straggler-queries-and-resource-isolation.md)

### Federated query across two systems is much slower than either alone

- Pushdown doesn't cross the federation boundary → [Query Federation Across Engines](patterns/query-systems/query-federation.md)

### Cached plan or cached result is wrong or unexpectedly missed

- Plan cache and result cache have different, independent invalidation triggers → [Result/Plan Caching](patterns/query-systems/result-and-plan-caching.md)
