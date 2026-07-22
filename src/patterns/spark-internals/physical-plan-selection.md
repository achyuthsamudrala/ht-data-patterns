# Physical Plan Selection

> **One-liner:** The planner chooses concrete algorithms (join strategy, aggregation strategy) from the logical plan, using estimates that can be stale.

## Symptom

- The same logical query produces different physical plans on different days, with no
  code change — only underlying table statistics changed.
- A physical plan chosen at compile time looks reasonable given the estimated sizes in
  `explain()` output, but those estimated sizes are wildly different from the actual
  runtime sizes shown in the execution UI.
- Forcing a specific physical strategy via a hint fixes a slow query, but the same hint
  applied to a structurally similar query makes it slower.
- A recently added `ANALYZE TABLE` (or equivalent statistics refresh) job changes
  several unrelated queries' plans simultaneously.

## Mechanism

Where [Catalyst's logical optimization](catalyst-optimizer.md) rewrites *what* a query
computes into an equivalent, simpler form, physical plan selection decides *how* to
compute it: which join algorithm ([Broadcast vs. Shuffle Join](../joins-and-shuffle/broadcast-vs-shuffle-join.md),
[Sort-Merge vs. Shuffle-Hash Join](../joins-and-shuffle/sort-merge-vs-shuffle-hash-join.md)),
which aggregation strategy (hash-based vs. sort-based), and how many partitions to use
at each shuffle boundary.

This selection is cost-based: the planner estimates the cost of each candidate physical
plan using table and column statistics, and picks the cheapest estimate. The entire
selection is therefore only as reliable as those estimates, computed at compile time,
before any of the query's own operators have actually run. Estimates compound
multiplicatively through a plan — an error in a base table's row count estimate
propagates through every filter, join, and aggregation built on top of it, and each
additional operator can amplify rather than average out the error (see
[Statistics & Cardinality Estimation](../sql-execution/statistics-and-cardinality-estimation.md)).

This is fundamentally a static decision problem solved with (necessarily) incomplete
information: the true cost of a physical plan depends on runtime data characteristics
that aren't fully known until the query actually executes. Traditional query optimizers
accept this as an inherent limitation of compile-time planning; the more recent
alternative is not better estimation, but deferred decision-making — re-planning after
partial execution, once actual data characteristics are observable. That is precisely
what [Adaptive Query Execution (AQE)](adaptive-query-execution.md) does for a subset of
physical plan decisions.

## Real-world sightings

The general problem of cost-based physical plan selection being fragile to
cardinality-estimation error is a long-standing, well-documented topic in the database
research literature — Leis et al.'s "How Good Are Query Optimizers, Really?" (VLDB 2015)
is a widely cited empirical study showing that cardinality estimation errors, not cost
model inaccuracy, are the dominant cause of bad physical plan choices across several
production-grade optimizers, and that these errors grow exponentially with query
complexity (number of joins).

In Spark specifically, Databricks' AQE documentation and engineering posts describe the
motivation for adaptive re-planning directly in these terms: compile-time statistics for
a base table don't account for the selectivity of filters or joins applied before a
given operator runs, so the physical plan chosen for a deeply nested query is
frequently based on estimates several steps removed from the data that operator will
actually see.

## Mitigations

### Keeping table statistics current

**What it is:** Regularly run statistics-refresh jobs (`ANALYZE TABLE`, or the
equivalent for the engine in use) so cost-based decisions are working from
representative, current data.

**Cost:** Statistics collection itself scans data and takes time and compute,
especially for detailed (histogram-level) statistics on large tables.

**How it backfires:** Statistics refreshed on a fixed schedule can still be stale
relative to intra-day data changes, and a plan chosen from stale-but-present statistics
looks no different, structurally, from one chosen from accurate statistics — there's no
signal in the plan itself that the inputs were wrong.

### Runtime re-planning (AQE)

**What it is:** Defer some physical plan decisions until after an initial shuffle
stage's actual output size is known, replacing a compile-time estimate with a
measurement. See [Adaptive Query Execution (AQE)](adaptive-query-execution.md).

**Cost:** Only corrects decisions made *after* a shuffle boundary; decisions baked into
the plan before the first shuffle (e.g., initial scan strategy) aren't revisited.

**How it backfires:** Re-planning has its own overhead (materializing intermediate
results, coordination) and a query with very few shuffle boundaries gets fewer
opportunities for correction than one with many.

### Explicit hints for known-volatile queries

**What it is:** Pin a physical strategy via a query hint for cases where automatic
selection is known to be unreliable (highly seasonal data, rapidly growing tables).

**Cost:** A pinned hint doesn't benefit from either improved statistics or AQE's runtime
correction — it's deliberately static.

**How it backfires:** The volatility that motivated the hint in the first place doesn't
stop; a hint tuned for one season or one data-growth regime becomes wrong in the next,
without any warning that it's now stale.

## Interactions

- [Catalyst Optimizer & Logical Plans](catalyst-optimizer.md) — physical plan selection
  operates on the logical plan Catalyst produces; errors compound across both phases.
- [Statistics & Cardinality Estimation](../sql-execution/statistics-and-cardinality-estimation.md) —
  the direct input whose quality determines physical plan selection quality.
- [Adaptive Query Execution (AQE)](adaptive-query-execution.md) — the primary mechanism
  for correcting physical plan decisions after compile-time estimates prove wrong.

## References

- Leis, V. et al. *How Good Are Query Optimizers, Really?*. VLDB 2015. Empirical study
  establishing cardinality estimation error as the dominant cause of bad physical plans.
- Armbrust, M. et al. *Spark SQL: Relational Data Processing in Spark*. SIGMOD 2015.
  Describes the cost-based physical planning phase following logical optimization.
- Databricks Engineering Blog. *Adaptive Query Execution: Speeding Up Spark SQL at
  Runtime*. Motivates runtime re-planning as a response to compile-time estimation
  limits.
