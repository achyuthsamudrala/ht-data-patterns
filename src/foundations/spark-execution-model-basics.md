# Spark Execution Model Basics

> **Nothing runs until an action is called — everything before that is just a
> description of work.** Spark's execution model separates *declaring* a computation
> (transformations, building a lazy DAG) from *running* it (actions, which trigger
> planning and execution). Most of the confusion new Spark users hit traces back to
> not distinguishing these two phases.

## RDDs, DataFrames, and what they have in common

An RDD (Resilient Distributed Dataset) is Spark's original core abstraction: an
immutable, partitioned collection of records, distributed across a cluster, with
enough recorded lineage (the sequence of transformations that produced it) to
reconstruct any lost partition by recomputing it from its inputs rather than requiring
replication for fault tolerance.

DataFrames and Datasets are higher-level APIs built on top of this same execution
substrate: instead of describing computation as arbitrary functions over opaque
records, they describe it as relational operations (select, filter, join, aggregate)
over structured, schema-aware data. This structure is exactly what makes
[Catalyst](../patterns/spark-internals/catalyst-optimizer.md) possible — a DataFrame
query can be analyzed, rewritten, and cost-optimized before execution in ways an
arbitrary RDD lambda cannot, because the engine can reason about relational operations
symbolically. In modern Spark, the DataFrame/SQL API is the default interface, and it
compiles down to the same RDD-based (or, more precisely, Tungsten binary-encoded)
execution underneath.

## Transformations are lazy; actions trigger execution

Operations on an RDD or DataFrame fall into two categories. **Transformations**
(`filter`, `select`, `join`, `groupBy`, `map`) build up a description of computation —
a lineage graph — without touching any actual data. Calling `.filter(...)` doesn't
scan anything; it records "the result of filtering this DataFrame" as a new node in a
plan.

**Actions** (`count`, `collect`, `write`, `show`) are what actually trigger execution:
only when an action is called does Spark analyze the accumulated transformation graph,
optimize it, and dispatch real work to the cluster. This laziness is deliberate — it
lets the optimizer see the *entire* chain of transformations before committing to an
execution plan, rather than executing each transformation eagerly and losing the
opportunity to, for instance, push a late filter earlier in the chain (see
[Predicate & Projection Pushdown](../patterns/sql-execution/predicate-and-projection-pushdown.md)).

The practical consequence: a bug in a transformation (a malformed filter expression, a
reference to a nonexistent column) often doesn't surface until a much later line of
code calls an action — the error's *location* in a stack trace can be far from its
actual *cause* in the source code, because nothing ran until the action forced it to.

## Driver, executors, and the cluster manager

A running Spark application has three distinct roles. The **driver** runs the
application's main program, builds the transformation DAG as API calls are made,
and — once an action triggers execution — converts that DAG into
[stages and tasks](../patterns/spark-internals/stages-tasks-and-the-dag-scheduler.md)
and schedules them across the cluster. The driver is a single process; if it fails,
the whole application fails, which is why driver resource sizing and stability matter
disproportionately to its single-node footprint.

**Executors** are the worker processes that actually run tasks and hold data in memory
or on disk — including cached DataFrames (see
[Memory Management](../patterns/spark-internals/memory-management.md)) and shuffle
output (see [The Cost Model of Shuffle](shuffle-cost-model.md)). Executors are
distributed across the cluster and are individually replaceable — losing one executor
means recomputing or refetching its lost data, not losing the whole application.

The **cluster manager** (YARN, Kubernetes, or Spark's own standalone mode) is
responsible for allocating the actual machine resources (containers, pods) that
executors and the driver run in, independent of Spark's own scheduling logic — Spark
asks the cluster manager for resources, and the cluster manager decides where and
whether they're available.

## Why this matters for reading the rest of the guide

Nearly every pattern in the [Joins & Shuffle](../patterns/joins-and-shuffle/index.md)
and [Spark/Batch Engine Internals](../patterns/spark-internals/index.md) families
assumes this mental model as a starting point: a "stage" is a unit of the DAG between
shuffle boundaries, a "task" is one partition's worth of work within a stage, and
"the planner" refers to the process — triggered by an action, running on the driver —
that turns a lazy transformation graph into a concrete, schedulable set of stages and
tasks. Without this baseline, terms like "shuffle boundary" or "driver OOM" don't have
a clear referent.

## Connections to other foundations

[The Cost Model of Shuffle](shuffle-cost-model.md) describes what happens at the
specific points in this execution model where a transformation requires
repartitioning data across executors. [Batch vs. Streaming Spectrum](batch-vs-streaming-spectrum.md)
describes how this same lazy-transformation-then-action model is adapted (via
micro-batches or continuous processing) when the input is unbounded rather than fixed.
