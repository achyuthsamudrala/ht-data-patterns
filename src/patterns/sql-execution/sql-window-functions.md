# SQL Window Functions

> **One-liner:** A window function's `PARTITION BY` and frame specification determine whether it's nearly free or forces a full shuffle and sort — and the syntax gives no visual hint which.

## Symptom

- Adding a window function (`ROW_NUMBER()`, `RANK()`, a running `SUM() OVER (...)`) to
  an otherwise simple query introduces a new, expensive shuffle stage that wasn't
  present before.
- Two window function calls that look superficially similar — differing only in their
  `PARTITION BY` column — have dramatically different performance, one nearly free and
  one expensive.
- A window function with an unbounded preceding frame (`ROWS BETWEEN UNBOUNDED
  PRECEDING AND CURRENT ROW`) shows memory usage that grows with partition size in a
  way a fixed-size frame doesn't.
- Combining multiple window functions with different `PARTITION BY`/`ORDER BY`
  specifications in the same query triggers multiple separate, expensive shuffle-and-
  sort passes, one per distinct window specification, rather than a single combined
  pass.

## Mechanism

A window function computes a value for each row using a "window" of related rows —
defined by `PARTITION BY` (which rows belong together) and `ORDER BY`/frame bounds
(which rows within a partition are visible to the computation) — without collapsing
the result to one row per group the way a `GROUP BY` aggregation does. This makes
window functions powerful for tasks like running totals, rankings, and
row-to-row comparisons, but their cost structure is governed entirely by the same
[shuffle cost model](../../foundations/shuffle-cost-model.md) and
[partitioning](../../foundations/partitioning-and-data-locality.md) principles that
govern joins and aggregations — a fact the SQL syntax itself gives no visual cue about.

**`PARTITION BY` requires the same co-location as a `GROUP BY` or join key**: to
compute a window function correctly, all rows sharing a partition value need to be
processed together, which — exactly as with
[Shuffle Partitioning Strategy](../joins-and-shuffle/shuffle-partitioning-strategy.md) —
requires a shuffle to bring same-partition rows together if they aren't already
co-located. A `PARTITION BY` on a column the data isn't already partitioned by
therefore forces a shuffle no different in kind from a `GROUP BY` on that column,
even though the query syntax (a window function embedded in a `SELECT` list, rather
than an explicit `GROUP BY` clause) can visually obscure that this is happening.

**Frame specification determines both computational complexity and memory profile**:
a bounded frame (`ROWS BETWEEN 5 PRECEDING AND CURRENT ROW`) requires holding only a
small, fixed window of rows in memory at once as the partition is scanned in order. An
unbounded frame (`ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`, common for
running totals) requires either holding the full accumulated state for the partition or
recomputing over an ever-growing prefix, and — for a partition that's large relative to
available memory — this can force the same kind of spill described in
[Spill to Disk](../joins-and-shuffle/spill-to-disk.md), scaled by partition size rather
than by total row count.

**Multiple distinct window specifications multiply shuffle cost**: a query with several
window functions using *different* `PARTITION BY`/`ORDER BY` combinations generally
requires a separate shuffle-and-sort pass per distinct specification, because rows
co-located for one partitioning scheme aren't necessarily co-located for another.
Query planners can sometimes share a single shuffle across window functions with
*identical* partition and order specifications, but this optimization doesn't extend
across genuinely different specifications — a query casually combining several
differently-partitioned window functions can silently pay for several full shuffles
where a query author might have expected one combined pass.

## Real-world sightings

Spark's and other SQL engines' physical plan documentation for window functions
explicitly describes the shuffle-and-sort requirement driven by `PARTITION BY`/`ORDER
BY`, and query optimization guidance from vendors (Databricks among them) commonly
recommends being deliberate about `PARTITION BY` column choice for window functions
specifically because of this shuffle cost, treating it as equivalent in kind to
choosing a `GROUP BY` or join key.

The ANSI SQL:2003 standard, which introduced window functions (`OVER` clause) to the
SQL language, defines the frame specification semantics (`ROWS`/`RANGE`,
`UNBOUNDED PRECEDING`, etc.) that determine a given window function's memory and
computation profile — the standard's flexibility in frame specification is precisely
what creates the performance variability described above, since syntactically similar
frame clauses can have very different execution costs depending on the specific bounds
chosen.

## Mitigations

### Choosing `PARTITION BY` columns with shuffle cost in mind

**What it is:** Treat a window function's `PARTITION BY` column choice as a shuffle-cost
decision equivalent to choosing a `GROUP BY` or join key, considering cardinality and
existing data partitioning rather than choosing purely for query-logic convenience.

**Cost:** May require restructuring a query's logic or upstream data layout to align
window partitioning with a cheaper, already-co-located column where business logic
allows.

**How it backfires:** Business logic sometimes genuinely requires partitioning on a
column that doesn't align with existing data layout, in which case the shuffle cost is
unavoidable regardless of how carefully the column is chosen — this mitigation reduces
avoidable cost, not all of it.

### Bounding frame specifications where the business logic allows

**What it is:** Use a bounded frame (a fixed number of preceding/following rows)
instead of an unbounded one where the actual analytical requirement permits it,
keeping memory cost independent of partition size.

**Cost:** A bounded frame may not correctly express a genuine "running total since the
beginning of the partition" requirement, in which case an unbounded frame is
semantically necessary regardless of its cost.

**How it backfires:** None specific to correctly bounding a frame where the logic
allows — the risk is defaulting to an unbounded frame out of habit for computations
that would have been equally correct, and much cheaper, with a bounded one.

### Consolidating window functions to share partition/order specifications

**What it is:** Where multiple window functions are needed in the same query, use
consistent `PARTITION BY`/`ORDER BY` specifications across them where the analytical
requirement allows, so the planner can share a single shuffle-and-sort pass rather
than paying for several.

**Cost:** Requires restructuring query logic that might otherwise use genuinely
different partition/order specifications per window function, which isn't always
possible if the underlying analytical requirements truly differ.

**How it backfires:** Forcing a shared specification onto window functions that
genuinely need different partitioning changes query semantics, not just performance —
this consolidation is only valid when the underlying analytical intent is actually
compatible across the functions being consolidated.

## Interactions

- [Shuffle Partitioning Strategy](../joins-and-shuffle/shuffle-partitioning-strategy.md) —
  the same partition-count and co-location cost model applies directly to window
  function `PARTITION BY` clauses.
- [Spill to Disk](../joins-and-shuffle/spill-to-disk.md) — an unbounded window frame
  over a large partition is exposed to the same memory-exceeded spill risk as any
  other large in-memory computation.
- [Aggregation Strategies](aggregation-strategies.md) — window functions and
  aggregations solve related problems (computing over groups of rows) with different
  output cardinality, but share much of the same underlying cost model.

## References

- ISO/IEC 9075 (SQL:2003) and later revisions. Defines the `OVER` clause, `PARTITION
  BY`, and frame specification (`ROWS`/`RANGE`) semantics for SQL window functions.
- Apache Spark Documentation. *Window Functions*. Describes physical execution
  requirements (shuffle and sort) for `PARTITION BY`/`ORDER BY` in a widely used engine.
- Databricks Engineering Blog. *Introducing Window Functions in Spark SQL*. Discusses
  practical performance considerations for window function partition and frame choice.
