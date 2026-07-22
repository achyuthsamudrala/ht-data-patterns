# Statistics & Cardinality Estimation

> **One-liner:** Cardinality estimates compound multiplicatively across a plan; a single bad estimate can send join ordering off the rails.

## Symptom

- A query's estimated row counts in `explain()` output diverge from actual row counts
  shown in the execution UI by an order of magnitude or more, especially for deeper
  operators in the plan.
- A join on two correlated columns (e.g., city and postal code, or product category and
  brand) produces a wildly inaccurate cardinality estimate, while a join on independent
  columns estimates accurately.
- Query plans degrade gradually over weeks as data grows, without any single
  identifiable trigger — statistics simply became progressively less representative.
- A newly added column with a skewed distribution (a few very common values, many rare
  ones) produces bad filter selectivity estimates using only basic count statistics.

## Mechanism

A cardinality estimate answers "how many rows will this operator produce," and every
downstream decision — join order, join strategy, partition count — depends on these
estimates being reasonably accurate. The basic building blocks are table row counts and
per-column statistics: distinct value counts, min/max, and (where maintained) histograms
approximating a column's value distribution.

Two structural problems make cardinality estimation unreliable in ways that are
difficult to fix simply by "collecting more statistics." First, **the independence
assumption**: standard cardinality estimation for multi-column filters and joins
typically assumes column values are statistically independent, multiplying individual
column selectivities together. Real-world columns are frequently correlated — city and
postal code, product category and price range — and multiplying independent
selectivities for correlated columns systematically produces wrong estimates, often by
a large margin, because the joint selectivity of correlated columns is not the product
of their marginal selectivities.

Second, **compounding across plan depth**: even a modest per-operator estimation error
doesn't stay modest as it propagates. If each join in a five-way join sequence has its
output cardinality estimated with some error, and each downstream join's own cardinality
estimate is computed using the (already erroneous) upstream estimate as an input, the
error doesn't average out — it compounds, often multiplicatively, so a plan's final,
deepest operators can be based on estimates that are wrong by orders of magnitude even
if every individual estimation step was only moderately off.

Histograms improve on simple min/max statistics by approximating the actual shape of a
column's distribution, which helps with skewed single-column selectivity but does
nothing for the correlation problem above — a histogram on column A and a separate
histogram on column B still cannot capture how A and B vary together, which is exactly
the information needed for an accurate joint-filter or join estimate.

## Real-world sightings

Leis et al.'s "How Good Are Query Optimizers, Really?" (VLDB 2015) directly measured
this: comparing cardinality estimates against ground-truth actual cardinalities across
the Join Order Benchmark's real-world (correlated) join predicates, the paper found
that estimation errors grew, in the worst cases, by orders of magnitude as query depth
(number of joins) increased — empirically confirming the multiplicative-compounding
mechanism, and specifically implicating correlated predicates (rather than uniform,
independent ones) as the dominant source of the largest errors.

The independence assumption's failure on correlated data is a long-recognized problem
in the database research literature, motivating decades of work on multi-column
statistics (multivariate histograms, sampling-based join size estimation) — work that,
per Leis et al.'s findings, still hadn't fully closed the gap in production optimizers
as of their 2015 study, which is part of why runtime-informed re-planning (measuring
actual cardinalities rather than only estimating them) has become a complementary
rather than a superseding approach.

## Mitigations

### Collecting histogram-level statistics on skewed columns

**What it is:** Maintain histograms (not just row counts and min/max) for columns known
to have non-uniform distributions, improving single-column selectivity estimates.

**Cost:** Histogram maintenance costs more than simple counts, and choosing the right
bucketing granularity requires understanding the column's actual distribution shape.

**How it backfires:** Histograms address single-column skew but not cross-column
correlation — a column with an excellent histogram can still produce a bad joint
estimate when combined with a correlated column, and it's easy to mistake "we have good
statistics on this column" for "our joint estimates involving this column are
reliable."

### Multi-column / correlated statistics where supported

**What it is:** Where the engine supports it, collect statistics on combinations of
frequently co-filtered or co-joined columns, directly capturing correlation rather than
assuming independence.

**Cost:** Multi-column statistics are more expensive to collect and maintain, and the
combinatorial space of "which column pairs matter" isn't always obvious in advance.

**How it backfires:** Multi-column statistics collected for today's dominant query
pattern don't automatically cover a different correlation that becomes relevant as
query patterns evolve — this mitigation requires ongoing curation, not a one-time
setup.

### Runtime measurement instead of relying purely on pre-computed estimates

**What it is:** Use adaptive, runtime-informed re-planning to substitute actual
measured cardinalities for compile-time estimates at shuffle boundaries. See
[Adaptive Query Execution (AQE)](../spark-internals/adaptive-query-execution.md).

**Cost:** Only available at points in the plan where materialization already
happens — it doesn't eliminate the need for reasonable initial estimates before the
first such boundary.

**How it backfires:** For queries with correlated filters applied *before* the first
shuffle boundary, the initial scan's cardinality is still purely estimate-based, and a
bad initial estimate can still misdirect the first stage's own physical plan choice
before any runtime correction is possible.

## Interactions

- [Join Ordering](join-ordering.md) — the highest-stakes consumer of cardinality
  estimates, since ordering errors compound across every join in a multi-way join.
- [Query Planning & Cost-Based Optimization](query-planning-and-cbo.md) — the general
  mechanism this page's estimates feed into.
- [Adaptive Query Execution (AQE)](../spark-internals/adaptive-query-execution.md) —
  the primary mitigation for estimation error, substituting measurement for prediction
  wherever the plan structure allows it.

## References

- Leis, V. et al. *How Good Are Query Optimizers, Really?*. VLDB 2015. Empirically
  measures cardinality estimation error and its compounding effect across join depth.
- Ioannidis, Y. E. *The History of Histograms (abridged)*. VLDB 2003. Traces
  histogram-based statistics techniques and their limitations.
- Leis, V. et al. *Cardinality Estimation Done Right: Index-Based Join Sampling*. CIDR
  2017. Proposes sampling-based approaches specifically to address correlated-predicate
  estimation error.
