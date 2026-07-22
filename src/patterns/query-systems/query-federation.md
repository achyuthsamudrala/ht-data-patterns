# Query Federation Across Engines

> **One-liner:** Federating a query across multiple storage or execution engines means the slowest, least-optimizable leg sets the floor for the whole query.

## Symptom

- A federated query joining data from two systems (e.g., a data lake and an operational
  database) runs far slower than either system would take to answer an equivalent
  query against its own data alone.
- Pushdown optimizations that work well for queries entirely within one engine (see
  [Predicate & Projection Pushdown](../sql-execution/predicate-and-projection-pushdown.md))
  silently don't apply across the federation boundary, forcing one side to pull far
  more data than a filter would suggest is necessary.
- A federated query's execution plan shows one connector or data source responsible for
  the overwhelming majority of total query time, while the others complete quickly.
- Adding a new federated data source to an existing query degrades overall query
  latency by more than that source's own query cost alone would explain.

## Mechanism

Query federation lets a single query span multiple underlying storage or execution
engines — joining a table in a data lake against a table in an operational database, or
combining results from two different analytical systems — without requiring the data
to first be physically consolidated into one system. This is valuable for avoiding
duplicative ETL pipelines purely to enable a single cross-system query, but it comes
with a structural cost: the federating query engine can only optimize what it controls
directly, and each underlying source's own capabilities (or lack thereof) become a
hard constraint on what the federated query as a whole can achieve.

The most consequential limitation is pushdown: within a single engine, filters and
projections can be pushed all the way down to the storage layer (see
[Predicate & Projection Pushdown](../sql-execution/predicate-and-projection-pushdown.md)).
Across a federation boundary, pushdown is only possible to the extent the federating
engine's connector for that specific source can translate the filter into that
source's native query language and the source can execute it efficiently — a
source with a weak or generic connector (or one that doesn't support certain predicate
types) forces the federating engine to pull a much larger result set across the
boundary and apply the filter locally, defeating much of the pushdown benefit that
would apply to a query running entirely within that source.

This produces the "slowest leg sets the floor" dynamic directly: a federated query
executes, at minimum, as slow as its slowest, least-optimizable leg, because the
federating engine has to wait for every source's contribution before it can complete
a join or aggregation spanning them — there's no way for a fast source's result to
compensate for a slow source's, since the query fundamentally needs both. Unlike a
join within one engine, where the planner has full visibility and control over both
sides' execution (see [Join Ordering](../sql-execution/join-ordering.md)), a federated
join's cost model has a genuine, unavoidable blind spot for whatever's happening inside
each underlying source's own execution.

## Real-world sightings

Presto/Trino's connector architecture, and its documentation on connector-specific
pushdown capabilities, explicitly describes pushdown support (predicate pushdown,
aggregation pushdown, limit pushdown) as varying by connector — some connectors support
extensive pushdown to their underlying source, others support minimal or none — and
this variability is a first-class, documented consideration when designing federated
queries spanning connectors with different capabilities.

The general federated query performance problem — that cross-system joins are bounded
by the weakest participating system's query capability — is a long-standing concern in
distributed database and data integration literature, predating any specific modern
implementation, and remains the central design challenge motivating ongoing connector
and pushdown capability development in federation-focused query engines.

## Mitigations

### Verifying connector pushdown capability before relying on federation for performance-sensitive queries

**What it is:** Check which pushdown optimizations a specific connector actually
supports for the sources involved in a federated query, rather than assuming
federation performs comparably to a single-engine query.

**Cost:** Requires connector-specific knowledge that isn't always obvious from a
federated query's SQL text alone.

**How it backfires:** Connector capabilities evolve over engine version upgrades; a
connector's pushdown support verified once can improve or regress with a version
change, without an obvious signal that the previously-verified assumption needs
re-checking.

### Pre-materializing slow-source data for repeated federated queries

**What it is:** For federated queries run repeatedly against a source with weak
pushdown support, periodically materialize a filtered or aggregated extract of that
source's relevant data into the federating engine's own fast storage, rather than
re-querying the slow source live every time.

**Cost:** Reintroduces the staleness and pipeline-maintenance overhead federation was
meant to avoid, at least for the materialized subset.

**How it backfires:** A materialization schedule tuned for the query pattern at setup
time becomes stale if that pattern shifts (a new filter dimension needed that wasn't
part of the original extract), and the staleness of the materialized copy is exactly
the read-replica-style staleness risk described in
[Read Replicas & Staleness](../serving/read-replicas-and-staleness.md).

### Restructuring queries to minimize cross-boundary data movement

**What it is:** Design federated queries to filter and aggregate as much as possible
on each individual source's native side (using whatever pushdown that source's
connector does support) before combining results across the federation boundary.

**Cost:** Requires understanding each connector's specific pushdown capabilities and
writing queries deliberately to exploit them, rather than writing a naive query and
trusting the federating engine to optimize it fully.

**How it backfires:** Manually restructured queries tuned for one connector's current
pushdown capability can become unnecessarily convoluted if that capability improves
later, trading present-day performance for reduced query readability that outlives its
justification.

## Interactions

- [Predicate & Projection Pushdown](../sql-execution/predicate-and-projection-pushdown.md) —
  the optimization whose cross-boundary limitation is the central mechanism of this
  pattern.
- [Join Ordering](../sql-execution/join-ordering.md) — federated joins have less
  planner visibility and control than single-engine joins, limiting how well join order
  can be optimized across the federation boundary.
- [Distributed Query Coordination](distributed-query-coordination.md) — the
  coordinator has to manage federated query state across heterogeneous sources, adding
  to its coordination burden beyond a single-engine query.

## References

- Presto/Trino Documentation. *Connectors* and *Pushdown*. Describes per-connector
  pushdown capability variability for federated queries.
- Sethi, R. et al. (Facebook). *Presto: SQL on Everything*. ICDE 2019. Discusses the
  federation architecture and its connector-dependent optimization boundaries.
- Halevy, A. Y. *Answering Queries Using Views: A Survey*. VLDB Journal, 2001.
  Foundational treatment of the broader data integration and federated query
  optimization problem.
