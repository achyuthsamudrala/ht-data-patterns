# Spark / Batch Engine Internals

These patterns cover the internal machinery of a modern batch engine — how a logical query becomes a physical plan, how that plan becomes stages and tasks, and where the engine's automatic adaptivity helps or actively misleads.

## Reading order

[Catalyst Optimizer & Logical Plans](catalyst-optimizer.md) first — everything downstream is a transformation of that plan. Then [Stages, Tasks & the DAG Scheduler](stages-tasks-and-the-dag-scheduler.md) for how the plan becomes execution, and [Adaptive Query Execution](adaptive-query-execution.md) for how the engine revises its own plan mid-flight.

## Patterns in this section

- [Catalyst Optimizer & Logical Plans](catalyst-optimizer.md)
- [Physical Plan Selection](physical-plan-selection.md)
- [Stages, Tasks & the DAG Scheduler](stages-tasks-and-the-dag-scheduler.md)
- [Adaptive Query Execution (AQE)](adaptive-query-execution.md)
- [Memory Management](memory-management.md)
- [Speculative Execution & Stragglers](speculative-execution-and-stragglers.md)
- [Dynamic Partition Pruning](dynamic-partition-pruning.md)
- [Serialization & Tungsten](serialization-and-tungsten.md)
