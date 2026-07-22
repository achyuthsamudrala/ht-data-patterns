# Kafka Partitioning & Consumer Groups

> **One-liner:** Partition count sets the ceiling on consumer parallelism and can't be lowered without data loss — only raised.

## Symptom

- Consumer lag grows steadily even though individual consumers show low CPU and
  network utilization — the bottleneck isn't consumer capacity, it's the number of
  partitions available to spread work across.
- Adding more consumer instances to a group beyond the topic's partition count has no
  effect on throughput; some consumers sit idle.
- Increasing partition count on an existing topic changes the assignment of keys to
  partitions for all future messages, and consumers relying on strict per-key ordering
  see order violated across the transition.
- A rebalance (a consumer joining or leaving the group) causes a visible processing
  pause across the entire consumer group, not just for the affected partitions.

## Mechanism

A Kafka topic is divided into partitions, and partition count is the hard ceiling on
how many consumers within a single consumer group can process that topic's messages in
parallel — each partition is consumed by exactly one consumer in a group at a time, so
a topic with 8 partitions can have at most 8 actively-consuming instances in one group,
regardless of how many instances are running.

This makes partition count a capacity-planning decision with an asymmetric cost:
partitions can be added later (increasing parallelism headroom), but partitions cannot
be safely removed, because Kafka's default partitioning (hash of the message key modulo
partition count) changes which partition a given key maps to whenever the partition
count changes. Increasing partition count means keys previously produced to partition N
may now map to a different partition — this breaks strict ordering guarantees for that
key across the transition, since Kafka only guarantees ordering *within* a partition,
not across partition reassignments. This is why partition count is typically set with
headroom for anticipated growth rather than tuned reactively, since growing it later has
real correctness costs for order-sensitive consumers, and shrinking it isn't a
supported operation at all (a topic's partition count can only be increased, never
decreased, without deleting and recreating it).

Consumer group rebalancing — reassigning partitions among consumers when the group's
membership changes (a consumer joins, leaves, or is considered dead by a missed
heartbeat) — has historically used a "stop-the-world" protocol in which all consumers
in the group pause processing during reassignment, meaning a single consumer's restart
or a rolling deployment can pause the entire group's throughput, not just the
partitions that consumer owned. Incremental cooperative rebalancing protocols reduce
this blast radius by reassigning only the specific partitions that need to move,
letting unaffected consumers continue processing during a rebalance.

## Real-world sightings

The original Kafka paper (Kreps, Narkhede, and Rao, "Kafka: a Distributed Messaging
System for Log Processing," LinkedIn/NetDB 2011) describes the partition-based
parallelism model and per-partition ordering guarantee as core design decisions,
directly motivating the tradeoff described above between partition count and
consumer-group parallelism.

The stop-the-world rebalancing cost and its production impact is extensively
documented in Kafka's own KIP (Kafka Improvement Proposal) process — KIP-429
("Kafka Consumer Incremental Rebalance Protocol") explicitly describes the pre-existing
eager rebalancing protocol's full-group-pause behavior as a production pain point
motivating the incremental cooperative rebalancing alternative, which reassigns only
the specific partitions that changed ownership.

## Mitigations

### Provisioning partition count with growth headroom

**What it is:** Set a topic's partition count higher than current throughput strictly
requires, anticipating future consumer-group scale-out without needing a partition
count increase later.

**Cost:** More partitions means more open file handles and replication overhead on
brokers, and more per-partition consumer-side bookkeeping, even when not all partitions
are needed yet.

**How it backfires:** Overprovisioning partitions "just in case" for a topic that never
actually grows into that headroom wastes broker resources indefinitely, and the
headroom chosen today can still turn out to be wrong in either direction as actual
growth unfolds.

### Incremental cooperative rebalancing

**What it is:** Use a rebalancing protocol that reassigns only the specific partitions
affected by a membership change, rather than pausing the entire consumer group.

**Cost:** Requires a compatible consumer/broker version and correct configuration;
older or misconfigured clients fall back to the full-pause behavior.

**How it backfires:** Cooperative rebalancing reduces pause blast radius but doesn't
eliminate rebalance cost entirely — a consumer group experiencing frequent membership
churn (flapping instances, aggressive autoscaling) still pays rebalancing overhead
repeatedly, just with a smaller footprint each time.

### Key design that tolerates partition-count changes

**What it is:** Design message keys and downstream consumer logic to not depend on
strict, global cross-partition ordering, so a partition count increase doesn't silently
break correctness.

**Cost:** Requires giving up strict ordering guarantees that a naive key scheme with
a fixed partition count would otherwise provide, which not every downstream consumer can
tolerate.

**How it backfires:** A consumer built assuming order-independence can develop subtle
bugs if a later requirement (e.g., strict event sequencing for a specific key)
re-introduces an ordering dependency without revisiting the partitioning scheme's
tolerance for change.

## Interactions

- [Backpressure in Streaming](backpressure-in-streaming.md) — undersized partition
  count is one of the most common root causes of consumer lag that backpressure
  mechanisms alone cannot fix, since the parallelism ceiling is structural, not a
  throttling problem.
- [Stateful Processing & State Stores](stateful-processing-and-state-stores.md) — a
  rebalance that moves partition ownership between consumers also moves ownership of
  any partition-keyed state, forcing state migration or reconstruction.
- [Partitioning & Data Locality](../../foundations/partitioning-and-data-locality.md) —
  the general co-location principle this pattern applies specifically to Kafka's
  partition/consumer-group model.

## References

- Kreps, J., Narkhede, N., and Rao, J. *Kafka: a Distributed Messaging System for Log
  Processing*. NetDB 2011. The original Kafka design paper describing partition-based
  parallelism and ordering guarantees.
- Apache Kafka KIP-429. *Kafka Consumer Incremental Rebalance Protocol*. Documents the
  stop-the-world rebalancing cost and the cooperative rebalancing alternative.
- Apache Kafka Documentation. *Consumer Groups and Partition Assignment*. Official
  reference for partition-to-consumer assignment and rebalancing behavior.
