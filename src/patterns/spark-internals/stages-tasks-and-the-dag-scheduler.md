# Stages, Tasks & the DAG Scheduler

> **One-liner:** Shuffle boundaries split a job into stages; understanding that boundary explains most Spark UI confusion.

## Symptom

- The execution UI shows more stages than there are visible steps in the job's code,
  and it's unclear what triggered the split.
- A job "hangs" between two stages with no visible task activity, and it isn't obvious
  which stage is actually blocking progress.
- Re-running a failed job re-executes far more work than the single operation that
  failed, sometimes recomputing stages that had already completed successfully.
- Increasing the number of executors doesn't reduce a job's wall-clock time, even
  though the job clearly has parallel work available.

## Mechanism

A batch job is represented internally as a directed acyclic graph (DAG) of
transformations. The DAG scheduler's central job is deciding where that graph must be
split into **stages**: every point where a shuffle is required (data must be
repartitioned across nodes — see
[Partitioning & Data Locality](../../foundations/partitioning-and-data-locality.md))
becomes a stage boundary, because all of a stage's output must be available before the
next stage can begin reading it in its new partitioning.

Within a stage, work is divided into **tasks** — one task per partition, each an
independent unit that can run on any available executor without coordinating with other
tasks in the same stage. This is what makes a stage parallelizable: tasks within it
have no data dependency on each other. Tasks in different stages, by contrast, have a
strict dependency — a stage cannot begin until its upstream stage's shuffle output is
fully written, because any task in the new stage might need data from any task in the
old one.

This structure explains the three most common sources of confusion in execution UIs.
**More stages than code suggests**: any operation implying repartitioning (a `groupBy`,
a join between differently-partitioned datasets, an explicit `repartition()`) inserts a
new stage boundary that isn't visually obvious from a linear reading of the code.
**Apparent hangs between stages**: a stage cannot start until the *entire* upstream
stage's output is ready — if a single upstream task is a straggler (see
[Speculative Execution & Stragglers](speculative-execution-and-stragglers.md)), every
task in the next stage waits on it, showing as "no progress" even though most of the
prior stage completed quickly. **Re-executing more than the failed step**: an RDD's
lineage (the DAG of transformations that produced it) determines what must be recomputed
on failure — if intermediate output wasn't persisted, recovering from a failure deep in
the DAG can require recomputing every upstream stage, not just retrying the failed task
in isolation.

## Real-world sightings

The stage/task/DAG scheduler model is described in the original Spark paper (Zaharia et
al., "Resilient Distributed Datasets," NSDI 2012), which frames stage boundaries
explicitly around "narrow" (no shuffle, pipelineable within a stage) versus "wide"
(shuffle-requiring, stage-boundary-inducing) dependencies — a distinction that remains
the conceptual foundation for how Spark's execution UI presents jobs today.

This stage/task model, and the confusion around implicit stage boundaries from
operations like `groupBy` or unbalanced joins, is one of the most frequently addressed
topics in Spark troubleshooting guides and vendor documentation (Databricks, AWS EMR),
usually framed as "why does my job have more stages than steps in my code" — a direct
consequence of shuffle-inducing operations not being visually distinguished from
narrow, pipelined ones in typical DataFrame/SQL code.

## Mitigations

### Reading the DAG visualization before assuming linear execution

**What it is:** Use the execution UI's stage/DAG visualization to identify actual
shuffle boundaries, rather than inferring stage structure from source code structure.

**Cost:** Requires operational familiarity with the specific engine's UI, which is a
skill that atrophies on teams that treat job execution as opaque.

**How it backfires:** The DAG view shows what happened for *this run*; a plan chosen
adaptively (see [Adaptive Query Execution (AQE)](adaptive-query-execution.md)) can
differ between runs with different data volumes, so a DAG snapshot from one run isn't
guaranteed to represent the next.

### Persisting intermediate results at natural checkpoints

**What it is:** Explicitly cache or checkpoint intermediate results at points in a long
DAG where recomputation on failure would otherwise be expensive, trading storage for
reduced recovery cost.

**Cost:** Persisted data consumes memory or disk, and choosing checkpoint points
requires understanding where in the lineage recomputation would actually be expensive.

**How it backfires:** Over-checkpointing adds I/O overhead to the happy path (writing
data that's never actually needed for recovery) without a corresponding reduction in
recovery cost, since not every stage boundary is expensive to recompute.

### Minimizing unnecessary shuffle-inducing operations

**What it is:** Restructure a pipeline to avoid `groupBy`, `repartition`, or
differently-partitioned joins where they aren't strictly necessary, reducing the number
of stage boundaries.

**Cost:** Sometimes a shuffle is the correct, necessary way to express a computation;
avoiding it at all costs can produce a more convoluted, harder-to-maintain pipeline for
a marginal performance gain.

**How it backfires:** A pipeline restructured to minimize shuffle for today's query
pattern can require reintroducing shuffle boundaries when the query pattern changes,
undoing the restructuring's benefit.

## Interactions

- [Speculative Execution & Stragglers](speculative-execution-and-stragglers.md) — a
  single straggler task blocks its entire stage's completion, which blocks the next
  stage from starting, magnifying one slow task's effect on total wall-clock time.
- [Shuffle Partitioning Strategy](../joins-and-shuffle/shuffle-partitioning-strategy.md) —
  stage boundaries are exactly where partition count decisions take effect.
- [Checkpointing & Fault Tolerance](../streaming/checkpointing-and-fault-tolerance.md) —
  the batch DAG lineage-recomputation model and the streaming checkpoint-based recovery
  model solve the same problem (recovering from failure without redoing all prior work)
  with structurally different mechanisms.

## References

- Zaharia, M. et al. *Resilient Distributed Datasets: A Fault-Tolerant Abstraction for
  In-Memory Cluster Computing*. NSDI 2012. Defines narrow vs. wide dependencies and the
  stage-boundary model still used today.
- Apache Spark Documentation. *Cluster Mode Overview* and *Job Scheduling*. Describes
  the DAG scheduler's stage-splitting and task-scheduling behavior.
- Databricks Engineering Blog. *A Deep Dive into Spark SQL's Physical Planning and
  Execution*. Practitioner-facing explanation of stage boundaries in the execution UI.
