# Table Formats & Metadata Layers

> **One-liner:** Iceberg, Delta, and Hudi add snapshot isolation and time travel over plain files — but the metadata layer itself becomes a scaling bottleneck.

## Symptom

- Query planning time grows noticeably as a table accumulates more historical
  snapshots or transaction log entries, even though the amount of *current* data being
  queried hasn't changed.
- Listing a table's current set of files takes longer than actually reading them, once
  the table has undergone many small commits over time.
- A table's metadata (manifest files, transaction log, commit history) grows to a size
  comparable to or exceeding the data it describes.
- Concurrent writers to the same table experience increasing commit conflicts or
  retries as write concurrency increases, even when their actual data writes don't
  logically overlap.

## Mechanism

Plain columnar files on an object store have no built-in way to answer "what is the
current, correct set of files for this table" atomically — a reader listing files
directly can see a partially-written commit, or an inconsistent view during a
concurrent write. Table formats (Apache Iceberg, Delta Lake, Apache Hudi) solve this by
introducing a metadata layer: a sequence of immutable snapshots or a transaction log
that atomically records which underlying files constitute the table's state at each
point in time, enabling snapshot isolation (readers always see a consistent view) and
time travel (querying the table as of a prior snapshot).

This metadata layer is itself a data structure with its own scaling characteristics,
and it can become the bottleneck it was designed to route around. Every commit adds an
entry to this layer — a new manifest file, a new transaction log entry — and if commits
happen frequently (many small writes rather than fewer large ones), metadata volume
grows roughly in proportion to commit *count*, not to data volume. A query planner
has to read enough of this metadata to determine the current file set before it can
even begin planning the actual scan, so metadata size directly adds latency to every
query's planning phase, independent of how much data the query ultimately needs to
read.

Concurrent write conflicts follow from the same design: most table formats implement
optimistic concurrency control at the commit layer — a writer reads the current
metadata state, prepares its change, and attempts to commit atomically against that
state, retrying if another writer committed first. Under low write concurrency this
almost never conflicts; under high concurrency (many writers targeting overlapping
partitions or the same table root), the retry rate rises, and — because a retry means
re-reading current metadata and reattempting the commit — this compounds under
sustained high concurrency rather than resolving itself.

## Real-world sightings

The Delta Lake paper (Armbrust et al., "Delta Lake: High-Performance ACID Table
Storage over Cloud Object Stores," VLDB 2020) explicitly describes the transaction log
as the mechanism providing ACID guarantees over plain object-store files, and discusses
log compaction (periodically consolidating the log into checkpoint files) as a
necessary mitigation for log growth over the table's lifetime — directly acknowledging
that unbounded log growth would otherwise degrade query planning performance.

Apache Iceberg's documentation on manifest files and metadata management describes
similar concerns, including manifest file rewriting/compaction operations explicitly
recommended as tables accumulate many small commits, and both Iceberg's and Hudi's
project documentation discuss optimistic concurrency conflict rates as a function of
write concurrency and partition overlap, generally recommending partitioning writes to
reduce overlapping commit contention where high write concurrency is expected.

## Mitigations

### Periodic metadata compaction / checkpointing

**What it is:** Consolidate accumulated transaction log entries or manifest files into
compact checkpoint representations, bounding metadata read cost for query planning.

**Cost:** Compaction itself is a maintenance operation consuming compute, and needs to
run frequently enough to keep pace with commit rate.

**How it backfires:** Metadata compaction that falls behind commit rate (the same
falling-behind failure mode as data compaction — see
[Compaction Strategies](compaction-strategies.md)) allows metadata size to grow
unbounded in the interim, and catching up requires processing an increasingly large
backlog.

### Batching writes to reduce commit frequency

**What it is:** Batch multiple logical writes into fewer, larger commits rather than
committing every small write individually, directly reducing metadata growth rate.

**Cost:** Batching writes trades write latency (data isn't committed, and therefore not
queryable, until the batch completes) for reduced metadata overhead.

**How it backfires:** A batching window tuned for a given write rate needs re-tuning if
write frequency changes substantially, and under-batched high-frequency writes reproduce
the same metadata bloat this mitigation is meant to avoid.

### Partitioning writes to reduce concurrent commit conflicts

**What it is:** Structure concurrent writers to target non-overlapping partitions where
possible, reducing the optimistic-concurrency conflict rate under high write
concurrency.

**Cost:** Requires coordinating writers' target partitions, which adds operational
complexity especially across independently-operated pipelines writing to a shared
table.

**How it backfires:** As write concurrency grows over time, a partitioning scheme that
successfully avoided conflicts at a lower concurrency level can start conflicting
again once enough writers are active, without a clear signal that the original
partitioning assumption has been outgrown.

## Interactions

- [Compaction Strategies](compaction-strategies.md) — data-file compaction and
  metadata-layer compaction are related but distinct maintenance operations, both
  necessary and both subject to the same "falls behind and compounds" failure mode.
- [Row vs. Columnar File Formats](row-vs-columnar-file-formats.md) — table formats
  typically sit on top of a columnar file format as their underlying storage,
  inheriting that format's own characteristics in addition to their own metadata layer.
- [Distributed Query Coordination](../query-systems/distributed-query-coordination.md) —
  a query coordinator's planning phase is directly exposed to metadata-layer read cost
  before it can even begin scheduling the actual scan.

## References

- Armbrust, M. et al. *Delta Lake: High-Performance ACID Table Storage over Cloud
  Object Stores*. VLDB 2020. Describes the transaction log design and log compaction.
- Apache Iceberg Documentation. *Maintenance — Manifest Rewriting*. Describes manifest
  file growth and compaction recommendations.
- Apache Hudi Documentation. *Concurrency Control*. Describes optimistic concurrency
  control and conflict resolution under concurrent writes.
