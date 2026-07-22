# Distributed Query Coordination

> **One-liner:** A coordinator/worker architecture centralizes planning and fan-out, which makes the coordinator both a single point of control and a single point of contention.

## Symptom

- Query latency across the entire cluster degrades simultaneously, traceable to a
  single coordinator node's CPU or memory saturation rather than to any worker.
- A coordinator restart or failure causes every in-flight query cluster-wide to fail,
  even though workers themselves remained healthy throughout.
- Query planning time (before any worker begins executing) becomes a significant
  fraction of total query latency for complex queries, disproportionate to actual
  execution time.
- Adding more worker nodes to the cluster doesn't improve overall query throughput past
  a certain point, because the coordinator itself has become the bottleneck.

## Mechanism

Distributed query engines built on a coordinator/worker (or coordinator/executor)
architecture — Presto/Trino being the canonical example — centralize query parsing,
planning, and result assembly on a coordinator node, while distributing the actual
data scanning and computation across many worker nodes. This design has clear
benefits: a single point of coordination makes consistent, cluster-wide-optimal
planning decisions possible (see
[Query Planning & Cost-Based Optimization](../sql-execution/query-planning-and-cbo.md)),
and it simplifies reasoning about query state versus a fully decentralized alternative.

The direct cost is that the coordinator becomes both a scaling bottleneck and a
single point of failure for the entire cluster's query-serving capability. Every
query's planning phase, and often result aggregation, runs on this one node
(or a small coordinator tier), meaning coordinator capacity — not aggregate worker
capacity — sets the ceiling on cluster-wide query throughput once worker capacity is no
longer the limiting factor. This is precisely the symptom of adding workers without
improving throughput: at some point, the bottleneck has moved from "not enough
workers" to "coordinator can't plan and dispatch fast enough to keep more workers
busy."

Coordinator failure has an outsized blast radius for the same reason: because query
state (which stage a query is in, its accumulated partial results) is coordinated
centrally, a coordinator failure doesn't just delay queries — for stateful coordinator
designs without external state persistence, it can require every in-flight query to
restart from scratch, since there's no other node holding the coordination state
needed to resume where the failed coordinator left off.

Query planning cost itself scales with query complexity in ways that can dominate
total latency for deeply nested or many-way-join queries (see
[Join Ordering](../sql-execution/join-ordering.md) for why planning cost grows with join
count) — for such queries, the coordinator's planning work, not the workers' execution
work, can be the larger share of total latency, which is counterintuitive given that
workers are doing the actual data processing.

## Real-world sightings

Presto's (and its fork Trino's) architecture documentation explicitly describes the
coordinator/worker split and the coordinator's role in parsing, planning, scheduling,
and result assembly, and operational guidance for running Presto/Trino at scale
consistently discusses coordinator resource sizing (CPU, memory) as a distinct,
first-class capacity-planning concern separate from worker fleet sizing — precisely
because coordinator saturation is a documented, recurring production bottleneck
distinct from worker capacity exhaustion.

High-availability coordinator designs (coordinator failover, or externalizing query
state to a separate, durable coordination store) are discussed in various distributed
query engine architectures specifically as a response to the single-point-of-failure
risk of a simple, stateful, single-coordinator design — an explicit acknowledgment
that the basic coordinator/worker model trades operational simplicity for this
availability risk.

## Mitigations

### Sizing and monitoring coordinator capacity independently from worker capacity

**What it is:** Treat coordinator CPU, memory, and network capacity as a distinct
capacity-planning dimension from worker fleet size, monitoring and scaling it based on
query volume and complexity rather than assuming worker scaling alone addresses
throughput.

**Cost:** Requires separate monitoring and alerting infrastructure specifically for
coordinator-tier health, in addition to worker-tier monitoring.

**How it backfires:** Coordinator capacity needs can grow with query *complexity*
(more joins, more subqueries) even when query *volume* stays flat, so monitoring based
only on query count can miss a coordinator capacity problem driven by query shape
changes instead.

### Coordinator high availability / failover

**What it is:** Run coordinator functionality across multiple nodes with failover
capability, or externalize critical query coordination state to a separate, durable
store, so a single coordinator failure doesn't take down all in-flight queries.

**Cost:** Adds architectural complexity and, for externalized state, adds latency for
every query's coordination operations that now have to persist state externally.

**How it backfires:** A failover mechanism that isn't regularly tested can fail
precisely when needed (during an actual coordinator outage), and externalized
coordination state introduces its own consistency and availability dependencies that
can become a new bottleneck or failure point.

### Federating planning-heavy queries to reduce coordinator load

**What it is:** For workloads with unusually complex, many-join queries, consider
query restructuring or splitting to reduce the coordinator's per-query planning
burden, rather than relying solely on coordinator hardware scaling.

**Cost:** Requires query authors or an intermediate layer to understand and act on
planning-cost characteristics, adding complexity to query authoring.

**How it backfires:** Restructuring a query to reduce planning cost can sometimes
increase execution cost (a differently-shaped query plan that's easier to plan but
less efficient to execute), trading one bottleneck for another.

## Interactions

- [Query Admission Control & Workload Management](query-admission-control.md) — a
  saturated coordinator is exactly the kind of shared resource admission control is
  meant to protect from unbounded concurrent demand.
- [Join Ordering](../sql-execution/join-ordering.md) — the specific query
  characteristic (many-way joins) that most directly drives coordinator planning cost
  up disproportionately to execution cost.
- [Straggler Queries & Resource Isolation](straggler-queries-and-resource-isolation.md) —
  a related concern about one query's resource consumption affecting others, at the
  worker level rather than the coordinator level.

## References

- Presto Documentation / Trino Documentation. *Presto/Trino Architecture Overview*.
  Describes the coordinator/worker split and coordinator responsibilities.
- Sethi, R. et al. (Facebook). *Presto: SQL on Everything*. ICDE 2019. Describes
  Presto's coordinator/worker architecture and scaling considerations at Facebook's
  production scale.
- Neumann, T. et al. *Adaptive Optimization of Very Large Join Queries*. SIGMOD 2018.
  Discusses planning cost scaling for complex, many-join queries.
