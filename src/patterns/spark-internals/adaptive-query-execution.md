# Adaptive Query Execution (AQE)

> **One-liner:** AQE re-plans joins and partition counts using runtime statistics — powerful, but it changes the plan you thought you were debugging.

## Symptom

- The physical plan shown by `explain()` before execution differs from the plan
  actually reported in the execution UI after the job runs.
- The same query, run twice on data of meaningfully different volume, produces
  different shuffle partition counts or different join strategies without any
  configuration change.
- A performance regression appears intermittently and correlates with data volume
  crossing some threshold, rather than with any code or config change.
- Debugging a slow stage by reading the compile-time plan leads to a dead end, because
  the actual bottleneck stage was inserted or altered by runtime re-planning.

## Mechanism

Traditional query planning is entirely compile-time: the planner estimates costs from
statistics, picks a physical plan, and executes it unchanged, even if those estimates
turn out to be wrong once real data flows through (see
[Physical Plan Selection](physical-plan-selection.md) and
[Statistics & Cardinality Estimation](../sql-execution/statistics-and-cardinality-estimation.md)
for why those estimates are frequently wrong). Adaptive Query Execution addresses this
by re-planning *during* execution, at shuffle-stage boundaries, using the actual size and
distribution of data the previous stage produced — a measurement rather than an
estimate.

AQE performs three main corrections at these boundaries: **coalescing** small
post-shuffle partitions into fewer, appropriately-sized ones (see
[Shuffle Partitioning Strategy](../joins-and-shuffle/shuffle-partitioning-strategy.md));
**converting** a sort-merge join into a broadcast join when the measured size of one
side turns out to be small enough (see
[Broadcast vs. Shuffle Join](../joins-and-shuffle/broadcast-vs-shuffle-join.md)); and
**splitting** skewed partitions detected from measured, not estimated, partition sizes
(see [Data Skew & Salting](../joins-and-shuffle/data-skew-and-salting.md)).

The mechanism that makes this possible — waiting until a shuffle stage's output is
materialized before deciding the next stage's plan — is also what limits it: AQE can
only correct decisions at points where a shuffle boundary already exists to pause and
measure. A query with few or no shuffle boundaries offers little opportunity for
adaptive correction, and the very first stage's plan (before any measurement is
possible) is chosen exactly the same way it always was — from compile-time estimates.

The practical consequence for anyone debugging a query: the plan you see with
`explain()` before execution is a *prediction*, and the plan the execution UI reports
after the fact reflects what actually happened, potentially including strategies AQE
substituted mid-flight. Treating the former as ground truth for what ran is a reliable
source of confusion.

## Real-world sightings

Databricks' engineering blog "Adaptive Query Execution: Speeding Up Spark SQL at
Runtime" is the primary public description of this feature's design and the specific
production problems (static estimation errors on broadcast thresholds, skewed
partitions, oversized shuffle partition counts) that motivated each of its three
corrections. The post explicitly frames AQE as a response to the limits of
compile-time-only optimization, consistent with the broader database research finding
(Leis et al., VLDB 2015) that cardinality estimation error, not cost model design,
dominates bad physical-plan decisions in traditional optimizers.

Spark's JIRA tracking for AQE (SPARK-23128 and related sub-tasks) documents the
feature's staged rollout — skew join handling, partition coalescing, and join
conversion were developed and stabilized somewhat independently — reflecting that each
correction addresses a distinct estimation failure mode rather than a single unified
fix.

## Mitigations

### Enabling AQE as a default, not an opt-in tuning step

**What it is:** Run with adaptive execution enabled by default (as recent Spark
versions do), rather than treating it as a specialized tuning flag applied only after
a problem is diagnosed.

**Cost:** Adds runtime overhead for the measurement and re-planning itself, and makes
plan behavior slightly less predictable run-to-run for otherwise-identical queries on
different data.

**How it backfires:** Because AQE changes plans based on runtime measurements, two runs
of the same query on different-sized inputs can produce genuinely different plans —
this is the intended behavior, but it breaks the assumption (common in performance
regression testing) that identical SQL implies an identical, reproducible plan.

### Debugging from the post-execution plan, not the pre-execution one

**What it is:** When diagnosing a slow query, inspect the actual execution UI's
reported plan and stage metrics rather than relying solely on a pre-execution
`explain()` call.

**Cost:** Requires re-running or having access to a completed execution to see the
adaptive corrections that were actually applied.

**How it backfires:** For long-running or expensive queries, this means diagnosis can't
happen until after paying the full cost of a run — there's no cheap way to preview
AQE's runtime decisions without executing the shuffle stages that trigger them.

### Understanding AQE's boundary limitations

**What it is:** Recognize which decisions AQE can and cannot correct (post-shuffle
corrections only, not pre-first-shuffle decisions), to avoid assuming it will fix
issues outside that boundary.

**Cost:** Requires deeper mental-model investment than treating AQE as a general
"makes queries faster" switch.

**How it backfires:** None specifically — this mitigation is purely about calibrating
expectations, but its absence is a common cause of "I enabled AQE and it didn't help"
reports where the actual bottleneck was in a pre-shuffle scan or filter AQE has no
visibility into.

## Interactions

- [Physical Plan Selection](physical-plan-selection.md) — AQE is the runtime correction
  mechanism for exactly the compile-time estimation risk that section describes.
- [Data Skew & Salting](../joins-and-shuffle/data-skew-and-salting.md) — AQE's
  skew-join handling automates what manual salting otherwise addresses by hand.
- [Shuffle Partitioning Strategy](../joins-and-shuffle/shuffle-partitioning-strategy.md) —
  AQE's partition coalescing directly replaces the need for a hand-tuned static
  partition count in many cases.

## References

- Databricks Engineering Blog. *Adaptive Query Execution: Speeding Up Spark SQL at
  Runtime*. The primary design and motivation reference for AQE's three correction
  mechanisms.
- Apache Spark JIRA, SPARK-23128. *Support Adaptive Execution in Spark*. Umbrella issue
  tracking the feature's staged development.
- Leis, V. et al. *How Good Are Query Optimizers, Really?*. VLDB 2015. Establishes the
  cardinality-estimation-error problem that adaptive, runtime-informed re-planning is a
  direct response to.
