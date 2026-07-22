# Result/Plan Caching

> **One-liner:** Caching query plans avoids re-planning cost; caching results avoids re-execution cost — each has a different invalidation problem.

## Symptom

- Planning time for a recurring, structurally identical query remains high on every
  execution, even though the query's plan should be reusable across runs.
- A query result served from cache is stale relative to underlying data changes, in a
  system that also separately (and correctly) caches query plans without issue — the
  two caches have different, non-overlapping failure modes.
- Invalidating a cached plan after a schema change misses some cached entries,
  producing errors or silently incorrect results for queries whose cached plan
  references since-changed schema.
- Plan cache hit rate is unexpectedly low for queries that are logically identical but
  differ in literal parameter values, when a parameterized plan cache should have
  matched them.

## Mechanism

Plan caching and result caching address two distinct costs and have two distinct
invalidation problems, and conflating them is a common source of confusion when
reasoning about a caching layer's behavior.

**Plan caching** stores the compiled physical execution plan for a query shape, so a
subsequent execution of the same (or a parametrically similar) query skips the
planning phase — [Query Planning & Cost-Based Optimization](../sql-execution/query-planning-and-cbo.md)
and [Join Ordering](../sql-execution/join-ordering.md)'s work — and proceeds directly to
execution. This is valuable because planning cost, especially for complex queries, can
be a significant fraction of total query latency (see
[Distributed Query Coordination](distributed-query-coordination.md)). Plan cache
invalidation is primarily a *schema* and *statistics* concern: a cached plan becomes
invalid if the underlying table schema changes (a column is dropped or its type
changes) or, more subtly, if statistics have changed enough that the previously-chosen
plan is no longer the best available one — a plan cache that never re-validates
against current statistics can serve a stale, sub-optimal (though still logically
correct) plan indefinitely.

**Result caching** stores the actual output of a query, skipping execution entirely on
a cache hit — this is [Result/Query Caching](../serving/result-and-query-caching.md)'s
subject in a serving context, and the same principles apply here at the query-system
level. Result cache invalidation is a *data* concern: a cached result becomes stale the
moment any data it depends on changes, regardless of whether the plan used to compute
it is still valid.

These are genuinely independent axes: a plan can remain valid (same schema, same
reasonable cost estimate) while its cached result is stale (underlying data changed),
and conversely a cached result can still be correct even after a schema change that
would invalidate a cached plan, if the schema change didn't affect the specific data the
result depends on. A caching layer that handles one invalidation concern correctly but
not the other will exhibit exactly the kind of split symptom described above — plans
cached and reused correctly while results serve stale data, or vice versa.

**Parameterized plan matching** adds a further wrinkle: for a plan cache to benefit
queries with the same shape but different literal parameter values (a filter on a
different specific customer ID each time), the cache has to recognize the shape as
equivalent independent of the literal values — this requires the query engine to
support parameterized or "prepared statement"-style plan caching rather than caching
by exact query text, and queries submitted with literals inlined directly (rather than
as bind parameters) will miss a parameterized plan cache even when logically eligible.

## Real-world sightings

Most production relational database systems' query plan caching (prepared statement
caching, plan cache invalidation on DDL) is extensively documented, generally
describing automatic plan cache invalidation triggered by schema changes and, in more
sophisticated implementations, by statistics changes exceeding some staleness
threshold — an explicit acknowledgment that plan cache validity depends on more than
just schema stability.

Presto/Trino's and other distributed query engines' documentation on query result
caching describes it as a distinct, separately-configured feature from plan-level
caching, generally requiring explicit dependency tracking (which tables a cached result
depends on) for correct invalidation — reflecting the same split described above
between plan validity and result validity as genuinely separate concerns requiring
separate invalidation logic.

## Mitigations

### Separating plan cache invalidation from result cache invalidation logic

**What it is:** Implement and reason about plan cache invalidation (schema/statistics-
driven) and result cache invalidation (data-change-driven) as genuinely independent
mechanisms, rather than assuming one implies correctness for the other.

**Cost:** Requires maintaining two distinct invalidation tracking systems rather than
a single, simpler one.

**How it backfires:** None specific to correctly separating these concerns — the risk
this mitigation addresses is precisely the confusion that arises from treating them as
a single caching problem.

### Using parameterized queries to maximize plan cache hit rate

**What it is:** Submit queries using bind parameters (prepared statements) rather than
inlined literals, so structurally identical queries with different parameter values
share the same cached plan.

**Cost:** Requires application code and query-generation tooling to consistently use
parameterized query construction rather than string-interpolated literals.

**How it backfires:** Some query shapes genuinely benefit from literal-value-specific
planning (a highly skewed column where the specific literal value affects the optimal
plan choice) — over-aggressively parameterizing every query can force a
one-size-fits-all plan onto queries that would have benefited from per-value planning.

### Explicit staleness thresholds for statistics-driven plan re-validation

**What it is:** Re-validate (and potentially re-plan) a cached plan if the underlying
table's statistics have changed by more than a configured threshold since the plan was
cached, rather than treating a cached plan as valid indefinitely absent a schema
change.

**Cost:** Requires tracking statistics staleness per cached plan, adding bookkeeping
overhead to the plan cache.

**How it backfires:** A threshold set too conservatively re-validates plans more often
than necessary, forfeiting some of the planning-cost savings the cache exists to
provide; set too loosely, it allows a plan cache to serve an increasingly sub-optimal
plan for longer than intended.

## Interactions

- [Query Planning & Cost-Based Optimization](../sql-execution/query-planning-and-cbo.md) —
  the planning work this pattern's plan-caching half exists to avoid repeating.
- [Result/Query Caching](../serving/result-and-query-caching.md) — the serving-layer
  instance of this pattern's result-caching half, sharing the same core invalidation
  challenge.
- [Distributed Query Coordination](distributed-query-coordination.md) — the
  coordinator is typically where both plan and result caches live and are consulted.

## References

- Presto/Trino Documentation. *Query Result Caching*. Describes result caching as
  distinct from plan-level caching, with its own dependency-tracking invalidation.
- Selinger, P. G. et al. *Access Path Selection in a Relational Database Management
  System*. SIGMOD 1979. Discusses early plan caching (for repeated execution of
  compiled query plans) and its relationship to statistics-driven re-optimization.
- Gupta, A. and Mumick, I. S. *Maintenance of Materialized Views: Problems, Techniques,
  and Applications*. IEEE Data Engineering Bulletin, 1995. Foundational treatment of
  result/view invalidation, directly applicable to result cache invalidation logic.
