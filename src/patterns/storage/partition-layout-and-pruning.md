# Partition Layout & Pruning

> **One-liner:** A partition scheme that doesn't match query filter patterns turns every query into a full scan, regardless of file format.

## Symptom

- A query that filters on a column not part of the partition scheme scans every
  partition, regardless of how selective the filter would be if the storage layout
  supported pruning on it.
- Two structurally similar queries against the same table show very different scan
  volumes, depending on whether their filter aligns with the partition columns.
- A table partitioned by a high-cardinality column (user ID, request ID) produces an
  enormous number of tiny partitions, each suffering the small-file problems described
  in [Compaction Strategies](compaction-strategies.md).
- A partition scheme chosen early in a table's life no longer matches the dominant
  query pattern, and query performance has degraded gradually as usage shifted away
  from that original assumption.

## Mechanism

Partitioning a table physically segregates data by the value of one or more columns —
commonly a date, a region, or a category — so that a query filtering on that column can
skip reading partitions that provably don't match, without needing to open a single
file in them. This is the storage-layer, physical counterpart to
[Predicate & Projection Pushdown](../sql-execution/predicate-and-projection-pushdown.md):
partition pruning happens before pushdown even gets a chance to operate on individual
files, because unmatched partitions are never listed or opened at all.

This benefit is entirely contingent on the query's filter aligning with the
partition scheme. A table partitioned by date, queried with a filter on customer ID,
gets no pruning benefit whatsoever from the date partitioning — every partition still
has to be scanned, because the filter provides no information about which date
partitions can be skipped. This is a common, easy-to-miss mismatch: a partition scheme
designed around the dominant query pattern at table-design time silently stops helping
once query patterns shift, without any error or warning — the query still runs
correctly, just as a full scan.

Partition granularity is itself a tradeoff. Coarse partitioning (e.g., partitioning by
month rather than by day) reduces the number of partitions but means each partition
covers more data, reducing the pruning benefit's precision. Fine partitioning
(partitioning by a high-cardinality column, or a very granular time bucket) maximizes
pruning precision but risks the small-file problem directly — each partition,
especially for a table with modest total volume, can end up containing very few rows,
turning partition proliferation into the same fragmentation cost
[Compaction Strategies](compaction-strategies.md) describes for files generally, just
at the partition-directory level instead of the file level.

## Real-world sightings

Partition design guidance in Hive (the original source of the partitioning conventions
most lakehouse formats still use) and subsequent lakehouse table format documentation
(Iceberg, Delta, Hudi) consistently warns against partitioning by high-cardinality
columns specifically because of the resulting small-partition, small-file
proliferation — this is one of the most commonly repeated data-warehousing design
mistakes across vendor best-practice documentation.

Apache Iceberg's "hidden partitioning" feature is explicitly motivated by a related but
distinct problem: traditional Hive-style partitioning requires queries to filter on the
literal partition column, and a query filtering on a derived expression of that column
(a timestamp filtered by date, when the table is partitioned by a computed date column)
can fail to get pruning if the planner can't recognize the equivalence. Iceberg's
design documentation describes hidden partitioning as removing this brittleness by
tracking the transform relationship (e.g., "day of timestamp") as metadata, so queries
filtering on the raw timestamp column still get correct pruning without needing to
reference the derived partition column explicitly.

## Mitigations

### Partitioning on columns matching the dominant, stable query pattern

**What it is:** Choose partition columns based on the most common and stable filter
patterns actual queries use against the table, rather than an arbitrary or
convenience-driven column choice.

**Cost:** Requires understanding query patterns at table-design time, which may not be
fully known for a new table, and a scheme optimized for one query pattern may not help
a different, less common one.

**How it backfires:** Query patterns evolve — a table designed around today's dominant
filter can become poorly matched as usage shifts, and there's no automatic signal that
the original partition design assumption has been outgrown, only gradually worsening
scan volumes.

### Choosing partition granularity to avoid small-partition proliferation

**What it is:** Size partition granularity (e.g., daily vs. monthly) to keep individual
partitions reasonably sized given the table's actual data volume, rather than
maximizing pruning precision at all costs.

**Cost:** Coarser partitioning trades some pruning precision for fewer, larger,
healthier partitions.

**How it backfires:** A granularity tuned for a table's current data volume can need
re-tuning (repartitioning, which requires a rewrite) as volume grows or shrinks
substantially.

### Hidden or transform-based partitioning

**What it is:** Use table format features (like Iceberg's hidden partitioning) that
track partition transforms as metadata, so queries filtering on the raw column still
get pruning without needing to reference a derived partition column explicitly.

**Cost:** Ties the table to a specific table format's capability, and requires that
format's version and configuration to actually support the feature.

**How it backfires:** None specific to correct usage — this mitigation directly
removes the brittleness it targets; the risk is only in assuming a table format
supports this feature without verifying the specific version and configuration in use.

## Interactions

- [Predicate & Projection Pushdown](../sql-execution/predicate-and-projection-pushdown.md) —
  partition pruning is the physical, directory-level counterpart operating one level
  above file-level pushdown.
- [Dynamic Partition Pruning](../spark-internals/dynamic-partition-pruning.md) — the
  runtime, join-aware complement to this page's static, filter-based partition
  pruning.
- [Compaction Strategies](compaction-strategies.md) — over-granular partitioning
  produces the same small-file fragmentation this pattern addresses at the file level.

## References

- Apache Hive Documentation. *Partitioned Tables*. The original partitioning
  conventions and guidance against high-cardinality partition columns.
- Apache Iceberg Documentation. *Partitioning — Hidden Partitioning*. Describes
  transform-based partitioning and its resilience to filter-expression mismatches.
- Apache Spark Documentation. *Partition Discovery*. Describes how partition column
  values are inferred from directory structure and used for pruning.
