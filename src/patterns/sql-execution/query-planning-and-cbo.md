# Query Planning & Cost-Based Optimization

> **One-liner:** The planner picks a physical execution strategy by estimating cost from statistics — and is only as good as those statistics.

## Symptom

- A query's plan changes after an unrelated `ANALYZE`/statistics-refresh job runs,
  with no change to the query itself.
- Two queries that are logically identical but textually different (different join
  order in the SQL, equivalent subquery restructuring) produce different plans and
  different runtimes.
- A query that was fast for months degrades gradually as a table grows, without any
  single identifiable change — the plan simply becomes progressively less appropriate.
- Forcing a specific join order or scan method via a hint improves one query but the
  same hint, copy-pasted into a similar query, makes it worse.

## Mechanism

Cost-based optimization (CBO) is the phase of query planning that chooses among
multiple logically equivalent plans by estimating each candidate's execution cost — I/O,
CPU, memory — and picking the cheapest estimate. This differs from purely rule-based
optimization (see [Catalyst Optimizer & Logical Plans](../spark-internals/catalyst-optimizer.md)),
which applies transformations known to be safe regardless of data characteristics; CBO's
decisions genuinely depend on the data, and are only as trustworthy as the statistics
describing it.

The core inputs to a cost estimate are cardinalities — how many rows will flow through
each operator — and those cardinalities are themselves estimates, derived from table
and column statistics (row counts, distinct value counts, histograms) that are computed
in advance, not observed live. A cost model can be arithmetically correct and still
produce a bad plan if the cardinality estimates it's given are wrong, because "cheapest
estimated plan" is only meaningful relative to estimates that reflect reality.

This is why CBO decisions are fragile in a specific, well-studied way: cardinality
estimation errors compound multiplicatively as a plan grows deeper (see
[Statistics & Cardinality Estimation](statistics-and-cardinality-estimation.md)), so a
plan with many joins is far more exposed to bad CBO decisions than a simple single-table
scan, even though both rely on the same underlying statistics infrastructure.

## Real-world sightings

Leis et al.'s "How Good Are Query Optimizers, Really?" (VLDB 2015) is the widely cited
empirical benchmark on this exact question: running the same query workload (the Join
Order Benchmark) across multiple production-grade optimizers and directly measuring
cardinality estimation error against actual runtime cardinalities, the paper found that
estimation error — not cost-model inaccuracy — was the dominant driver of bad plan
choices, and that even sophisticated cost models produced good plans when given
accurate cardinalities and bad plans when not, regardless of the cost model's own
sophistication.

This finding is broadly consistent with practitioner experience across Spark, Presto/
Trino, and traditional RDBMS query planners, and is the direct motivation for
[Adaptive Query Execution (AQE)](../spark-internals/adaptive-query-execution.md)-style
runtime re-planning in modern big-data engines: rather than trying to make compile-time
estimates arbitrarily more accurate, defer some decisions until actual data can be
measured.

## Mitigations

### Maintaining fresh, sufficiently granular statistics

**What it is:** Regularly refresh table and column statistics, including histograms
for columns with non-uniform distributions, not just row counts.

**Cost:** Statistics collection is itself a scan of the data (or a sample of it), and
histogram-level statistics cost more to compute and maintain than simple counts.

**How it backfires:** Statistics granularity that was sufficient when a column's
distribution was roughly uniform can become insufficient after the distribution shifts
(a new category dominates), and nothing signals that existing statistics no longer
represent the data well enough for CBO to reason about it accurately.

### Runtime re-planning instead of relying solely on compile-time CBO

**What it is:** Let the engine correct compile-time cost-based decisions using actual,
measured data characteristics at runtime. See
[Adaptive Query Execution (AQE)](../spark-internals/adaptive-query-execution.md).

**Cost:** Only corrects decisions at points where the engine has already paused to
materialize intermediate results — it isn't a substitute for good initial statistics on
the first stage of a plan.

**How it backfires:** Runtime re-planning has overhead of its own, and for a query
whose compile-time plan happens to already be close to optimal, that overhead is pure
cost with no offsetting benefit.

### Simplifying deeply nested queries

**What it is:** Restructure queries with many joins or nested subqueries into simpler,
more directly estimable forms where possible, reducing the number of compounding
estimation steps.

**Cost:** Can trade query readability or maintainability for estimation reliability,
and isn't always feasible for genuinely complex analytical questions.

**How it backfires:** A simplification that reduces estimation risk for the current
data distribution can reintroduce complexity if business requirements later demand the
nested structure back — this is a real tradeoff, not a strict improvement.

## Interactions

- [Statistics & Cardinality Estimation](statistics-and-cardinality-estimation.md) — the
  direct dependency this entire pattern rests on.
- [Join Ordering](join-ordering.md) — the highest-stakes CBO decision, since join order
  errors compound the most across a deep plan.
- [Physical Plan Selection](../spark-internals/physical-plan-selection.md) — the
  Spark-specific instance of cost-based physical strategy selection this page
  generalizes.

## References

- Leis, V. et al. *How Good Are Query Optimizers, Really?*. VLDB 2015. The definitive
  empirical study of cardinality estimation error's role in bad query plans.
- Selinger, P. G. et al. *Access Path Selection in a Relational Database Management
  System*. SIGMOD 1979. The original cost-based optimization design, still the
  conceptual basis for most modern optimizers.
- Ioannidis, Y. E. *The History of Histograms (abridged)*. VLDB 2003. Traces the
  evolution of the statistics infrastructure CBO depends on.
