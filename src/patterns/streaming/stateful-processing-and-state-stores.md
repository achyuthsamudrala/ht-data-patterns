# Stateful Processing & State Stores

> **One-liner:** Stream processors that maintain state (aggregations, joins) turn a data problem into a database problem, with its own compaction and recovery costs.

## Symptom

- A streaming job's state store grows continuously, and neither natural key expiry nor
  configured TTLs are actually bounding its size.
- Recovery after a failure takes far longer than expected, traceable to reloading a very
  large state store from its backing checkpoint rather than to reprocessing input data.
- A rebalance that moves partition ownership between consumers causes a visible latency
  spike, because the receiving consumer has to reconstruct or fetch the state associated
  with its newly assigned partitions before it can resume processing.
- State store disk usage grows faster than the logical data it represents would suggest,
  traceable to compaction falling behind on an LSM-based local state store.

## Mechanism

Many streaming operations are inherently stateful: a running aggregate (count, sum,
average) needs to remember its accumulated value across events; a stream-stream join
needs to remember one side's events long enough to match arriving events on the other
side; deduplication needs to remember which keys have already been seen. This state has
to persist across events, survive process restarts, and — because a single logical key's
state should live wherever that key's partition is currently owned — move when
partition ownership moves during a rebalance.

Modern stream processors (Flink, Kafka Streams, Spark Structured Streaming) typically
implement state stores using an embedded, per-partition local database, often backed by
an LSM-tree-based engine (see [B-Tree vs. LSM-Tree Tradeoffs](../indexing/btree-vs-lsm-tree.md)),
because LSM engines' write-optimized design suits the high write rate of continuously
updated aggregation state well. This choice inherits LSM's own operational
characteristics directly: state stores need their own compaction, and a state store
whose compaction falls behind its write rate accumulates the same kind of
write-amplification debt any LSM-based system does under those conditions.

Recovery and rebalancing both interact with state size directly. On recovery from a
failure, a state store has to be reconstructed — either by replaying the underlying
change log from the last checkpoint, or by restoring a snapshot and replaying only the
delta — and the time this takes scales with state size, not with the size of new input
data since the failure. On rebalance, if a partition's state isn't already replicated to
or fetchable by the consumer taking over that partition, that consumer has to
reconstruct the state (often by replaying a change-log topic) before it can safely
resume processing that partition, producing a visible latency gap proportional to that
partition's state size.

Without TTL or an explicit eviction policy, state that logically should expire (a
deduplication window, a session that's genuinely over) doesn't — it simply accumulates,
because the stream processor has no independent signal that a given key's state is no
longer needed unless the application explicitly configures one.

## Real-world sightings

Kafka Streams' documentation on state stores and standby replicas describes exactly
this tradeoff: state stores are backed by RocksDB (an LSM-based embedded store)
specifically for its write throughput characteristics, and the documentation explicitly
recommends standby replicas (pre-warmed copies of a partition's state on a second
consumer) as a mitigation for the rebalance-time state reconstruction latency described
above — trading additional storage and replication cost for faster failover and
rebalance recovery.

Flink's documentation on state backends and incremental checkpointing similarly
describes RocksDB-backed state and its own compaction behavior as a first-class
operational concern, and Flink's incremental checkpoint mechanism (checkpointing only
the state that changed since the last checkpoint, rather than a full snapshot every
time) is explicitly motivated by the observation that full-state checkpointing cost
scales with total state size, which becomes prohibitive as state grows large relative
to the rate of change within it.

## Mitigations

### TTL and explicit state eviction policies

**What it is:** Configure explicit time-to-live or eviction policies for state that has
a natural expiry (a deduplication window, a session past its inactivity gap), so state
size is bounded by design rather than growing until manually addressed.

**Cost:** Requires the application to correctly identify and configure appropriate TTLs
per state type, which isn't always obvious for state whose "natural" lifetime is
business-logic-dependent.

**How it backfires:** A TTL set too aggressively evicts state a later event still
needed (a legitimately delayed but relevant continuation), producing subtly incorrect
results (treated as a "new" entity rather than a continuation) rather than an obvious
failure.

### Standby replicas for faster rebalance recovery

**What it is:** Maintain a pre-warmed, replicated copy of a partition's state on a
secondary consumer, so a rebalance can hand off processing without a full state
reconstruction delay.

**Cost:** Doubles (or more) the storage and replication overhead for state that's being
kept warm on standby instances that aren't actively processing.

**How it backfires:** Standby replication itself consumes resources continuously
(replication traffic, storage) whether or not a rebalance ever actually occurs — it's a
cost paid for a contingency, and sizing how many standbys are worth maintaining is a
real tradeoff against steady-state resource cost.

### Incremental checkpointing

**What it is:** Checkpoint only the state that changed since the last checkpoint rather
than a full snapshot every time, keeping checkpoint cost proportional to change rate
rather than total state size.

**Cost:** Incremental checkpoints depend on a chain of prior checkpoints for full
recovery, so losing an earlier checkpoint in the chain can force a more expensive full
rebuild.

**How it backfires:** Incremental checkpoint chains that grow very long without a
periodic full checkpoint can make recovery slower in aggregate (replaying many small
increments) than a well-timed full snapshot would have been.

## Interactions

- [B-Tree vs. LSM-Tree Tradeoffs](../indexing/btree-vs-lsm-tree.md) — most state store
  implementations are LSM-based internally, and inherit LSM's compaction and
  write-amplification behavior directly.
- [Checkpointing & Fault Tolerance](checkpointing-and-fault-tolerance.md) — state store
  recovery is a direct consumer of whatever checkpointing strategy the pipeline uses.
- [Kafka Partitioning & Consumer Groups](kafka-partitioning-and-consumer-groups.md) — a
  rebalance event, triggered by consumer group membership changes, is exactly what
  forces state migration or reconstruction between consumers.

## References

- Apache Kafka Streams Documentation. *Streams DSL — State Stores*. Describes
  RocksDB-backed state stores and standby replica configuration for rebalance
  resilience.
- Apache Flink Documentation. *State Backends* and *Incremental Checkpointing*.
  Describes RocksDB state backend behavior and the design motivation for incremental
  checkpoints.
- O'Neil, P. et al. *The Log-Structured Merge-Tree (LSM-Tree)*. Acta Informatica, 1996.
  The foundational design most embedded state store engines (RocksDB and similar)
  build on.
