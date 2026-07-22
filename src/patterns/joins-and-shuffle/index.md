# Joins & Shuffle

Join and shuffle patterns address the failure modes that emerge when data must move across the network to be combined. The meta-pattern: a join plan that's correct on sampled data can be catastrophically wrong at full scale, because shuffle cost and skew don't show up until the data does.

## Reading order

[Broadcast vs. Shuffle Join](broadcast-vs-shuffle-join.md) first — it's the fork in the road every join planner makes. Then [Data Skew & Salting](data-skew-and-salting.md) for the most common way shuffle joins go wrong in production, and [Spill to Disk](spill-to-disk.md) for what happens when a shuffle exceeds memory.

## Patterns in this section

- [Broadcast vs. Shuffle Join](broadcast-vs-shuffle-join.md)
- [Sort-Merge vs. Shuffle-Hash Join](sort-merge-vs-shuffle-hash-join.md)
- [Data Skew & Salting](data-skew-and-salting.md)
- [Spill to Disk](spill-to-disk.md)
- [Shuffle Partitioning Strategy](shuffle-partitioning-strategy.md)
- [Bucketing & Co-partitioning](bucketing-and-co-partitioning.md)
- [Shuffle Service Internals](shuffle-service-internals.md)
