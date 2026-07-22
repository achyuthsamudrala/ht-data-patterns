# Speculative Execution & Stragglers

> **One-liner:** Re-running slow tasks speculatively hides stragglers from data skew but can mask the underlying cause and double the cost.

## Symptom

- One task in a stage runs substantially longer than its peers, and a duplicate copy of
  that task appears running concurrently elsewhere in the cluster.
- Cluster resource usage (CPU, executor-hours) is higher than the job's useful work
  would suggest, traceable to duplicated speculative task attempts.
- A straggler that speculative execution successfully "fixes" (the duplicate finishes
  first) recurs on every run of the same job, at the same stage, without ever being
  investigated as a root cause.
- Speculative execution is enabled cluster-wide, and jobs with genuinely skewed data
  show no improvement despite duplicated task attempts.

## Mechanism

A straggler is a task that takes substantially longer than its peers in the same
stage. Speculative execution is a scheduler-level mitigation: if a task is running
much slower than the median for its stage, the scheduler launches a duplicate copy on a
different executor, and whichever copy finishes first "wins" — the other is killed.

This is an effective, general mitigation for stragglers caused by **infrastructure
heterogeneity or transient host issues**: a node experiencing unusual contention (noisy
neighbor, hardware degradation, transient network issue) will produce a slow task
purely because of where it happened to run, and a duplicate on different hardware will
usually finish faster, with no changes to the underlying data or algorithm.

It is not an effective mitigation for stragglers caused by **data skew** (see
[Data Skew & Salting](../joins-and-shuffle/data-skew-and-salting.md)): if a task is
slow because its partition genuinely contains far more data than its peers' partitions
(a hot key), a duplicate copy of that same task, processing the same oversized
partition, on any other node, will be equally slow. Speculative execution in this case
doesn't fix anything — it merely doubles the cluster resources consumed for the same,
unchanged runtime, because the bottleneck was never about which node ran the task.

This distinction matters operationally because both cases present identically in a
dashboard: one task, much slower than its peers. Distinguishing them requires looking
at what the task is actually doing — bytes processed relative to peer tasks (skew) versus
CPU/network/disk metrics on the host it ran on relative to other hosts (infrastructure
straggler) — rather than relying on speculative execution's blanket duplicate-and-race
behavior to resolve either case automatically.

## Real-world sightings

The original MapReduce paper (Dean and Ghemawat, OSDI 2004) introduced speculative
execution as a general straggler mitigation and explicitly discussed its limits: it
noted that speculative execution helps with machine-level slowness but that other
causes of slow tasks (algorithmic or data-related) are not addressed by re-running the
same work elsewhere — an observation that has held for every MapReduce-lineage
execution engine since, including Spark.

Spark's own documentation and numerous production engineering write-ups distinguish
"true" stragglers (fixable by speculative execution) from skew-induced slow tasks
(requiring salting, AQE's skew-join handling, or repartitioning) as a standard
diagnostic step, generally recommending speculative execution be evaluated and tuned
independently of — not as a substitute for — addressing key skew directly.

## Mitigations

### Enabling speculative execution for infrastructure heterogeneity

**What it is:** Turn on speculative execution to duplicate and race tasks that are
statistical outliers within their stage, catching genuinely slow-node cases
automatically.

**Cost:** Doubles resource consumption for every task that triggers speculation,
whether or not the duplicate actually helps.

**How it backfires:** On a cluster where skew is the dominant cause of stragglers,
speculative execution consumes extra resources on every skewed run without improving
wall-clock time at all — it's pure overhead for that failure mode.

### Diagnosing straggler cause before choosing a mitigation

**What it is:** Check whether a slow task's *data volume* is disproportionate to its
peers (skew) versus whether the *host* it ran on shows anomalous resource metrics
(infrastructure) before applying speculative execution or salting.

**Cost:** Requires operational tooling and practice to distinguish the two causes
quickly, rather than reaching for a single default mitigation.

**How it backfires:** Under time pressure during an incident, this diagnostic step is
often skipped in favor of "just enable speculation and see if it helps" — which,
for a skew-caused straggler, wastes the incident-response window on a mitigation that
was never going to work.

### Addressing skew directly rather than relying on speculation

**What it is:** For data-skew-induced stragglers, apply salting or AQE's skew-join
handling (see [Data Skew & Salting](../joins-and-shuffle/data-skew-and-salting.md))
instead of, or in addition to, speculative execution.

**Cost:** Requires identifying the specific skewed key(s), which is more investigative
work than flipping a cluster-wide speculation flag.

**How it backfires:** None specific to this mitigation — the risk is entirely in
*not* doing this and relying on speculative execution as a substitute, which is the
failure mode this entire pattern page describes.

## Interactions

- [Data Skew & Salting](../joins-and-shuffle/data-skew-and-salting.md) — the primary
  case where speculative execution does not help, and where the two are commonly
  conflated.
- [Stages, Tasks & the DAG Scheduler](stages-tasks-and-the-dag-scheduler.md) — a
  straggler task blocks its entire stage from completing, which blocks every downstream
  stage, magnifying one slow task's effect on total job time.
- [Straggler Queries & Resource Isolation](../query-systems/straggler-queries-and-resource-isolation.md) —
  the same straggler concept applied at the level of a whole query competing for shared
  cluster resources, rather than a single task within one job.

## References

- Dean, J. and Ghemawat, S. *MapReduce: Simplified Data Processing on Large Clusters*.
  OSDI 2004. Introduces speculative execution and explicitly scopes its effectiveness
  to machine-level slowness.
- Apache Spark Documentation. *Configuration — Scheduling*. Describes speculative
  execution configuration flags and their intended use case.
- Ananthanarayanan, G. et al. *Reining in the Outliers in Map-Reduce Clusters using
  Mantri*. OSDI 2010. Extends straggler mitigation beyond blind speculation, explicitly
  distinguishing skew-caused stragglers from resource-contention-caused ones.
