# Catalyst Optimizer & Logical Plans

> **One-liner:** Rule-based and cost-based rewrites transform a logical plan before it ever touches data — and can transform it wrong.

## Symptom

- The `explain()` output for a query shows a logical plan structurally different from
  the SQL as written — filters moved, projections pruned, joins reordered — before any
  data has been read.
- Two semantically equivalent queries (same result set, different SQL structure)
  produce very different execution plans and very different runtimes.
- Adding a seemingly unrelated `WHERE` clause changes the plan for an entirely
  different part of the query, in a way that isn't obvious from reading the SQL.
- A user-defined function (UDF) in a query disables optimizations (pushdown,
  pruning) that apply to the rest of the query, without any explicit signal that this
  happened.

## Mechanism

Catalyst is Spark SQL's query optimizer: it takes a query's logical plan — a
tree of relational operators (filter, project, join, aggregate) — and applies a
sequence of transformation rules to produce an equivalent but (hopefully) more
efficient plan, before any physical execution strategy is chosen. This happens in
phases: analysis (resolving references, types), logical optimization (rule-based
rewrites like predicate pushdown and constant folding), physical planning (choosing
concrete algorithms), and code generation.

The rules Catalyst applies are individually simple and provably correctness-preserving
— pushing a filter below a join is safe if the filter only references columns from one
side, for instance — but their *combined* effect on a specific query can be
non-obvious, because rules apply repeatedly and interact with each other. A predicate
pushed past one operator can enable another rule to fire that wouldn't have applied
otherwise, producing a final plan that's several rewrite steps removed from what the
SQL text suggests.

The optimizer's blind spots are as important as its rewrites. A user-defined function is
opaque to Catalyst — it cannot look inside a UDF to determine whether a filter can be
pushed through it, so it conservatively doesn't, which silently disables pushdown for
anything downstream of the UDF in the plan. Similarly, rule-based optimization doesn't
know the actual size or distribution of the data; that's the job of the cost-based
phase, which depends on statistics (see
[Statistics & Cardinality Estimation](../sql-execution/statistics-and-cardinality-estimation.md))
that may be stale, absent, or simply not granular enough for the specific filtered
subquery being planned.

## Real-world sightings

The original Catalyst design is described in Armbrust et al.'s "Spark SQL: Relational
Data Processing in Spark" (SIGMOD 2015), which documents the rule-based logical
optimization phases (predicate pushdown, constant folding, projection pruning) as
extensible, pattern-matched tree transformations — a design explicitly chosen so new
optimization rules could be added without rewriting the planner, which is also why
Catalyst's rule set has grown substantially since the paper's publication as Spark has
added support for more SQL constructs and data sources.

The interaction between UDFs and pushdown optimization is a widely documented
Spark performance gotcha in vendor engineering blogs (Databricks in particular),
consistently recommending native SQL expressions or built-in functions over UDFs
specifically because Catalyst can reason about and optimize around the former but
treats the latter as an opaque black box.

## Mitigations

### Reading `explain()` output before assuming query intent

**What it is:** Inspect the logical and physical plan Catalyst actually produced,
rather than reasoning purely from the SQL text, when diagnosing unexpected performance.

**Cost:** Requires familiarity with reading plan trees, which is a skill separate from
writing SQL and often underdeveloped on teams that treat the query engine as a black
box.

**How it backfires:** `explain()` shows the plan Catalyst chose given current
statistics; it doesn't show *why* alternative plans were rejected, so it's diagnostic
but not always sufficient to explain a regression without also checking statistics
freshness.

### Preferring built-in expressions over UDFs

**What it is:** Express logic using native SQL/DataFrame functions wherever possible,
reserving UDFs for genuinely custom logic Catalyst has no equivalent for.

**Cost:** Some logic is genuinely awkward or verbose to express without a UDF, trading
optimizer visibility for code clarity.

**How it backfires:** Even "mostly built-in" queries with a single UDF in a filter
predicate can lose pushdown for that entire predicate, so partial UDF usage doesn't
give partial optimization — the blocked rule simply doesn't fire for that path.

### Explicit hints for known-good plans

**What it is:** Use planner hints (join strategy, repartition hints) to pin a plan that
has been empirically verified as correct, bypassing rule-based or cost-based
uncertainty.

**Cost:** Hints override the optimizer's ability to adapt as data or statistics change,
trading the risk of a bad automatic decision for the certainty of a decision that
doesn't update itself.

**How it backfires:** A hint that was correct for last year's data volume becomes
actively wrong as volume grows, and — because it's a hint, not a suggestion — the
planner won't override it even when its own updated statistics would recommend
something else.

## Interactions

- [Physical Plan Selection](physical-plan-selection.md) — Catalyst's logical
  optimization phase feeds directly into physical plan selection; a logical plan
  Catalyst mis-optimized produces a physical plan chosen from the wrong starting point.
- [Statistics & Cardinality Estimation](../sql-execution/statistics-and-cardinality-estimation.md) —
  cost-based rewrites within Catalyst are only as reliable as the statistics feeding
  them.
- [Adaptive Query Execution (AQE)](adaptive-query-execution.md) — AQE re-runs a subset
  of Catalyst's optimization logic at runtime using actual shuffle statistics,
  correcting some (not all) of the compile-time estimation errors described above.

## References

- Armbrust, M. et al. *Spark SQL: Relational Data Processing in Spark*. SIGMOD 2015.
  The original Catalyst optimizer design paper.
- Databricks Engineering Blog. *Deep Dive into Spark SQL's Catalyst Optimizer*. Explains
  the rule-based transformation phases and extensibility model in practitioner terms.
- Databricks Engineering Blog. *Introducing Pandas UDF for PySpark* and related UDF
  performance guidance. Documents the pushdown-blocking effect of opaque UDFs.
