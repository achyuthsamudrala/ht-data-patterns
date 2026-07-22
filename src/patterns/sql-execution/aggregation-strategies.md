# Aggregation Strategies

> **One-liner:** Hash-based and sort-based aggregation make the same memory-versus-ordering tradeoff as their join-strategy counterparts, and exact distinct counting doesn't scale the way sums and counts do.

## Symptom

- A `GROUP BY` query's memory usage grows unpredictably with the number of distinct
  groups, in a way a `SUM` or `COUNT` alone over the same data wouldn't.
- Aggregating a high-cardinality dimension (a user ID, a session ID) causes spill or
  out-of-memory errors that don't occur when aggregating a low-cardinality one (a
  country code) over the same row count.
- `COUNT(DISTINCT ...)` on a large, high-cardinality column runs dramatically slower
  and consumes far more memory than an approximate distinct-count function over the
  same column.
- Pre-aggregating a metric partially at the map/shuffle-input side, before the final
  shuffle, reduces shuffle volume dramatically for a low-cardinality group-by but
  provides almost no benefit for a high-cardinality one.

## Mechanism

Aggregation combines many rows into fewer, grouped results, and — like joins (see
[Sort-Merge vs. Shuffle-Hash Join](../joins-and-shuffle/sort-merge-vs-shuffle-hash-join.md)) —
engines choose between hash-based and sort-based strategies with the same underlying
memory-versus-ordering tradeoff.

**Hash-based aggregation** builds an in-memory hash table keyed by the group-by
columns, updating each group's running aggregate (sum, count, running average) as rows
stream through. This is efficient when the number of distinct groups is small enough
that the hash table fits comfortably in memory — the classic case of aggregating a
low-cardinality dimension. When the number of distinct groups is large (high
cardinality), the hash table itself grows large and can exceed the available memory
budget, forcing the same kind of spill described in
[Spill to Disk](../joins-and-shuffle/spill-to-disk.md), and — just as with a spilled
hash join — a spilled hash-based aggregation degrades disproportionately, since
random-access updates against spilled state are far more expensive than in-memory
ones.

**Sort-based aggregation** sorts rows by the group-by key first, so all rows
belonging to the same group become adjacent, and the aggregate can then be computed in
a single sequential pass with bounded memory (only the current group's running state
needs to be held at once, not every group simultaneously). This trades the sort's
upfront cost for a memory profile that doesn't scale with group cardinality the way
hash-based aggregation's does — the same tradeoff sort-merge join makes relative to
shuffle-hash join.

**Partial (pre-shuffle) aggregation** reduces shuffle volume by aggregating locally,
on each task's own data, before the shuffle that brings matching groups together for a
final aggregation pass. This is highly effective for low-cardinality group-bys — many
rows collapse into few pre-aggregated groups locally, so the shuffle only has to move a
small number of partial aggregates per task rather than every raw row. For
high-cardinality group-bys, this benefit shrinks toward nothing: if nearly every row
belongs to its own distinct group, local pre-aggregation produces almost as many
partial results as there were raw rows, and the shuffle still has to move nearly the
full data volume regardless.

**Exact `COUNT(DISTINCT)`** requires tracking the full set of distinct values seen —
either via a hash-based aggregation over the distinct column itself, or a sort-and-
deduplicate pass — and its cost therefore scales with the number of distinct values,
not with the total row count, which is exactly the high-cardinality-aggregation cost
problem above, applied specifically to distinct counting. Approximate distinct-count
algorithms (HyperLogLog and related sketch-based approaches) sidestep this by
maintaining a small, fixed-size probabilistic summary instead of the full distinct set,
trading exactness for bounded memory regardless of cardinality — a tradeoff that's
usually acceptable for large-scale analytical distinct counts (where a small
percentage error is immaterial) but not for contexts requiring exact counts (billing,
compliance).

## Real-world sightings

