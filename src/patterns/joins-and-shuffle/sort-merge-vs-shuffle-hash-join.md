# Sort-Merge vs. Shuffle-Hash Join

> **One-liner:** Two shuffle join strategies with different memory and ordering tradeoffs, chosen automatically by the planner — usually correctly.

## Symptom

- Two structurally similar joins in the same pipeline show very different memory
  profiles in the execution UI — one spills, one doesn't.
- A join stage shows a sort step before the join that seems unnecessary for the query
  as written.
- Disabling a "shuffle hash join" config flag changes a job's runtime substantially in
  one direction.
- A join with a large build side occasionally OOMs, but only under certain data
  distributions.

## Mechanism

Once both sides of a join are shuffled so matching keys are co-located (see
[Broadcast vs. Shuffle Join](broadcast-vs-shuffle-join.md) for when this shuffle
happens at all), the engine still has to choose *how* to match rows within each
co-located partition. Two strategies dominate:

**Shuffle-hash join** builds an in-memory hash table from the smaller side of the join
within each partition, then streams the larger side through, probing the hash table for
matches. This avoids a sort entirely, so it's cheap when the build side fits
comfortably in memory. Its failure mode is exactly that assumption: if the build side
doesn't fit, the hash table itself has to spill, and a spilled hash table is far more
expensive to probe than a spilled sorted stream, because random-access probes against
spilled data don't benefit from sequential I/O the way a merge does.

**Sort-merge join** sorts both sides of each partition by the join key, then merges them
in a single sequential pass — the same key values from each side appear adjacent after
sorting, so matching becomes a linear scan instead of a hash lookup. This trades the
sort's CPU and (if it spills) I/O cost for a bounded, predictable memory footprint that
degrades gracefully — a sort-merge join that has to spill is still doing sequential
I/O, not scattered random access.

The planner's default preference (sort-merge as the safe general case, shuffle-hash
only when the build side is provably small enough) reflects this asymmetry: shuffle-hash
is faster when its assumption holds and considerably worse than sort-merge when it
doesn't, while sort-merge's worst case is only moderately worse than its best case. This
is a classic low-variance-vs-low-mean tradeoff, and most planners default toward the
lower-variance option unless given strong evidence the low-mean option is safe.

## Real-world sightings

Spark's own physical planning code and documentation describe `ShuffledHashJoin` as
requiring the build side to be markedly smaller than the stream side and to fit in
memory per-partition — a stricter condition than the broadcast threshold, which is why
shuffle-hash join is comparatively rare in default configurations and often has to be
explicitly enabled via a planner hint or configuration flag in versions where it isn't
cost-based by default.

Databricks and other vendor tuning guides consistently recommend sort-merge join as the
default-safe choice for large, unpredictable joins and reserve shuffle-hash join
recommendations for cases with well-understood, stable size asymmetry between the two
sides — echoing the general engineering practice of preferring predictable degradation
over a faster average case with a sharp cliff.

## Mitigations

### Prefer sort-merge for unpredictable size ratios

**What it is:** Leave the planner's default preference for sort-merge join in place
when the relative sizes of the two join sides aren't well known or stable over time.

**Cost:** Pays sort cost (CPU, and I/O if it spills) even in cases where a hash join
would have been cheaper.

**How it backfires:** For genuinely small-build-side joins that recur constantly (a
hot dimension table joined every run), always sorting both sides leaves real
performance on the table — this mitigation is conservative, not free.

### Enable shuffle-hash join only for known-stable size asymmetry

**What it is:** Explicitly hint or configure shuffle-hash join for specific joins where
the build side's size is bounded by a business invariant (a small, slow-changing
reference table).

**Cost:** Requires knowing and re-validating that size bound; it isn't self-correcting
the way the planner's default logic is.

**How it backfires:** The business invariant that made this safe ("this table only ever
has a few thousand rows") is exactly the kind of assumption that silently stops being
true after a schema change or new data source is merged in, and the failure shows up as
an OOM under load rather than a query-time warning.

### Size-based automatic selection (cost-based join strategy)

**What it is:** Let the planner choose between sort-merge and shuffle-hash based on
runtime or statistics-derived size estimates rather than a fixed hint.

**Cost:** Inherits the same estimation risk as
[Query Planning & Cost-Based Optimization](../sql-execution/query-planning-and-cbo.md)
generally — the decision is only as good as the estimate.

**How it backfires:** Under [Adaptive Query Execution (AQE)](../spark-internals/adaptive-query-execution.md),
runtime statistics correct static estimation errors at shuffle boundaries, but a join
strategy chosen before the relevant shuffle stage completes doesn't get this correction
retroactively.

## Interactions

- [Spill to Disk](spill-to-disk.md) — the two strategies fail differently under spill:
  a spilled hash table costs more than a spilled sorted stream for the same excess
  bytes.
- [Data Skew & Salting](data-skew-and-salting.md) — skew affects both strategies, but a
  skewed build-side key is catastrophic for shuffle-hash join specifically, since one
  partition's hash table becomes disproportionately large.
- [Memory Management](../spark-internals/memory-management.md) — the memory budget
  available for a hash table build directly determines whether shuffle-hash join is
  viable for a given partition.

## References

- Apache Spark Documentation. *SQL Performance Tuning — Join Strategies*. Describes the
  conditions under which `ShuffledHashJoinExec` is selected.
- Databricks Engineering Blog. *A Deep Dive into Query Execution Engine of Spark SQL*.
  Covers the internal decision logic between sort-merge and shuffle-hash join physical
  operators.
- Graefe, G. *Query Evaluation Techniques for Large Databases*. ACM Computing Surveys,
  1993. The classical treatment of sort-merge vs. hash join tradeoffs that most modern
  engines' planners still follow.
