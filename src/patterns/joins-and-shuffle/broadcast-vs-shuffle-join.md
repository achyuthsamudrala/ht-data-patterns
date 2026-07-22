# Broadcast vs. Shuffle Join

> **One-liner:** The choice between broadcasting a small table and shuffling both sides determines whether a join costs milliseconds or minutes.

## Symptom

- A join that ran in seconds in staging takes minutes or hours in production, with no
  code change — only data volume changed.
- Spark UI (or equivalent execution UI) shows a `SortMergeJoin` or `ShuffledHashJoin`
  physical operator where a `BroadcastHashJoin` was expected.
- Every executor shows heavy shuffle read/write for a stage that "should" have been a
  simple lookup against a small dimension table.
- After a routine data refresh, the same query's physical plan changes even though the
  SQL text didn't.

## Mechanism

A join needs matching rows to be co-located before they can be compared. There are two
ways to get there: shuffle both sides so matching keys land on the same node
(expensive, general), or copy one side — if it's small enough — to every node so no
shuffle is needed at all (cheap, but only works when one side fits in memory
everywhere it's needed).

Broadcast join copies the smaller table to every executor's memory. Each executor then
does a local, in-memory hash join against its partition of the large table. No shuffle
of the large table happens at all — this is the entire point. The cost is bounded by
the broadcast table's size times the number of executors, not by the large table's
size.

Shuffle join (sort-merge or shuffle-hash — see
[Sort-Merge vs. Shuffle-Hash Join](sort-merge-vs-shuffle-hash-join.md)) repartitions
*both* sides of the join by the join key, paying the full
[shuffle cost](../../foundations/shuffle-cost-model.md) — serialization, network
transfer, and possibly spill — for both tables, however large they are.

Query planners choose between these strategies using a size threshold: if the
estimated size of one side is below the broadcast threshold (Spark's default is 10 MB,
commonly raised to hundreds of MB or a few GB in production), the planner broadcasts.
That estimate comes from table statistics, which is exactly where this pattern breaks:
the estimate can be wrong, stale, or simply absent for the specific filtered/joined
subquery the planner needs to decide on, at which point it falls back to a shuffle join
for a table that would easily have fit in a broadcast.

## Real-world sightings

Databricks' own engineering documentation and conference talks on Adaptive Query
Execution describe this exact failure mode as a primary motivation for AQE's
runtime-based join strategy conversion: static, compile-time size estimates
(especially after several chained filters or joins) are frequently wrong by an order of
magnitude, causing the planner to pick shuffle joins for tables that turn out, at
execution time, to be broadcast-sized. AQE's "convert sort-merge join to broadcast
join" rule exists specifically to correct this after the fact, using actual
shuffle-stage output sizes instead of compile-time estimates.

The Spark project's own tuning guide and numerous vendor engineering blogs (Databricks,
AWS EMR, Google Cloud Dataproc) document the broadcast threshold as one of the first
tuning knobs recommended when diagnosing an unexpectedly slow join, precisely because
the default threshold is conservative and many real dimension tables comfortably exceed
it while still being broadcast-worthy on modern executor memory sizes.

## Mitigations

### Explicit broadcast hints

**What it is:** Annotate the query (`/*+ BROADCAST(t) */` or the equivalent DataFrame
hint) to force broadcast join regardless of the planner's size estimate.

**Cost:** Bypasses the planner's safety check. If the hinted table grows beyond
executor memory capacity, every executor now tries to hold a copy that no longer fits.

**How it backfires:** A hint added when a table was small becomes a landmine when the
table grows — nothing warns that the hint is now unsafe, because the whole point of a
hint is that it overrides the planner's own size-based judgment. This is a common
source of executor OOMs that appear only after months of organic data growth.

### Raising the broadcast threshold

**What it is:** Increase `spark.sql.autoBroadcastJoinThreshold` (or engine equivalent)
so more tables qualify for broadcast automatically, based on the planner's own
estimate.

**Cost:** Every table under the new threshold is now a broadcast candidate, increasing
per-executor memory pressure for all such joins, not just the one you were tuning.

**How it backfires:** If the underlying statistics are stale or wrong (see
[Statistics & Cardinality Estimation](../sql-execution/statistics-and-cardinality-estimation.md)),
raising the threshold doesn't fix bad estimates — it just makes the planner more
willing to act on them, which can convert a *correctly* shuffle-joined large table into
an *incorrectly* broadcast one.

### Adaptive Query Execution join conversion

**What it is:** Let the engine measure actual shuffle-stage output size at runtime and
convert a sort-merge join to a broadcast join after the fact, if the measured size
qualifies. See
[Adaptive Query Execution (AQE)](../spark-internals/adaptive-query-execution.md).

**Cost:** Requires an initial shuffle stage to measure size before conversion can
happen — the first stage isn't free, only the *join* stage is optimized.

**How it backfires:** AQE re-planning happens at shuffle stage boundaries; a join whose
inputs are produced without an intervening shuffle boundary (e.g., already
broadcast-joined upstream) gets no opportunity to reconsider.

## Interactions

- [Data Skew & Salting](data-skew-and-salting.md) — a shuffle join chosen instead of a
  broadcast join is also now exposed to key skew, compounding the mis-planning cost.
- [Statistics & Cardinality Estimation](../sql-execution/statistics-and-cardinality-estimation.md) —
  the broadcast/shuffle decision is only as good as the size estimate feeding it.
- [Memory Management](../spark-internals/memory-management.md) — a broadcast that
  succeeds at the planner level can still exhaust executor memory if the broadcast
  table's size estimate was itself wrong.

## References

- Databricks Engineering Blog. *Adaptive Query Execution: Speeding Up Spark SQL at
  Runtime*. Explains the broadcast-conversion rule and why static estimates fail.
- Apache Spark Documentation. *Performance Tuning — Join Strategy Hints*. Official
  reference for broadcast thresholds and hint syntax.
- Armbrust, M. et al. *Spark SQL: Relational Data Processing in Spark*. SIGMOD 2015.
  The original Catalyst optimizer paper, including early join-strategy selection logic.