The HyperLogLog algorithm (Flajolet et al., "HyperLogLog: The Analysis of a
Near-Optimal Cardinality Estimation Algorithm," 2007) is the foundational reference for
approximate distinct counting with bounded memory, and its adoption across essentially
every major analytical database and query engine (Presto/Trino's
`approx_distinct`, Spark's `approx_count_distinct`, and equivalents elsewhere) reflects
how widely the exact-`COUNT(DISTINCT)` cost problem is felt in production analytical
workloads at scale.

Spark's and other engines' documentation on partial aggregation (sometimes called
"map-side combine" or "pre-aggregation," tracing back to the combiner concept in the
original MapReduce paper) explicitly frames it as a shuffle-volume-reduction
optimization whose effectiveness is directly tied to group cardinality relative to row
count — an optimization that's automatic and highly beneficial for typical low-
cardinality business dimensions and correspondingly less impactful as cardinality
approaches the row count itself.

## Mitigations

### Using approximate distinct-count functions for large-scale analytical counts

**What it is:** Replace exact `COUNT(DISTINCT ...)` with an approximate,
sketch-based equivalent (HyperLogLog or similar) for analytical use cases that can
tolerate a small percentage error in exchange for bounded memory and much faster
execution.

**Cost:** Introduces a known, typically small but non-zero error margin, which is
unacceptable for exact-count requirements like billing or compliance reporting.

**How it backfires:** Approximate counts can compound unpredictably when combined
across multiple aggregation levels (summing several approximate counts doesn't
necessarily preserve the same error bound as a single approximate count over the
combined data), which is easy to overlook when composing approximate aggregates
across a multi-stage pipeline.

### Sort-based aggregation for known high-cardinality group-bys

**What it is:** Prefer or force sort-based aggregation for group-by operations known
to have high cardinality, where hash-based aggregation's memory profile would be
risky.

**Cost:** Pays the sort's upfront cost even for cases where cardinality turns out to be
lower than expected and hash-based aggregation would have been cheaper.

**How it backfires:** A cardinality assumption that motivated choosing sort-based
aggregation can become stale as the underlying dimension's actual cardinality
changes over time, without a clear signal that the original choice should be
revisited.

### Understanding when partial aggregation provides real benefit

**What it is:** Recognize that partial (pre-shuffle) aggregation's shuffle-volume
reduction is proportional to how much the group-by key collapses row count, and not
expect meaningful benefit for high-cardinality group-bys where this collapse is
minimal.

**Cost:** Requires understanding the specific cardinality of a group-by key in
advance, which may not always be well known.

**How it backfires:** None specific to understanding this correctly — the risk is
assuming partial aggregation is a universal shuffle-reduction technique and being
surprised when it doesn't help for a high-cardinality case.

## Interactions

- [Sort-Merge vs. Shuffle-Hash Join](../joins-and-shuffle/sort-merge-vs-shuffle-hash-join.md) —
  the join-strategy counterpart to hash-based vs. sort-based aggregation, sharing the
  same underlying memory-versus-ordering tradeoff.
- [Spill to Disk](../joins-and-shuffle/spill-to-disk.md) — a hash-based aggregation
  whose group count exceeds its memory budget spills in exactly the same manner and
  with the same disproportionate cost as a spilled hash join.
- [Shuffle Partitioning Strategy](../joins-and-shuffle/shuffle-partitioning-strategy.md) —
  partial aggregation's shuffle-volume reduction directly affects how much data a
  chosen partition count actually needs to move.

## References

- Flajolet, P. et al. *HyperLogLog: The Analysis of a Near-Optimal Cardinality
  Estimation Algorithm*. AofA 2007. The foundational approximate distinct-counting
  algorithm underlying most modern engines' approximate `COUNT(DISTINCT)` support.
- Dean, J. and Ghemawat, S. *MapReduce: Simplified Data Processing on Large Clusters*.
  OSDI 2004. Introduces the combiner concept underlying map-side partial aggregation.
- Graefe, G. *Query Evaluation Techniques for Large Databases*. ACM Computing Surveys,
  1993. Classical treatment of hash-based vs. sort-based aggregation execution
  strategies.
