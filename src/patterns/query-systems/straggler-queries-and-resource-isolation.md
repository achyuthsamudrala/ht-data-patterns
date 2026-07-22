# Straggler Queries & Resource Isolation

> **One-liner:** One query with a bad plan or hot partition can consume a disproportionate share of shared cluster resources unless isolated.

## Symptom

- A single query, badly planned or hitting a skewed partition, causes noticeably
  degraded latency for every other concurrently running query sharing the same
  cluster, even though the offending query is only one of many running.
- Killing one specific long-running, resource-heavy query immediately restores normal
  latency for all other concurrent queries, revealing that query as the sole cause of a
  cluster-wide slowdown.
- A query with an unexpectedly bad cardinality estimate (see
  [Statistics & Cardinality Estimation](../sql-execution/statistics-and-cardinality-estimation.md))
  consumes far more memory or CPU than its apparent complexity would suggest,
  crowding out concurrently scheduled queries.
- Resource usage metrics for the cluster as a whole look reasonable in aggregate, but
  per-query latency percentiles show a small number of queries taking dramatically
  longer than the rest, without an isolation mechanism to contain their impact on
  others.

## Mechanism

In a shared query cluster, resources (CPU, memory, I/O bandwidth, network) are
typically pooled across all concurrently running queries rather than strictly
partitioned per-query. This is efficient when queries are well-behaved and roughly
comparable in resource demand, but it means a single query that consumes far more
resources than expected — due to a bad plan (see
[Physical Plan Selection](../spark-internals/physical-plan-selection.md) and
[Join Ordering](../sql-execution/join-ordering.md)), a skewed partition (see
[Data Skew & Salting](../joins-and-shuffle/data-skew-and-salting.md) applied at the
query-serving level), or simply an unusually large, legitimate workload — has no
structural barrier preventing it from crowding out every other concurrent query's
share of the same pooled resources.

This is distinct from, but closely related to, the general straggler-task problem
described in [Speculative Execution & Stragglers](../spark-internals/speculative-execution-and-stragglers.md):
where that pattern concerns a single slow *task* within one job, this pattern concerns
a single slow or resource-heavy *query* affecting other, entirely unrelated queries
sharing the same cluster. The underlying mechanism (a resource imbalance concentrated
in one unit of work) is analogous, but the blast radius here spans across
tenants and workloads rather than within a single job's own tasks.

Resource isolation techniques address this by bounding how much of the shared pool any
single query can consume, regardless of how badly it's planned or how skewed its data
is. This is the query-execution-level complement to
[Query Admission Control & Workload Management](query-admission-control.md) (which
decides whether to admit a query at all) and
[Query Queueing & Fair Scheduling](query-queueing-and-fair-scheduling.md) (which decides
tenant-level resource shares): isolation operates at the level of an individual,
already-running query, capping its resource consumption so a single bad query degrades
only itself, not the whole cluster.

## Real-world sightings

Presto/Trino's per-query memory limits (both user memory and total memory limits, with
configurable behavior on exceeding them — typically killing the offending query rather
than letting it degrade others) are explicitly documented as a resource isolation
mechanism protecting cluster stability from any single misbehaving query, motivated
directly by production experience with unbounded queries destabilizing shared clusters.

The general problem of one workload's resource consumption affecting unrelated
workloads sharing infrastructure — sometimes called the "noisy neighbor" problem in
multi-tenant systems literature broadly — is a recurring theme across cloud
infrastructure and shared-cluster design, with resource isolation (cgroups, per-query
memory/CPU limits, dedicated resource pools) as the consistent class of mitigation
across contexts.

## Mitigations

### Per-query resource limits with automatic termination

**What it is:** Enforce a hard limit on memory (and optionally CPU or execution time)
per query, automatically terminating any query that exceeds it rather than allowing it
to continue consuming shared resources indefinitely.

**Cost:** A legitimate, large query that genuinely needs more resources than the limit
allows gets killed rather than completing, which requires either raising the limit for
that specific case or restructuring the query.

**How it backfires:** A limit set too conservatively kills legitimate large queries
routinely, causing operational friction and pressure to raise it; set too loosely, it
fails to actually protect against the resource-hogging scenario it was meant to
prevent.

### Isolating known-risky query patterns to dedicated resource pools

**What it is:** Route queries matching known-risky patterns (very large joins, queries
against tables with known skew issues) to a separate, isolated resource pool, so their
potential impact is contained rather than shared with the general query population.

**Cost:** Requires classifying queries by risk pattern in advance, which isn't always
possible for genuinely novel or unanticipated query shapes.

**How it backfires:** A risky-pattern classifier tuned against historically observed
risk patterns can miss a new pattern that wasn't previously problematic but becomes so
as data volume or query complexity grows.

### Monitoring per-query resource consumption relative to cluster-wide impact

**What it is:** Track individual query resource consumption as a first-class metric,
correlating spikes in cluster-wide latency with specific outlier queries, rather than
only monitoring aggregate cluster health.

**Cost:** Requires per-query resource attribution tooling, which is more
instrumentation than aggregate cluster monitoring alone.

**How it backfires:** None specific — the absence of this monitoring is itself the
failure mode: without per-query attribution, a cluster-wide slowdown is diagnosed
reactively (killing candidate queries one at a time to see if it helps) rather than
identified directly.

## Interactions

- [Query Admission Control & Workload Management](query-admission-control.md) — the
  complementary mechanism preventing a resource-heavy query from being admitted in the
  first place, rather than isolating its impact once running.
- [Speculative Execution & Stragglers](../spark-internals/speculative-execution-and-stragglers.md) —
  the analogous straggler problem at the task level within a single job, rather than
  the query level across a shared cluster.
- [Data Skew & Salting](../joins-and-shuffle/data-skew-and-salting.md) — a common
  underlying cause of a single query becoming a resource-heavy straggler relative to
  its peers.

## References

- Presto/Trino Documentation. *Resource Groups* and *Query Memory Limits*. Describes
  per-query memory limit enforcement and automatic termination behavior.
- Sethi, R. et al. (Facebook). *Presto: SQL on Everything*. ICDE 2019. Discusses
  resource isolation considerations at Facebook's production multi-tenant query
  cluster scale.
- Ananthanarayanan, G. et al. *Reining in the Outliers in Map-Reduce Clusters using
  Mantri*. OSDI 2010. Foundational discussion of outlier/straggler mitigation
  applicable to the query-level isolation problem described here.
