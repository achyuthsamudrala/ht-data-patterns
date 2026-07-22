# SQL Query Execution Basics

> **A SQL query passes through four distinct transformations before a single row is
> read: parsing, analysis, logical optimization, and physical planning.** Every pattern
> about query planning, pushdown, or cost-based optimization in this guide refers to a
> specific one of these phases — knowing which phase a given optimization or failure
> belongs to is most of the diagnostic work.

## The four phases

**Parsing** turns SQL text into an abstract syntax tree (AST) — a structural
representation of the query's clauses (`SELECT`, `FROM`, `WHERE`, `JOIN`, `GROUP BY`)
with no knowledge yet of whether the referenced tables or columns actually exist. A
syntax error (a missing keyword, an unbalanced parenthesis) is caught here, before the
engine has looked at the schema at all.

**Analysis** (sometimes called binding or resolution) takes the parsed AST and
resolves every table and column reference against the catalog: does this table exist,
does this column exist on it, what's its type, is this function call valid for these
argument types. The output is a **resolved logical plan** — the same tree of relational
operators, but now every reference is bound to a concrete schema element rather than a
bare name. A "column not found" or "ambiguous column reference" error surfaces here.

**Logical optimization** applies transformation rules to the resolved logical plan that
preserve its meaning while (hopefully) making it cheaper to execute — this is where
[predicate and projection pushdown](../patterns/sql-execution/predicate-and-projection-pushdown.md),
constant folding, and other rule-based rewrites happen (see
[Catalyst Optimizer & Logical Plans](../patterns/spark-internals/catalyst-optimizer.md)
for how this looks concretely in Spark). These rewrites are provably safe — they don't
depend on data statistics, only on the query's own structure — which is why they're
called *rule-based* rather than *cost-based*.

**Physical planning** is where the engine chooses concrete algorithms for each logical
operator: which join strategy (see
[Broadcast vs. Shuffle Join](../patterns/joins-and-shuffle/broadcast-vs-shuffle-join.md)
and [Sort-Merge vs. Shuffle-Hash Join](../patterns/joins-and-shuffle/sort-merge-vs-shuffle-hash-join.md)),
which aggregation strategy (see
[Aggregation Strategies](../patterns/sql-execution/aggregation-strategies.md)), how many
shuffle partitions. Unlike logical optimization, this phase is genuinely **cost-based**:
it depends on estimates of data volume and distribution (see
[Statistics & Cardinality Estimation](../patterns/sql-execution/statistics-and-cardinality-estimation.md)),
and its decisions are only as good as those estimates.

## Why the phase distinction matters diagnostically

Most confusing query-performance behavior traces back to conflating these phases. A
query that returns the *correct result* but performs *badly* almost never has a
parsing or analysis problem — those phases only determine whether a query is valid,
not how efficiently it runs. Performance issues live in logical optimization (did a
rewrite that should have applied not fire — see the UDF opacity problem in
[Catalyst Optimizer & Logical Plans](../patterns/spark-internals/catalyst-optimizer.md))
or physical planning (was the chosen join strategy or partition count appropriate for
the actual data — see [Physical Plan Selection](../patterns/spark-internals/physical-plan-selection.md)).

This is also why reading `explain()` output productively requires knowing which plan
representation you're looking at: a *logical* plan shows relational operators without
committing to an execution strategy; a *physical* plan shows the concrete algorithms
chosen. The same query's logical plan is stable across data volumes; its physical plan
is not, which is precisely what makes physical planning cost-based-and-fragile in the
way [Query Planning & Cost-Based Optimization](../patterns/sql-execution/query-planning-and-cbo.md)
describes.

## Where this pipeline gets revisited at runtime

The classic model above treats all four phases as happening once, before execution
begins. [Adaptive Query Execution (AQE)](../patterns/spark-internals/adaptive-query-execution.md)
breaks this by re-entering physical planning *during* execution, at shuffle
boundaries, using measured rather than estimated statistics — a deliberate departure
from the traditional compile-once model, motivated by how often physical planning's
cost estimates turn out to be wrong (see
[Statistics & Cardinality Estimation](../patterns/sql-execution/statistics-and-cardinality-estimation.md)).

## Connections to other foundations

[Partitioning & Data Locality](partitioning-and-data-locality.md) and
[The Cost Model of Shuffle](shuffle-cost-model.md) describe the physical realities that
physical planning's decisions are ultimately trying to account for — a physical plan is,
in effect, a set of bets about data movement cost, made with whatever information
(estimated or measured) is available at the time the bet is placed.
