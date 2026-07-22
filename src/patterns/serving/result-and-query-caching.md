# Result/Query Caching

> **One-liner:** Caching query results shifts the hard problem from computation to invalidation, and stale cache hits fail silently.

## Symptom

- A dashboard shows a value that doesn't match the underlying data after a recent
  update, and refreshing doesn't help because the stale value is being served from
  cache rather than recomputed.
- Cache hit rate is high and query latency looks excellent in aggregate, masking that a
  meaningful fraction of "fast" responses are actually stale.
- Two semantically identical queries with a trivial textual difference (whitespace,
  column order) miss the cache when a normalized version would have hit, silently
  losing the caching benefit.
- Invalidating a cache after a write causes a burst of expensive recomputation as many
  callers simultaneously recompute the same now-uncached query.

## Mechanism

Result caching stores the output of a previously executed query, keyed by some
representation of the query and its parameters, so that a subsequent identical (or
equivalent) request can be served from the cache instead of recomputed. This is
effective exactly to the degree that queries repeat and underlying data doesn't change
between repetitions — the harder problem isn't storing the result, it's knowing when a
cached result is no longer valid.

**Invalidation** is the crux of this pattern, and it comes in two flavors, each with a
distinct failure mode. Time-based invalidation (a fixed TTL) is simple but disconnected
from actual data change: it can serve overly stale data if the TTL is too generous, or
forfeit caching benefit unnecessarily if the TTL is too conservative relative to actual
data update frequency. Event-based invalidation (explicitly invalidating cached
results when the underlying data they depend on changes) is more precise but requires
tracking, for every cached result, exactly which underlying data it depends on — a
requirement that's straightforward for a simple single-table cache key and
substantially harder for a cached result derived from a join or aggregation over
several tables, each of which can independently invalidate the cached result.

This connects directly to [Consistency Models for Distributed Data](../../foundations/consistency-models-for-distributed-data.md):
a stale cache hit is, structurally, the same
read-your-writes violation described for
[Read Replicas & Staleness](read-replicas-and-staleness.md) — a caller that just wrote
new data has every reason to expect a subsequent query reflects it, and a cache
serving a pre-write result violates that expectation just as a lagging read replica
does, just via a different mechanism (explicit caching rather than replication lag).

**Query key normalization** is a secondary but practically significant concern:
caching effectiveness depends on recognizing that two syntactically different queries
are semantically equivalent (same result, different text), and a naive
text-based cache key misses this, treating trivially different queries as entirely
distinct cache entries — silently losing hit rate the cache was meant to provide.

**Cache stampede on invalidation** is the final compounding risk: when a widely-used
cached result is invalidated, every caller that would have hit the cache instead misses
simultaneously and recomputes the same expensive query at once, a specific instance of
the general coalescing problem any shared-cache system faces under a synchronized miss.

## Real-world sightings

Materialized view and query-result caching invalidation strategies are a long-standing,
extensively studied topic in database systems research and are explicitly addressed in
most modern analytical engines' documentation (Presto/Trino's query result caching,
various data warehouse vendors' result-cache features), generally offering both
TTL-based and dependency-tracking-based invalidation options and explicitly discussing
the tradeoffs between them.

Query normalization for cache key matching is a documented feature and design
consideration across query engines and caching layers supporting result caching,
generally implemented via query plan canonicalization (comparing normalized logical
plans rather than raw query text) specifically to catch semantically equivalent but
textually different queries.

## Mitigations

### Dependency-tracked invalidation over pure TTL

**What it is:** Track which underlying tables or partitions a cached result depends on,
and invalidate it explicitly when that underlying data changes, rather than relying
solely on a fixed expiration time.

**Cost:** Requires maintaining dependency metadata for every cached result, which adds
bookkeeping overhead proportional to query complexity.

**How it backfires:** For queries with broad or hard-to-precisely-determine
dependencies (a query touching many tables, or one whose dependencies change based on
runtime conditions), dependency tracking can either over-invalidate (losing cache
benefit unnecessarily) or under-invalidate (missing a genuine staleness case) if the
dependency analysis isn't conservative and precise.

### Cache key normalization via plan canonicalization

**What it is:** Key cached results by a normalized representation of the query's
logical plan rather than raw query text, so semantically equivalent queries hit the
same cache entry regardless of surface syntax differences.

**Cost:** Requires the caching layer to have access to and normalize the query
planner's logical plan, which is more implementation work than a simple text-based key.

**How it backfires:** Overly aggressive normalization can incorrectly treat two
queries as equivalent when a subtle semantic difference (different null handling, a
different implicit type coercion) actually changes the result, producing a correctness
bug rather than just a caching inefficiency.

### Request coalescing on cache miss

**What it is:** When a cache entry is invalidated and multiple concurrent callers miss
simultaneously, coalesce them into a single recomputation whose result is then shared
across all waiting callers, rather than letting each caller recompute independently.

**Cost:** Requires coordination logic (a lock or a shared in-flight-request tracking
mechanism) at the caching layer.

**How it backfires:** Coalescing adds latency for callers waiting on someone else's
in-flight recomputation rather than starting their own, which can be worse than
independent recomputation for a caller with an unusually tight latency budget, even
though it's better for the system in aggregate.

## Interactions

- [Read Replicas & Staleness](read-replicas-and-staleness.md) — the same
  read-your-writes staleness problem, produced by a different mechanism (explicit
  caching rather than replication lag).
- [OLAP Serving Layer](olap-serving-layer.md) — pre-aggregation is the proactive,
  structural counterpart to this pattern's reactive, per-query caching.
- [Consistency Models for Distributed Data](../../foundations/consistency-models-for-distributed-data.md) —
  the foundational framing for why any cached-versus-source-of-truth divergence is a
  consistency problem, not merely a performance one.

## References

- Presto/Trino Documentation. *Query Result Caching*. Describes practical
  TTL-and-dependency-based invalidation options for a widely used distributed query
  engine.
- Gupta, A. and Mumick, I. S. *Maintenance of Materialized Views: Problems, Techniques,
  and Applications*. IEEE Data Engineering Bulletin, 1995. Foundational treatment of
  materialized view invalidation strategies.
- Various database vendor documentation on query result caching (e.g., Snowflake
  Result Caching, BigQuery Cached Results). Describes production-grade result caching
  and invalidation semantics.
