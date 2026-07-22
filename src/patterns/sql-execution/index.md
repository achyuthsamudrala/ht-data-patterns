# SQL Query Execution

These patterns cover how a single query engine turns SQL into an execution plan and executes it efficiently — planning, pushdown, vectorization, and the statistics that make cost-based decisions possible.

## Reading order

[Query Planning & Cost-Based Optimization](query-planning-and-cbo.md) first, then [Statistics & Cardinality Estimation](statistics-and-cardinality-estimation.md) for the inputs that planning depends on, since a good planner fed bad statistics makes confidently wrong decisions.

## Patterns in this section

- [Query Planning & Cost-Based Optimization](query-planning-and-cbo.md)
- [Predicate & Projection Pushdown](predicate-and-projection-pushdown.md)
- [Vectorized Execution](vectorized-execution.md)
- [Columnar Storage Formats](columnar-storage-formats.md)
- [Join Ordering](join-ordering.md)
- [Statistics & Cardinality Estimation](statistics-and-cardinality-estimation.md)
