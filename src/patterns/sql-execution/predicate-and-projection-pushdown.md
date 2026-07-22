# Predicate & Projection Pushdown

> **One-liner:** Pushing filters and column selection down to the storage layer avoids reading data the query will discard anyway.

## Symptom

- A query that filters on a small fraction of a table's rows still shows a full-table
  scan in I/O metrics, reading far more data than the filter should require.
- Selecting fewer columns from a wide table doesn't reduce scan time proportionally,
  even though the storage format is column-oriented.
- A filter placed after a join or a user-defined transformation doesn't push down to
  the scan, while a logically equivalent filter placed before it does.
- Query I/O drops sharply after rewriting a filter to use a simpler expression, with no
  change to the filter's logical meaning.

## Mechanism

Pushdown is the optimization of moving a filter (predicate pushdown) or a column
selection (projection pushdown) as close as possible to the point where data is
physically read, so that data excluded by the filter or unused by the query is never
read into memory at all, rather than being read and then discarded.

This requires the storage layer to be able to act on the pushed-down predicate or
projection. Columnar formats (see
[Columnar Storage Formats](columnar-storage-formats.md)) support both natively:
projection pushdown is straightforward because columns are stored separately and
unrequested columns can simply not be read; predicate pushdown is enabled by per-chunk
or per-row-group statistics (min/max values, sometimes bloom filters — see
[Bloom Filters & Zone Maps](../indexing/bloom-filters-and-zone-maps.md)) that let the
reader skip entire chunks that provably cannot satisfy the filter, without inspecting
individual rows.

Pushdown has real limits, and understanding them explains most of the symptom list
above. A filter expressed as a user-defined function is opaque to the planner — it
cannot push down a predicate it cannot statically analyze, so the filter still applies,
but only after the data has already been read (see
[Catalyst Optimizer & Logical Plans](../spark-internals/catalyst-optimizer.md) for the
same opacity problem in a different context). A filter placed logically after a join
or aggregation can sometimes be pushed below that operator by the optimizer (if doing so
is provably safe) but isn't guaranteed to be — pushdown across a join requires the
filter to reference only columns available before the join, and complex expressions
can defeat the optimizer's ability to prove this safely.

## Real-world sightings

The role of per-row-group statistics in enabling predicate pushdown is a core, explicit
part of the Parquet format design, described in the original Dremel paper (Melnik et
al., "Dremel: Interactive Analysis of Web-Scale Datasets," VLDB 2010) whose columnar
storage approach directly informed Parquet's design, and reiterated in Parquet's own
project documentation describing min/max statistics and (optionally) bloom filters
stored per column chunk specifically to support pushdown-based chunk skipping without
reading full row groups.

The opacity of UDFs to pushdown optimization is a widely repeated finding in Spark and
Presto/Trino performance guidance, generally framed with the same recommendation:
prefer native SQL expressions the optimizer can analyze, and treat pushdown as a
property that has to be *preserved* through a query's transformations rather than one
that's automatically guaranteed regardless of how a filter is expressed.

## Mitigations

### Expressing filters as native, analyzable predicates

**What it is:** Write filter conditions using standard comparison and logical
operators the optimizer understands, rather than wrapping them in opaque
user-defined functions.

**Cost:** Genuinely complex filter logic sometimes requires custom code, trading
optimizer visibility for expressiveness.

**How it backfires:** Not a backfire so much as an incomplete fix — some filtering
logic really does need custom code, and no amount of preference for native expressions
removes that need; the mitigation reduces unnecessary pushdown loss, not all of it.

### Maintaining useful column statistics in the storage format

**What it is:** Ensure written files include per-chunk min/max statistics (and bloom
filters where beneficial), which most modern writers do by default but which can be
disabled or degraded by certain write configurations.

**Cost:** Statistics add modest file size and write-time overhead.

**How it backfires:** Statistics computed at write time reflect that write's data
distribution; if a column's distribution shifts significantly across many small
appended writes, per-file statistics can become fragmented (many files each covering a
similar, overlapping range) and less useful for pruning — see
[Compaction Strategies](../storage/compaction-strategies.md).

### Structuring queries so filters precede joins where semantically valid

**What it is:** Write queries so restrictive filters are applied to the smallest
possible input before joining, both to help the optimizer prove pushdown safety and to
reduce shuffle volume regardless of whether automatic pushdown succeeds.

**Cost:** Requires understanding which filter placements are semantically equivalent
(some are not — an outer join changes which filter placements preserve correctness),
adding query-authoring complexity.

**How it backfires:** A filter manually pushed to preserve performance can silently
change query semantics if the join type isn't a simple inner join — this mitigation
requires real care, not blind application.

## Interactions

- [Columnar Storage Formats](columnar-storage-formats.md) — the storage-layer
  precondition that makes pushdown possible at all.
- [Catalyst Optimizer & Logical Plans](../spark-internals/catalyst-optimizer.md) — the
  rule-based optimization phase responsible for deciding whether a given predicate can
  be safely pushed down.
- [Dynamic Partition Pruning](../spark-internals/dynamic-partition-pruning.md) — a
  related but distinct optimization: pushdown applies statically-known filters,
  dynamic partition pruning applies filters only known at runtime.

## References

- Melnik, S. et al. *Dremel: Interactive Analysis of Web-Scale Datasets*. VLDB 2010.
  The columnar storage and statistics design that directly informed Parquet.
- Apache Parquet Documentation. *File Format*. Describes per-column-chunk statistics
  and their role in predicate pushdown and chunk skipping.
- Databricks Engineering Blog. *Introducing Pandas UDF for PySpark* and related
  performance guidance. Documents the pushdown-blocking effect of opaque UDFs.
