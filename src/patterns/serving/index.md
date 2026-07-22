# Serving Systems

Serving patterns address what happens when data produced by batch or streaming pipelines must be served back with low latency — a workload shape the storage and processing layers underneath were rarely designed for.

## Reading order

[Point Lookups vs. Analytical Scans](point-lookups-vs-analytical-scans.md) first — it's the fundamental tension in serving-layer design. Then [OLAP Serving Layer](olap-serving-layer.md) for how pre-aggregation resolves it.

## Patterns in this section

- [OLAP Serving Layer](olap-serving-layer.md)
- [Point Lookups vs. Analytical Scans](point-lookups-vs-analytical-scans.md)
- [Read Replicas & Staleness](read-replicas-and-staleness.md)
- [Feature Store Serving](feature-store-serving.md)
- [Result/Query Caching](result-and-query-caching.md)
- [Hot Partition Handling in Serving](hot-partition-handling.md)
