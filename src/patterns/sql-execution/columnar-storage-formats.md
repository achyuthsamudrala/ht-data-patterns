# Columnar Storage Formats

> **One-liner:** Parquet and ORC's column-oriented, chunked layout is what makes pushdown and vectorization possible in the first place.

## Symptom

- A query selecting a handful of columns from a wide table (hundreds of columns) scans
  in a small fraction of the time a `SELECT *` over the same table takes.
- Compression ratios vary dramatically by column within the same file, and columns
  with few distinct values compress far better than high-cardinality ones.
- A table written with many small appends performs worse on read than the same logical
  data written as fewer, larger files, even though total byte size is similar.
- Point-lookup queries (fetch one row by ID) against a columnar-formatted table are
  much slower than the equivalent query against a row-oriented store.

## Mechanism

Row-oriented formats store all of a row's fields contiguously — reading one row means
reading (or at least seeking past) every field of that row, which is efficient when a
query needs most or all columns of the rows it touches, but wasteful when it needs only
a few.

Columnar formats invert this: each column's values are stored contiguously, typically
further divided into row groups (Parquet) or stripes (ORC) — chunks of some number of
rows, each with its own per-column metadata. This layout directly enables three of the
optimizations covered elsewhere in this guide: **projection pushdown** (see
[Predicate & Projection Pushdown](predicate-and-projection-pushdown.md)) becomes
trivial, since unrequested columns are physically separate and simply aren't read;
**predicate pushdown** is enabled by per-row-group min/max statistics (and often bloom
filters), letting a reader skip entire chunks without inspecting individual rows; and
**vectorized execution** (see [Vectorized Execution](vectorized-execution.md)) is
natural, because a column's values are already laid out as a contiguous array, exactly
the shape vectorized operators expect.

Columnar formats also compress markedly better than row-oriented ones for typical
analytical data, because compression algorithms exploit redundancy, and values within a
single column are usually far more similar to each other (same type, often a small set
of repeated values) than values across a row's heterogeneous fields — this is why
per-column compression ratios in the symptom list above vary so much: a low-cardinality
categorical column compresses far better than a high-cardinality identifier column.

The corresponding cost is exactly what the last two symptoms describe. Small, frequent
appends fragment each column's data across many small chunks, each with its own
overhead and often duplicated or overlapping statistics ranges, degrading the very
pruning benefit that motivated columnar storage — a problem [Compaction Strategies](../storage/compaction-strategies.md)
exists to address. And a point lookup — one row, all its columns — is the exact
inverse of the access pattern columnar storage is optimized for: fetching one row's
value from every column requires touching every column's chunk containing that row,
which for a wide table can mean far more scattered reads than a row-oriented format
would require for the same lookup (see
[Point Lookups vs. Analytical Scans](../serving/point-lookups-vs-analytical-scans.md)).

## Real-world sightings

The Dremel paper (Melnik et al., VLDB 2010) is the foundational reference for
column-striping nested data at scale, directly motivating Parquet's design — Parquet's
own project documentation explicitly credits Dremel's column-striping algorithm as the
basis for representing nested and repeated fields in a columnar layout without
flattening them.

The small-file fragmentation problem for columnar formats specifically (as distinct
from the general small-file problem in distributed storage) is discussed in Delta
Lake, Iceberg, and Hudi project documentation as a primary motivation for these table
formats' compaction and file-sizing features — each explicitly frames "optimize" or
"compact" operations as necessary specifically because columnar formats' statistics-based
pruning degrades as row groups fragment across many small files.

## Mitigations

### Choosing row group / stripe size deliberately

**What it is:** Size row groups or stripes to balance pruning granularity (smaller
chunks prune more precisely) against per-chunk metadata overhead (smaller chunks mean
more of them, and more statistics to store and evaluate).

**Cost:** Requires understanding the query patterns a table will see, which isn't
always known at table-design time.

**How it backfires:** A row group size tuned for one query pattern (broad scans
benefiting from large groups) can be poorly suited to a different, later-emerging query
pattern (selective point queries benefiting from smaller groups) against the same
table.

### Compaction to counter file fragmentation

**What it is:** Periodically merge many small files into fewer, larger ones, restoring
compact, non-overlapping per-chunk statistics ranges. See
[Compaction Strategies](../storage/compaction-strategies.md).

**Cost:** Compaction itself is a read-and-rewrite operation, consuming compute and I/O
proportional to the data being compacted.

**How it backfires:** Compaction that runs less frequently than the ingest rate
requires falls permanently behind, and the fragmentation it's meant to fix accumulates
faster than it's cleared.

### Choosing row-oriented storage for point-lookup-heavy workloads

**What it is:** Use a row-oriented or hybrid storage engine for workloads dominated by
point lookups, reserving columnar formats for genuinely analytical (broad-scan) access
patterns.

**Cost:** Maintaining two storage representations (or migrating) for the same logical
data adds operational and consistency overhead.

**How it backfires:** Workload shape often isn't static — a table that starts as
purely analytical can accrue point-lookup-style serving traffic later, at which point
the storage choice made for the original workload becomes a poor fit, without an
obvious trigger for revisiting it.

## Interactions

- [Predicate & Projection Pushdown](predicate-and-projection-pushdown.md) — the
  optimization columnar layout most directly enables.
- [Vectorized Execution](vectorized-execution.md) — the execution-side counterpart that
  benefits from columnar layout's contiguous, per-column data arrangement.
- [Compaction Strategies](../storage/compaction-strategies.md) — the mitigation for
  columnar format's specific vulnerability to small-file fragmentation.

## References

- Melnik, S. et al. *Dremel: Interactive Analysis of Web-Scale Datasets*. VLDB 2010.
  Foundational column-striping algorithm for nested data.
- Apache Parquet Documentation. *File Format*. Describes row groups, column chunks, and
  per-chunk statistics.
- Apache ORC Documentation. *ORC File Format Specification*. The comparable design for
  ORC's stripe-based columnar layout.
