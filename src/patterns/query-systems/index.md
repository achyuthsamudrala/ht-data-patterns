# Query Systems

Query systems patterns address the distributed, multi-tenant layer above a single query's execution plan — coordination, admission, and isolation across many concurrent queries and, sometimes, many engines.

## Reading order

[Distributed Query Coordination](distributed-query-coordination.md) first, then [Query Admission Control & Workload Management](query-admission-control.md) for how a coordinator protects itself from its own concurrency.

## Patterns in this section

- [Distributed Query Coordination](distributed-query-coordination.md)
- [Query Admission Control & Workload Management](query-admission-control.md)
- [Query Federation Across Engines](query-federation.md)
- [Query Queueing & Fair Scheduling](query-queueing-and-fair-scheduling.md)
- [Result/Plan Caching](result-and-plan-caching.md)
- [Straggler Queries & Resource Isolation](straggler-queries-and-resource-isolation.md)
