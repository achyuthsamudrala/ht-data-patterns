# Dynamic Partition Pruning

> **One-liner:** Runtime filters propagated from a dimension table into a fact table scan can turn a full scan into a targeted one — when the plan supports it.

## Symptom

- A join between a small, filtered dimension table and a large, partitioned fact table
  scans far more of the fact table than the dimension-side filter should require.
- Adding an explicit partition filter to the fact table side of a query (duplicating a
  filter already implied by the join) dramatically speeds up the query, even though the
  join should have implied the same restriction.
- The execution UI shows the fact table scan reading partitions that can't possibly
  contain matching rows given the dimension table's filter, before the join has even
  executed.
- A query plan looks correct and the join key types match, but pruning still doesn't
  occur, with no clear indication why.

## Mechanism

A common analytical pattern joins a small, filtered dimension table (e.g., "stores in
region X") against a large fact table partitioned by the join key (e.g., store ID),
where only a small subset of the fact table's partitions could possibly match. Static
partition pruning — filtering partitions based on a literal predicate known at compile
time — can't help here, because the actual set of matching keys isn't known until the
dimension table's filter has been evaluated, which happens as part of executing the
join, not before it.

Dynamic partition pruning closes this gap: it evaluates the dimension side's filter
first, collects the resulting set of keys, and pushes that key set down as a runtime
filter into the fact table scan — before or during the scan, rather than after reading
everything and joining. This can reduce a fact table scan from "every partition" to
"only the partitions containing matching keys," which is potentially an order-of-
magnitude reduction in data read for a highly selective dimension filter.

The optimization has real preconditions, though: the planner has to recognize the join
as a partition-pruning opportunity (the fact table must be partitioned on the join key,
or a column derivable from it), and it has to be confident that materializing the
dimension side's filtered key set is cheap enough to be worth doing before the main
scan. When any precondition isn't met — the join is on a derived or transformed column
rather than the raw partition column, or the fact table isn't partitioned that way at
all — the optimization silently doesn't apply, and the query falls back to reading and
filtering the full fact table, with no error to indicate the pruning opportunity was
missed.

## Real-world sightings

Dynamic partition pruning is described in Spark's release documentation (introduced as
part of Spark 3.0) and Databricks engineering posts as directly targeting star-schema
and snowflake-schema query patterns common in data warehousing — exactly the small
dimension table / large partitioned fact table shape described above — and explicitly
frames it as extending static partition pruning to cases where the pruning predicate
isn't known until runtime.

The broader technique (runtime filter propagation into a scan, sometimes called
"semi-join reduction" or "runtime filters" in other engines like Presto/Trino and
Impala) is a long-standing technique in the database systems literature for exactly
this join shape, predating any single vendor's implementation — it reflects a general
optimization opportunity in star-schema analytical queries rather than an
engine-specific trick.

## Mitigations

### Structuring fact tables partitioned on common join keys

**What it is:** Partition large fact tables on columns commonly used as dimension-table
join keys, so dynamic partition pruning's precondition (partitioning aligned with the
join key) is met.

**Cost:** A partitioning scheme optimized for one common join pattern may not suit
other query patterns against the same fact table, requiring a tradeoff across use
cases.

**How it backfires:** A fact table partitioned for today's dominant query pattern loses
this optimization's benefit if the dominant join key changes as usage evolves, and
nothing signals that the partitioning scheme has become a poor fit.

### Avoiding derived-column joins where raw partition columns would work

**What it is:** Join directly on the fact table's actual partition column rather than a
transformed or derived version of it (e.g., joining on a raw date column rather than a
computed week-number derived from it).

**Cost:** Sometimes the natural, business-meaningful join key really is a derived
column, and joining on the raw column requires an awkward query restructuring.

**How it backfires:** This is a real constraint, not just a style preference — most
planners cannot see through arbitrary transformations to recognize a derived column as
equivalent to a partition column, so this restructuring is often a genuine requirement
for pruning to apply, not merely a nice-to-have.

### Verifying pruning is actually applied via `explain()`

**What it is:** Check the physical plan for the dynamic partition pruning operator's
presence, rather than assuming it applies whenever the query shape looks eligible.

**Cost:** Requires the same plan-reading familiarity described in
[Catalyst Optimizer & Logical Plans](catalyst-optimizer.md).

**How it backfires:** A plan verified once, at initial query design time, can silently
lose pruning eligibility later if a schema change alters column types or a query
rewrite introduces a transformation the planner can no longer see through.

## Interactions

- [Partition Layout & Pruning](../storage/partition-layout-and-pruning.md) — dynamic
  partition pruning is the runtime, join-aware complement to static partition layout
  design; the storage-layer page covers the layout decisions this optimization depends
  on.
- [Broadcast vs. Shuffle Join](../joins-and-shuffle/broadcast-vs-shuffle-join.md) —
  dynamic partition pruning is most commonly applied alongside a broadcast join on the
  small dimension side, since materializing the filtered key set cheaply usually
  implies the dimension side is broadcast-sized.
- [Predicate & Projection Pushdown](../sql-execution/predicate-and-projection-pushdown.md) —
  a closely related but distinct optimization: pushdown applies known filters at
  compile time, while dynamic partition pruning applies filters only known at runtime.

## References

- Apache Spark Documentation. *Spark 3.0 Release Notes — Dynamic Partition Pruning*.
  Describes the feature's design and target query shape.
- Databricks Engineering Blog. *Dynamic Partition Pruning in Apache Spark*. Explains
  the star-schema motivation and preconditions for the optimization to apply.
- Neumann, T. et al. *Adaptive Optimization of Very Large Join Queries*. SIGMOD 2018.
  Broader treatment of runtime filter propagation techniques across database systems.
