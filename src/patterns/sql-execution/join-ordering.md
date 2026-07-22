# Join Ordering

> **One-liner:** The order in which a multi-way join is executed changes intermediate result sizes by orders of magnitude.

## Symptom

- A query joining four or more tables runs far slower than expected, and the execution
  UI shows one intermediate join stage producing a vastly larger result than either its
  final output or its two inputs would suggest.
- Reordering the tables in a `FROM`/`JOIN` clause — with no other change — changes the
  query's runtime substantially, even though SQL join order in the text shouldn't
  matter for an optimizing planner.
- A join plan looks reasonable for each pairwise join individually, but the cumulative
  intermediate size across the whole plan is far larger than the final result set.
- A query that performs well in isolation performs poorly as part of a larger view or
  CTE chain, where the planner has less freedom (or less accurate information) to
  reorder joins across the boundary.

## Mechanism

For a join of more than two tables, there are many valid orders in which the pairwise
joins can be executed, and — unlike commutative arithmetic — the order matters
enormously for cost, because intermediate result sizes depend on which tables are
joined first. Joining two large, weakly-filtered tables early produces a large
intermediate result that then has to be joined again against everything else; joining
a highly selective, small intermediate result against subsequent tables keeps every
downstream operator working with less data.

The number of possible join orders grows factorially with the number of tables, which
makes exhaustive search infeasible beyond a small number of joins — real query
optimizers use dynamic programming (for tractable sizes) or heuristic/greedy search
(for larger joins) to explore a subset of the space, guided by cost estimates derived
from cardinality estimates (see
[Statistics & Cardinality Estimation](statistics-and-cardinality-estimation.md)).

This is exactly where join ordering becomes fragile: the optimizer's search is only as
good as the cardinality estimates guiding it. An underestimated intermediate result size
can lead the optimizer to choose a join order that looks cheap on paper but produces a
much larger actual intermediate result — and because estimation error compounds
multiplicatively across each join in the order, a four- or five-way join is
substantially more exposed to a single bad early estimate than a two-way join, since
that error propagates through every subsequent join's own estimate.

## Real-world sightings

The Join Order Benchmark, introduced in Leis et al.'s "How Good Are Query Optimizers,
Really?" (VLDB 2015), was specifically designed to stress-test join ordering decisions
using a real-world dataset (IMDB) with realistic, correlated join predicates — the
kind of correlation that defeats standard independence assumptions in cardinality
estimation. The paper found that even sophisticated cost models chose badly-ordered
joins when fed inaccurate cardinality estimates, and that estimation error grew
substantially worse as the number of joins in a query increased, directly supporting
the multiplicative-compounding mechanism described above.

Query engines built for interactive, ad-hoc analytics over large joins — Presto/Trino
and similar systems — document join reordering (including cost-based join
reordering informed by table statistics) as a core optimizer capability precisely
because these systems are commonly used for exploratory queries with many joins,
where manual join ordering by the query author isn't a reliable substitute for
automatic, statistics-informed reordering.

## Mitigations

### Enabling cost-based join reordering

**What it is:** Let the optimizer reorder joins automatically based on cost estimates,
rather than executing joins in the literal order written in the query.

**Cost:** Depends entirely on the quality of underlying statistics — see
[Statistics & Cardinality Estimation](statistics-and-cardinality-estimation.md) — and
adds planning-time overhead for exploring the join-order search space.

**How it backfires:** For queries with many joins and poor statistics, automatic
reordering can choose a *worse* order than a naively literal one, if the estimates
guiding the search are themselves badly wrong — there's no guarantee that
automatic beats manual when the inputs to automatic are unreliable.

### Manually restructuring join order for known-selective filters

**What it is:** Explicitly write queries so highly selective joins or filters happen
early, reducing intermediate result size before later, less selective joins.

**Cost:** Requires the query author to understand data distribution and selectivity,
knowledge that the optimizer is in principle supposed to have and use automatically.

**How it backfires:** A manually-ordered query encodes an assumption about data
distribution at the time it was written; as data evolves, that assumption can silently
become wrong, and a manually-ordered query doesn't get the benefit of the optimizer
reconsidering as automatic reordering would.

### Runtime-informed re-planning across shuffle boundaries

**What it is:** Where available, let the engine adjust downstream join strategy or
partition sizing based on actual, measured intermediate result sizes rather than
compile-time estimates alone. See
[Adaptive Query Execution (AQE)](../spark-internals/adaptive-query-execution.md).

**Cost:** This corrects strategy (e.g., broadcast vs. shuffle) and partition sizing at
measured boundaries, but does not retroactively re-order joins that already executed
in a suboptimal sequence before the measurement point.

**How it backfires:** Provides no benefit for the *first* join in a sequence, since
there's no prior measurement to correct against — the highest-leverage join order
decision (which join happens first) is exactly the one this mitigation can't touch.

## Interactions

- [Statistics & Cardinality Estimation](statistics-and-cardinality-estimation.md) — the
  direct input whose accuracy determines whether cost-based join reordering helps or
  hurts.
- [Query Planning & Cost-Based Optimization](query-planning-and-cbo.md) — join
  ordering is the highest-stakes instance of the general CBO fragility that page
  describes, since it compounds across the most operators.
- [Broadcast vs. Shuffle Join](../joins-and-shuffle/broadcast-vs-shuffle-join.md) — join
  order and join strategy selection interact: a reordered join can change which side of
  a given pairwise join is small enough to broadcast.

## References

- Leis, V. et al. *How Good Are Query Optimizers, Really?*. VLDB 2015. Introduces the
  Join Order Benchmark and establishes the compounding-error mechanism described above.
- Selinger, P. G. et al. *Access Path Selection in a Relational Database Management
  System*. SIGMOD 1979. The original dynamic-programming approach to join order
  enumeration.
- Ioannidis, Y. E. and Kang, Y. C. *Randomized Algorithms for Optimizing Large Join
  Queries*. SIGMOD 1990. Heuristic search approaches for join orders too large for
  exhaustive enumeration.
