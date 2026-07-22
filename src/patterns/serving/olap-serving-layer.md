# OLAP Serving Layer

> **One-liner:** Pre-aggregation, rollups, and materialized views trade storage and freshness for query-time latency in analytical serving.

## Symptom

- A dashboard querying raw event-level data directly takes seconds to load, while an
  equivalent dashboard backed by a pre-aggregated rollup returns in milliseconds.
- A pre-aggregated metric shown on a dashboard lags the true, current value by a
  noticeable and sometimes inconsistent amount, depending on when the underlying
  rollup job last ran.
- Adding a new dimension to a report requires waiting for a rollup or materialized view
  to be rebuilt or extended, rather than being immediately queryable.
- Storage for pre-aggregated rollup tables grows to a meaningful fraction of the raw
  data's size, especially for high-cardinality dimension combinations.

## Mechanism

Serving analytical queries directly against raw, granular data (every individual
event or transaction) at low latency is expensive: a dashboard query touching millions
or billions of raw rows to compute a simple aggregate pays the full scan cost every
time, regardless of how often the same or a similar aggregate was already computed
recently. Pre-aggregation addresses this by computing and materializing aggregates
ahead of query time — rollups (pre-computed sums/counts at a coarser grain, e.g., daily
totals instead of per-event rows) and materialized views (a stored, precomputed result
of a specific query or query shape) both trade compute-at-write-time for
latency-at-read-time.

This is a direct instance of [Result/Query Caching](result-and-query-caching.md)'s
general principle — moving work earlier so it doesn't have to be repeated at query
time — but applied structurally, ahead of any specific query, rather than reactively
after a query has run once. This means an OLAP serving layer's design has to
anticipate which aggregates and dimension combinations will actually be queried, since
a rollup built for one dimension combination provides no benefit for a differently
shaped query, and building rollups for every possible dimension combination is
combinatorially expensive — the classic cube-explosion problem in OLAP design, where
the number of possible aggregate combinations grows exponentially with the number of
dimensions.

The unavoidable cost of pre-aggregation is freshness: a rollup or materialized view is
only as current as its last refresh, and unlike caching a specific query result (which
can be invalidated precisely when its underlying data changes), a rollup covering a wide
range of underlying data typically refreshes on a schedule (hourly, nightly) rather
than reactively per-change, because reactively recomputing a wide aggregate on every
underlying write would defeat the purpose of pre-aggregating in the first place. This
produces the freshness lag visible in the symptom list — the tradeoff is deliberate,
but its magnitude (how stale is "acceptable") is a design decision that has to be made
explicit rather than left as an incidental side effect of whatever refresh schedule was
convenient to implement.

## Real-world sightings

The OLAP cube concept, and the storage-versus-latency tradeoff of materializing
aggregates ahead of query time, has deep roots in data warehousing literature and
remains the design basis for modern high-performance analytical serving engines
(Apache Druid, Apache Pinot, ClickHouse's materialized views) — these systems'
documentation consistently frames pre-aggregation and rollup as the primary mechanism
for achieving sub-second query latency over otherwise very large datasets, at the
explicit cost of either storage overhead or freshness lag depending on refresh
strategy.

Apache Druid's documentation on rollup explicitly discusses the storage/freshness
tradeoff and recommends choosing rollup granularity based on the actual query patterns
a dashboard needs to support, cautioning against over-aggressive rollup (losing detail
needed for drill-down queries) as much as under-aggressive rollup (missing the
performance benefit).

## Mitigations

### Designing rollup grain to match known query patterns

**What it is:** Choose pre-aggregation granularity (which dimensions and time
resolutions to materialize) based on the actual dashboards and reports that will query
the data, rather than aggregating to the finest or coarsest grain by default.

**Cost:** Requires knowing query patterns in advance, which may not be fully known for
new or evolving analytical use cases.

**How it backfires:** A rollup grain chosen for today's dashboards can silently fail to
support a new drill-down requirement that needs a finer grain than was materialized,
forcing either a fallback to slow raw-data queries or a rollup redesign.

### Explicit, monitored freshness SLAs for materialized data

**What it is:** Define and monitor an explicit freshness target for each rollup or
materialized view (e.g., "updated within 15 minutes of source data"), rather than
leaving refresh timing as an implementation detail.

**Cost:** Requires refresh-pipeline monitoring and alerting specifically for
freshness lag, in addition to whatever monitoring exists for the pipeline's own
success/failure.

**How it backfires:** A freshness SLA that's defined but not actually surfaced to
dashboard consumers can be silently violated (a refresh job failing or falling behind)
without anyone downstream realizing the data they're viewing is stale beyond the
intended bound.

### Layering pre-aggregation over raw data rather than replacing it

**What it is:** Retain access to raw, granular data alongside pre-aggregated rollups,
so queries needing detail beyond what's rolled up can still fall back to the raw layer.

**Cost:** Requires maintaining both a fast, aggregated path and a slower, granular
path, and query routing logic to choose between them appropriately.

**How it backfires:** If the fallback path isn't well-optimized (see
[Predicate & Projection Pushdown](../sql-execution/predicate-and-projection-pushdown.md)
and [Columnar Storage Formats](../sql-execution/columnar-storage-formats.md)), users
who need drill-down detail can experience a jarring latency cliff between the fast,
aggregated common case and the much slower detailed fallback.

## Interactions

- [Result/Query Caching](result-and-query-caching.md) — the reactive, per-query
  counterpart to this pattern's proactive, structural pre-aggregation.
- [Point Lookups vs. Analytical Scans](point-lookups-vs-analytical-scans.md) — OLAP
  serving layers are generally optimized for the analytical-scan side of that
  tradeoff, not point lookups.
- [Batch vs. Streaming Spectrum](../../foundations/batch-vs-streaming-spectrum.md) — a
  rollup's refresh schedule is a concrete instance of the general latency/freshness
  tradeoff described at the foundations level.

## References

- Apache Druid Documentation. *Rollup*. Describes rollup granularity design and its
  storage/freshness tradeoffs.
- Apache Pinot Documentation. *Star-Tree Index*. Describes a specific pre-aggregation
  indexing structure for low-latency OLAP serving.
- Gray, J. et al. *Data Cube: A Relational Aggregation Operator Generalizing Group-By,
  Cross-Tab, and Sub-Totals*. ICDE 1996. Foundational formalization of the OLAP cube
  and cube-explosion problem.
