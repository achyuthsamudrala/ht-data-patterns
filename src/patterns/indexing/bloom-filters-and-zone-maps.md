# Bloom Filters & Zone Maps

> **One-liner:** Probabilistic and min/max pruning structures let an engine skip data without reading it — until a workload's access pattern defeats their assumptions.

## Symptom

- Query pruning effectiveness (fraction of files or row groups skipped) drops sharply
  for a specific column's filters, even though the same pruning structures work well
  for other columns in the same table.
- A bloom filter's false-positive rate rises noticeably over time as more distinct
  values are inserted into it than it was originally sized for.
- Zone map (min/max) pruning provides no benefit for a column that's frequently
  updated out of its originally-written sort order, even though the same column pruned
  effectively when the data was first written.
- Enabling bloom filters on a column with very high cardinality provides negligible
  pruning benefit relative to the storage and maintenance cost of the filter itself.

## Mechanism

Both structures let a reader decide whether a chunk of data (a file, a row group, an
sstable) could possibly contain a value the query is looking for, without reading the
chunk's actual data — the pruning benefit described in
[Predicate & Projection Pushdown](../sql-execution/predicate-and-projection-pushdown.md)
and [Columnar Storage Formats](../sql-execution/columnar-storage-formats.md). They
achieve this with different mechanisms and different failure modes.

**Zone maps** (min/max statistics per chunk) let a reader skip a chunk if a query's
filter value falls outside that chunk's recorded min/max range. This is exact (no
false positives — if the value truly is outside the range, the chunk truly cannot
contain it) but only useful when data is at least loosely sorted or clustered by the
filtered column: if a column's values are scattered randomly across chunks (no
correlation between write order and that column's values), every chunk's min/max range
covers nearly the full domain, and zone maps provide no pruning benefit at all,
regardless of how selective the query's filter actually is.

**Bloom filters** are probabilistic set-membership structures: they can definitively
say "this value is not present," but can only say "this value is probably present" —
false positives are possible (the filter says "maybe present" for a value that isn't
actually there), though false negatives are not (the filter never wrongly says "not
present" for a value that is). This makes bloom filters valuable for high-cardinality
columns where zone maps don't help (no natural ordering to exploit), but they have
their own resource tradeoff: filter size and false-positive rate trade against each
other for a fixed number of distinct values, and a filter sized for one insertion volume
sees its false-positive rate climb if actually populated with more distinct values than
planned — a filter whose false-positive rate degrades doesn't fail outright, it just
becomes progressively less useful for pruning, silently, as more "maybe present"
answers accumulate for values that in fact are not present.

Both structures share a common vulnerability: they're computed once, typically at
write time, against the data as it existed then. A column that's updated out of its
original write-time sort order (for zone maps) or whose value distribution shifts
substantially after the filter was sized (for bloom filters) degrades in pruning
effectiveness without any explicit signal that this has happened — the query still
returns correct results, just without the pruning benefit these structures were meant
to provide.

## Real-world sightings

Zone map pruning (also called "min-max indexes" or, in some systems, "small
materialized aggregates") is a foundational technique in columnar analytical
databases, and its dependence on data clustering by the filtered column is explicitly
discussed in the design documentation of systems relying on it (including Parquet's own
per-row-group statistics, and dedicated clustering features like
[Sort Keys & Z-Ordering](sort-keys-and-z-ordering.md) that exist specifically to
maintain the clustering zone maps depend on).

Bloom filters' false-positive-rate-versus-size tradeoff is described in the original
Bloom filter paper (Bloom, "Space/Time Trade-offs in Hash Coding with Allowable
Errors," Communications of the ACM, 1970) and is a standard, explicit configuration
parameter in every modern system offering bloom-filter-based pruning (Parquet's bloom
filter support, Cassandra's SSTable bloom filters, and others), each requiring the
operator to size the filter based on an expected number of distinct values, with
documented guidance that under-sizing degrades effectiveness as actual value counts
exceed the planned capacity.

## Mitigations

### Sizing bloom filters for actual, not initial, cardinality

**What it is:** Size bloom filters based on the expected mature cardinality of the
indexed column, with margin for growth, rather than the cardinality present at initial
filter creation.

**Cost:** Larger filters consume more storage and maintenance cost than a filter sized
minimally for current data.

**How it backfires:** A filter sized generously for anticipated growth that never
materializes wastes storage indefinitely; one sized for a growth estimate that's
exceeded still degrades — there's no setting that's simultaneously optimal for unknown
future growth.

### Maintaining write-order clustering for zone-map-dependent columns

**What it is:** Ensure data is written (or periodically re-clustered) in an order that
correlates with the columns zone map pruning is expected to help, rather than allowing
arbitrary write order to defeat min/max range effectiveness. See
[Sort Keys & Z-Ordering](sort-keys-and-z-ordering.md).

**Cost:** Maintaining clustering requires either sorted writes (constraining ingestion
order) or periodic re-clustering (an additional maintenance operation, similar in kind
to compaction).

**How it backfires:** Clustering optimized for one column's pruning effectiveness can
degrade pruning for a different column that isn't correlated with the chosen
clustering order — clustering by one dimension is, in general, a tradeoff against
every other dimension.

### Monitoring pruning effectiveness directly

**What it is:** Track the actual fraction of chunks or files pruned by these
structures for representative queries, as an operational metric, rather than assuming
pruning remains effective indefinitely once configured.

**Cost:** Requires query-execution instrumentation capable of reporting pruning
statistics, which isn't universally exposed by default.

**How it backfires:** None specific — the absence of this monitoring is the failure
mode itself, since pruning degradation is otherwise discovered only as an unexplained
general slowdown.

## Interactions

- [Predicate & Projection Pushdown](../sql-execution/predicate-and-projection-pushdown.md) —
  the general optimization these structures enable at the physical storage layer.
- [Sort Keys & Z-Ordering](sort-keys-and-z-ordering.md) — the mechanism for maintaining
  the data clustering zone map pruning depends on.
- [Compaction Strategies](../storage/compaction-strategies.md) — compaction is often
  the point at which zone map statistics and bloom filters are recomputed, tying their
  freshness to compaction cadence.

## References

- Bloom, B. H. *Space/Time Trade-offs in Hash Coding with Allowable Errors*.
  Communications of the ACM, 1970. The original Bloom filter design and its
  false-positive-rate tradeoff.
- Apache Parquet Documentation. *Bloom Filters* and *Column Chunk Statistics*.
  Practical configuration reference for both pruning mechanisms in a widely used
  columnar format.
- Moerkotte, G. *Small Materialized Aggregates: A Light Weight Index Structure for Data
  Warehousing*. VLDB 1998. Foundational treatment of zone-map-style min/max pruning
  structures.
