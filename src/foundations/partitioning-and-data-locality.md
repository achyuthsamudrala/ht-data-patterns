# Partitioning & Data Locality

> **The cheapest byte to process is the one that never crosses a network link.** Every
> pattern in this guide — join strategy, shuffle cost, index design, storage layout — is
> downstream of one fact: computation is nearly free relative to moving data between
> nodes, and partitioning is the mechanism that decides how much data has to move.

## What partitioning actually decides

A partition is a unit of data assigned to a unit of compute. The partitioning scheme —
the function that maps a row to a partition — determines three things simultaneously:

**Parallelism ceiling.** A job can run at most as many concurrent tasks as it has
partitions (ignoring further splitting). Ten partitions means ten-way parallelism, no
matter how many cores the cluster has free.

**Co-location.** If two datasets are partitioned by the same key with the same
partitioning function, matching rows land in the same partition on the same node. If
they aren't, matching rows are scattered across the cluster and have to be brought
together before they can be compared — that bringing-together is a shuffle.

**Skew exposure.** Partitioning is a hash or range function applied to real-world data,
and real-world data is almost never uniform. A partitioning scheme that looks balanced
on a schema diagram can put 40% of rows in one partition once it meets production key
distributions. See [Data Skew & Salting](../patterns/joins-and-shuffle/data-skew-and-salting.md).

## Locality is a spectrum, not a binary

"Data locality" is usually described as binary — local or remote — but in practice it's
a hierarchy, each level roughly an order of magnitude slower than the one above:

1. **Same process, in memory.** Nanoseconds to low microseconds.
2. **Same node, different process (shared disk/page cache).** Microseconds to low
   milliseconds.
3. **Same rack, over the network.** Low milliseconds, bandwidth shared with rack
   neighbors.
4. **Cross-rack or cross-AZ.** Milliseconds, plus the cost of crossing a network
   boundary that may itself be rate-limited or metered.
5. **Cross-region.** Tens to hundreds of milliseconds, and usually billed per byte.

A scheduler that ignores this hierarchy and places a task wherever a core is free will
work correctly — every layer above eventually serves the same bytes — but its throughput
is set by whichever level dominates the read pattern. This is why batch schedulers
(Spark, MapReduce-derived systems) bias task placement toward the node or rack holding
the input split, and why that bias erodes as clusters move to disaggregated storage
(object stores instead of co-located disks) where "local" data is a much weaker
guarantee.

## Partitioning choices and their downstream cost

**Hash partitioning** spreads rows uniformly *if* the key's hash distribution is
uniform. It gives no useful range-scan pruning — a query for `key BETWEEN 100 AND 200`
still has to touch every partition, because the hash scatters that range everywhere.

**Range partitioning** preserves order, so range predicates prune partitions
effectively. Its failure mode is temporal or naturally skewed keys: partitioning event
data by timestamp range concentrates all "today's" writes into whichever partition owns
today, turning ingest into a hot-partition problem. See
[Hot Partition Handling in Serving](../patterns/serving/hot-partition-handling.md).

**Co-partitioning** (partitioning two datasets by the same key with the same function
and the same partition count) is what makes a join shuffle-free: matching rows are
already on the same node. This is the mechanism behind
[Bucketing & Co-partitioning](../patterns/joins-and-shuffle/bucketing-and-co-partitioning.md)
— it front-loads the shuffle cost to write time, once, instead of paying it on every
query that joins the tables.

## Why this underlies the rest of the guide

Every pattern family in this guide is a consequence of the same tension: work needs to
happen where data lives, but data doesn't naturally live where work needs it.

- **Joins & Shuffle** patterns are about the cost of fixing a locality mismatch at query
  time.
- **Spark/Batch Internals** patterns are about how a scheduler tries to place tasks near
  data, and what happens when it can't.
- **Storage** patterns are about choosing an on-disk layout so that the locality
  mismatch is smaller the next time a query runs.
- **Indexing** patterns are about avoiding the need to touch most partitions at all.

None of these patterns eliminate data movement — that's not possible for any query that
combines data from more than one place. They're all strategies for moving less of it,
moving it earlier (at write time, when it's amortized over many future reads), or moving
it more cheaply (same rack instead of cross-region).

## Connections to other foundations

[The Cost Model of Shuffle](shuffle-cost-model.md) quantifies exactly what "moving data"
costs once locality is lost — network, disk spill, and serialization, each with
different scaling behavior. [Batch vs. Streaming](batch-vs-streaming-spectrum.md)
describes how the same locality tradeoffs play out when data arrives continuously
instead of as a fixed input.
