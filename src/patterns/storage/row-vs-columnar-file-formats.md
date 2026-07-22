# Row vs. Columnar File Formats

> **One-liner:** The choice between row-oriented (Avro) and column-oriented (Parquet/ORC) formats trades write simplicity for read efficiency.

## Symptom

- A high-throughput ingestion pipeline writing individual events one at a time performs
  noticeably worse against a columnar sink than against a row-oriented one, for the same
  event volume.
- Analytical queries selecting a handful of columns from a wide table are dramatically
  faster against one storage format than another storing the same logical data.
- A schema evolution (adding a column) is trivial in one format and requires a full
  table rewrite in another.
- A streaming pipeline's raw ingestion layer uses one format, and an ETL step
  immediately converts it to a different format before any analytical query touches it,
  with no apparent alternative considered.

## Mechanism

Row-oriented formats (Avro being the canonical example in the Hadoop/Spark ecosystem)
store each record's fields contiguously, one full record after another. Writing a new
record is simple and cheap: append it to the end of the file, fields and all, with no
need to touch data belonging to other records. This makes row formats a natural fit for
write-heavy, append-only workloads — event logging, message serialization between
services, streaming ingestion — where records arrive one at a time and the write path's
simplicity matters more than later read efficiency.

Columnar formats (Parquet, ORC) store each column's values contiguously instead,
requiring a write to touch every column's section of the file for even a single
logical record — this is why they are typically written in batches (buffering many
records, then writing a complete row group across all columns at once) rather than
appended one record at a time. This upfront cost buys the analytical benefits described
in [Columnar Storage Formats](../sql-execution/columnar-storage-formats.md): efficient
column pruning, better compression, and statistics-based predicate pushdown — but it
means columnar formats are a poor fit for streaming ingestion of individual records,
where the batching required to write efficiently either adds latency (waiting to
accumulate a batch) or forces many small, inefficiently-structured files if batches are
kept small (see [Compaction Strategies](compaction-strategies.md) for the resulting
cost).

Schema evolution differences follow directly from the same physical layout: a row
format's per-record structure typically allows appending new fields with defaults for
older records read under a newer schema (Avro's schema evolution rules are explicitly
designed around this compatibility model). A columnar format's per-column physical
separation makes some schema changes (especially field reordering or certain type
widenings) more consequential, since column data physically laid out under one schema
version has to be reconciled against readers using a different one.

This is precisely why a common architecture uses row-oriented formats for the initial,
write-heavy ingestion layer and converts to columnar formats for the read-heavy
analytical layer downstream — matching each format to the access pattern it was
designed for, rather than forcing one format to serve both.

## Real-world sightings

Avro's project documentation explicitly describes its design goals around efficient,
compact binary serialization with strong schema evolution support (readers and writers
can use different, compatible schema versions), motivated directly by its intended use
in high-throughput RPC and data serialization contexts — a different design target than
Parquet's analytical scan optimization.

The common "raw layer in Avro, analytical layer in Parquet" architecture is documented
across numerous vendor reference architectures for streaming-to-lakehouse pipelines
(Databricks, Confluent, AWS), consistently framing this as matching format to access
pattern: row-oriented for the append-heavy Kafka-to-storage ingestion hop, columnar for
the query-heavy analytical layer built from that raw data.

## Mitigations

### Matching format to the dominant access pattern per layer

**What it is:** Use row-oriented formats for write-heavy, append-only, streaming
ingestion layers, and columnar formats for read-heavy, analytical layers, converting
between them at the natural boundary between ingestion and analytics.

**Cost:** Requires an explicit conversion step (an ETL or streaming job) between the two
layers, adding pipeline complexity and a conversion latency window.

**How it backfires:** If the conversion step falls behind (see
[Compaction Strategies](compaction-strategies.md) for a related failure mode), the raw,
row-oriented layer accumulates data that hasn't yet reached the queryable, columnar
layer, and consumers querying only the analytical layer see an increasingly stale view
without necessarily realizing the conversion lag is the cause.

### Batching writes appropriately for columnar targets

**What it is:** Buffer records into reasonably sized batches before writing to a
columnar format, rather than writing one record (or a very small batch) per file.

**Cost:** Batching adds latency between when a record is produced and when it becomes
queryable in the columnar layer.

**How it backfires:** A batch size tuned to balance latency and file size for one
throughput level becomes wrong (too many small files, or too much latency) if
throughput shifts meaningfully in either direction without a corresponding re-tuning.

### Explicit schema evolution discipline

**What it is:** Adopt one format's schema evolution rules explicitly and enforce
compatible changes (additive fields, compatible type widenings) rather than making
changes that force full-table rewrites.

**Cost:** Constrains how freely schemas can change, requiring more upfront thought
about field design than an unconstrained approach would.

**How it backfires:** A schema-evolution discipline that's understood and followed by
one team can be silently violated by another team writing to the same table without
equivalent awareness of the constraint, especially in organizations with many
independent producers writing to shared tables.

## Interactions

- [Columnar Storage Formats](../sql-execution/columnar-storage-formats.md) — the
  analytical-side benefits that motivate converting from row to columnar format at the
  ingestion/analytics boundary.
- [Compaction Strategies](compaction-strategies.md) — the operational cost of an
  ingestion pattern that produces many small columnar files, whether from streaming
  writes or an under-batched conversion step.
- [Table Formats & Metadata Layers](table-formats-and-metadata-layers.md) — modern
  lakehouse formats add transactional guarantees on top of a chosen underlying file
  format, typically columnar, for the analytical layer.

## References

- Apache Avro Documentation. *Schema Resolution*. Describes Avro's compatibility rules
  for reading data under a different schema version than it was written with.
- Apache Parquet Documentation. *File Format*. Describes the columnar layout and its
  implications for write batching.
- Melnik, S. et al. *Dremel: Interactive Analysis of Web-Scale Datasets*. VLDB 2010.
  Foundational columnar storage design that directly informed Parquet.
