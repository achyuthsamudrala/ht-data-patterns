# Summary

[Introduction](introduction.md)
[Symptom Index](symptom-index.md)
[Interaction Map](interaction-map.md)

---

# Foundations

- [Partitioning & Data Locality](foundations/partitioning-and-data-locality.md)
- [The Memory & I/O Hierarchy](foundations/the-memory-and-io-hierarchy.md)
- [Batch vs. Streaming: The Latency/Throughput/Consistency Spectrum](foundations/batch-vs-streaming-spectrum.md)
- [Event Time vs. Processing Time](foundations/event-time-vs-processing-time.md)
- [Consistency Models for Distributed Data](foundations/consistency-models-for-distributed-data.md)
- [The Cost Model of Shuffle](foundations/shuffle-cost-model.md)

---

# Patterns


- [Joins & Shuffle](patterns/joins-and-shuffle/index.md)
  - [Broadcast vs. Shuffle Join](patterns/joins-and-shuffle/broadcast-vs-shuffle-join.md)
  - [Sort-Merge vs. Shuffle-Hash Join](patterns/joins-and-shuffle/sort-merge-vs-shuffle-hash-join.md)
  - [Data Skew & Salting](patterns/joins-and-shuffle/data-skew-and-salting.md)
  - [Spill to Disk](patterns/joins-and-shuffle/spill-to-disk.md)
  - [Shuffle Partitioning Strategy](patterns/joins-and-shuffle/shuffle-partitioning-strategy.md)
  - [Bucketing & Co-partitioning](patterns/joins-and-shuffle/bucketing-and-co-partitioning.md)
  - [Shuffle Service Internals](patterns/joins-and-shuffle/shuffle-service-internals.md)

- [Spark / Batch Engine Internals](patterns/spark-internals/index.md)
  - [Catalyst Optimizer & Logical Plans](patterns/spark-internals/catalyst-optimizer.md)
  - [Physical Plan Selection](patterns/spark-internals/physical-plan-selection.md)
  - [Stages, Tasks & the DAG Scheduler](patterns/spark-internals/stages-tasks-and-the-dag-scheduler.md)
  - [Adaptive Query Execution (AQE)](patterns/spark-internals/adaptive-query-execution.md)
  - [Memory Management](patterns/spark-internals/memory-management.md)
  - [Speculative Execution & Stragglers](patterns/spark-internals/speculative-execution-and-stragglers.md)
  - [Dynamic Partition Pruning](patterns/spark-internals/dynamic-partition-pruning.md)
  - [Serialization & Tungsten](patterns/spark-internals/serialization-and-tungsten.md)

- [SQL Query Execution](patterns/sql-execution/index.md)
  - [Query Planning & Cost-Based Optimization](patterns/sql-execution/query-planning-and-cbo.md)
  - [Predicate & Projection Pushdown](patterns/sql-execution/predicate-and-projection-pushdown.md)
  - [Vectorized Execution](patterns/sql-execution/vectorized-execution.md)
  - [Columnar Storage Formats](patterns/sql-execution/columnar-storage-formats.md)
  - [Join Ordering](patterns/sql-execution/join-ordering.md)
  - [Statistics & Cardinality Estimation](patterns/sql-execution/statistics-and-cardinality-estimation.md)
  - [Aggregation Strategies](patterns/sql-execution/aggregation-strategies.md)
  - [SQL Window Functions](patterns/sql-execution/sql-window-functions.md)

- [Event-Driven / Streaming Systems](patterns/streaming/index.md)
  - [Kafka Partitioning & Consumer Groups](patterns/streaming/kafka-partitioning-and-consumer-groups.md)
  - [Exactly-Once Semantics](patterns/streaming/exactly-once-semantics.md)
  - [Watermarks & Late Data](patterns/streaming/watermarks-and-late-data.md)
  - [Windowing Strategies](patterns/streaming/windowing-strategies.md)
  - [Backpressure in Streaming](patterns/streaming/backpressure-in-streaming.md)
  - [Stateful Processing & State Stores](patterns/streaming/stateful-processing-and-state-stores.md)
  - [Micro-batch vs. Continuous Processing](patterns/streaming/microbatch-vs-continuous.md)
  - [Checkpointing & Fault Tolerance](patterns/streaming/checkpointing-and-fault-tolerance.md)

- [Storage Systems](patterns/storage/index.md)
  - [Row vs. Columnar File Formats](patterns/storage/row-vs-columnar-file-formats.md)
  - [Table Formats & Metadata Layers](patterns/storage/table-formats-and-metadata-layers.md)
  - [Compaction Strategies](patterns/storage/compaction-strategies.md)
  - [Partition Layout & Pruning](patterns/storage/partition-layout-and-pruning.md)
  - [Storage Tiering](patterns/storage/storage-tiering.md)
  - [Object Store Characteristics](patterns/storage/object-store-characteristics.md)
  - [Replication & Erasure Coding](patterns/storage/replication-and-erasure-coding.md)

- [Serving Systems](patterns/serving/index.md)
  - [OLAP Serving Layer](patterns/serving/olap-serving-layer.md)
  - [Point Lookups vs. Analytical Scans](patterns/serving/point-lookups-vs-analytical-scans.md)
  - [Read Replicas & Staleness](patterns/serving/read-replicas-and-staleness.md)
  - [Feature Store Serving](patterns/serving/feature-store-serving.md)
  - [Result/Query Caching](patterns/serving/result-and-query-caching.md)
  - [Hot Partition Handling in Serving](patterns/serving/hot-partition-handling.md)

- [Indexing Systems](patterns/indexing/index.md)
  - [B-Tree vs. LSM-Tree Tradeoffs](patterns/indexing/btree-vs-lsm-tree.md)
  - [Secondary Indexes & Write Amplification](patterns/indexing/secondary-indexes-and-write-amplification.md)
  - [Bloom Filters & Zone Maps](patterns/indexing/bloom-filters-and-zone-maps.md)
  - [Sort Keys & Z-Ordering](patterns/indexing/sort-keys-and-z-ordering.md)
  - [Inverted Indexes for Search/Log Data](patterns/indexing/inverted-indexes.md)
  - [Index Maintenance vs. Compaction Interplay](patterns/indexing/index-maintenance-vs-compaction.md)

- [Query Systems](patterns/query-systems/index.md)
  - [Distributed Query Coordination](patterns/query-systems/distributed-query-coordination.md)
  - [Query Admission Control & Workload Management](patterns/query-systems/query-admission-control.md)
  - [Query Federation Across Engines](patterns/query-systems/query-federation.md)
  - [Query Queueing & Fair Scheduling](patterns/query-systems/query-queueing-and-fair-scheduling.md)
  - [Result/Plan Caching](patterns/query-systems/result-and-plan-caching.md)
  - [Straggler Queries & Resource Isolation](patterns/query-systems/straggler-queries-and-resource-isolation.md)
