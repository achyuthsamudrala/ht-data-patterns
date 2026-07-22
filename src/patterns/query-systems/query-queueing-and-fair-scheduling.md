# Query Queueing & Fair Scheduling

> **One-liner:** Without per-tenant fairness, one tenant's expensive queries can starve every other tenant sharing the same query cluster.

## Symptom

- A single team or tenant submitting a burst of expensive queries causes noticeable
  latency degradation for every other tenant sharing the same query cluster, even
  though the cluster's aggregate utilization doesn't look unreasonably high.
- Queries from a low-volume tenant experience inconsistent, unpredictable queuing
  delay depending entirely on what other tenants happen to be running at the same
  moment, with no isolation between their workloads.
- A scheduling policy that treats all queries identically (simple FIFO) lets a handful
  of very large, long-running queries monopolize execution slots, delaying many
  smaller, faster queries that could otherwise have completed quickly.
- After introducing per-tenant fair scheduling, one tenant's workload — previously
  fast, because it happened to run when the cluster was underutilized — becomes
  noticeably slower under its now-enforced fair share, revealing that its prior
  performance was borrowed capacity, not guaranteed capacity.

## Mechanism

A shared query cluster serving multiple tenants (teams, applications, business units)
faces a scheduling problem structurally identical to any shared-resource
multitenancy problem: without an explicit fairness policy, whichever tenant submits
the most or largest queries consumes the most resources, and there's no guarantee this
correlates with that tenant's actual priority or entitlement — it's simply a function
of who happened to ask for the most.

Simple FIFO (first-in-first-out) scheduling treats query order as the only priority
signal, which fails specifically when query *size* varies widely: a large, expensive
query queued ahead of several small, cheap ones forces all of them to wait for the
large query's full duration, even though serving the small queries first (or
interleaving them) would have let far more total queries complete in the same wall-clock
time — this is the same head-of-line-blocking problem that motivates priority and
size-aware scheduling in any shared queue-based system.

Fair scheduling policies (weighted fair queuing, or explicit per-tenant resource
quotas) address this by allocating a defined share of cluster capacity to each tenant
or workload class, ensuring one tenant's demand surge can consume, at most, that
tenant's allocated share rather than an unbounded fraction of total capacity. The
tradeoff this introduces is visible in the last symptom above: a tenant whose workload
previously ran fast by opportunistically using *other* tenants' unused capacity will,
under enforced fairness, be constrained to its own guaranteed share even when other
capacity happens to be idle — unless the fairness policy specifically supports
work-conserving behavior (using idle capacity from other tenants' unused shares when
available, while still guaranteeing each tenant's own share when contested).

Getting this right requires distinguishing *guaranteed* capacity (what a tenant can
always count on) from *opportunistic* capacity (extra throughput available only when
others aren't using their share) — a policy that conflates the two either
under-utilizes the cluster (strict per-tenant caps that leave capacity idle when unused
by its owner) or under-protects tenants (no strict floor, so heavy contention still
degrades everyone proportionally rather than protecting each tenant's fair minimum).

## Real-world sightings

Apache Hadoop YARN's Fair Scheduler and Capacity Scheduler, and analogous features in
Presto/Trino's and Apache Impala's resource group implementations, explicitly document
weighted, per-tenant or per-queue resource allocation as a response to exactly this
problem — unmanaged shared clusters where one workload's demand degrades others'
performance unpredictably — and both explicitly support work-conserving behavior
(borrowing idle capacity from underutilized queues) as a deliberate design feature
rather than strict, always-enforced per-tenant caps.

The general fair-queuing problem long predates big-data query systems specifically —
weighted fair queuing algorithms originate in network packet scheduling literature
(Demers, Keshav, and Shenker's foundational work on fair queuing) and the same
underlying algorithmic approach (allocating shares proportional to weight, with
work-conserving borrowing) has been adapted across many shared-resource scheduling
domains, including the query-cluster scheduling context described here.

## Mitigations

### Weighted, work-conserving fair scheduling

**What it is:** Allocate per-tenant resource shares proportional to configured weights,
while allowing tenants to opportunistically use other tenants' unused capacity when
available, reverting to strict shares under contention.

**Cost:** Requires a scheduler implementation supporting this more sophisticated
allocation model, rather than a simple static-quota or FIFO approach.

**How it backfires:** Tenants that grow accustomed to opportunistic extra capacity
(because contention has historically been low) can experience a sharp, surprising
performance regression the first time genuine contention occurs and enforcement falls
back to strict per-tenant shares.

### Size-aware or shortest-job-oriented scheduling within fairness constraints

**What it is:** Within a given tenant's or queue's allocation, prioritize smaller,
faster queries over larger ones where possible, reducing head-of-line blocking from
large queries without violating overall fairness across tenants.

**Cost:** Requires reasonably accurate query size/cost estimation (inheriting the same
estimation fragility as admission control — see
[Query Admission Control & Workload Management](query-admission-control.md)) to make
size-aware scheduling decisions correctly.

**How it backfires:** Systematically de-prioritizing large queries in favor of small
ones can starve large queries indefinitely if small-query arrival is continuous, unless
an aging mechanism guarantees large queries eventually get scheduled regardless of
ongoing small-query arrival.

### Periodically re-evaluating per-tenant weight allocations

**What it is:** Revisit tenant weight or quota allocations periodically based on actual,
evolving business priority and usage patterns, rather than treating an initial
allocation as permanent.

**Cost:** Requires an ongoing governance process to review and adjust allocations,
which is easy to let lapse once initially configured.

**How it backfires:** An allocation left unrevisited for a long period can become
badly mismatched to actual current business priority, either over-provisioning a
tenant whose importance has declined or under-provisioning one whose importance has
grown.

## Interactions

- [Query Admission Control & Workload Management](query-admission-control.md) — the
  complementary mechanism deciding whether a query is admitted at all, before fair
  scheduling determines when an admitted query actually runs.
- [Straggler Queries & Resource Isolation](straggler-queries-and-resource-isolation.md) —
  a related concern about isolating one query's resource consumption from others,
  operating at the level of individual query execution rather than tenant-level
  scheduling.
- [Distributed Query Coordination](distributed-query-coordination.md) — the
  coordinator is typically where fair scheduling decisions are made and enforced
  across the cluster.

## References

- Demers, A., Keshav, S., and Shenker, S. *Analysis and Simulation of a Fair Queuing
  Algorithm*. SIGCOMM 1989. Foundational fair queuing algorithm underlying much
  weighted, work-conserving resource scheduling.
- Apache Hadoop Documentation. *Fair Scheduler* and *Capacity Scheduler*. Describes
  practical weighted, work-conserving per-tenant resource allocation for shared
  clusters.
- Presto/Trino Documentation. *Resource Groups*. Describes per-tenant/per-queue
  scheduling policy configuration for a distributed query engine.
