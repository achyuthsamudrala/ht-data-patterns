# Consistency Models for Distributed Data

> **Consistency is a spectrum you choose per operation, not a property a system has.**
> "Strongly consistent" and "eventually consistent" describe the ends of a range of
> guarantees about what a reader can see after a writer has written — and most
> production incidents in this space come from an operation quietly landing on a
> different point of that spectrum than the caller assumed.

## The guarantee, precisely

A consistency model answers one question: after a write completes, what can a
subsequent read observe, and under what conditions? The answer has to account for
concurrent writers, replica lag, and network partitions, because in a distributed
system all three are normal operating conditions, not failure modes.

**Strong (linearizable) consistency** — every read observes the most recent write, as if
there were only one copy of the data. This requires coordination on every operation
(consensus, or routing all reads/writes through a single leader), which caps throughput
at what that coordination point can handle and adds latency equal to at least one
network round-trip to establish agreement.

**Eventual consistency** — replicas converge to the same value *given no further
writes and enough time*, with no bound on how long "enough time" is under load. Reads
can return stale data indefinitely while writes are still propagating. This buys
availability and throughput at the cost of a staleness window that the caller must
either tolerate or explicitly work around.

**Read-your-writes** — a specific, weaker guarantee than strong consistency: a client
that just wrote a value will see that value (or a newer one) on its own subsequent
reads, even if other clients might still see stale data. This is usually implemented by
routing a client's reads to whichever replica handled its last write, or by version
stamping and rejecting reads that are behind the client's last known write.

**Causal consistency** — writes that are causally related (B was written after reading
A) are observed in that order by every reader; unrelated writes may be observed in any
order. This is strong enough to avoid most "that update showed up out of order"
confusion without paying for full linearizability.

## Why this belongs in a data-platform foundations page

Every pattern family in this guide makes an implicit consistency choice, usually without
naming it:

- **Storage replication** — [Replication & Erasure Coding](../patterns/storage/replication-and-erasure-coding.md)
  trades write latency (wait for N replicas to ack) against read consistency
  (how many replicas must agree before a read is trustworthy).
- **Serving read replicas** — [Read Replicas & Staleness](../patterns/serving/read-replicas-and-staleness.md)
  is eventual consistency applied to a serving layer, and the incident it produces is
  always the same shape: a caller assumed read-your-writes and got staleness instead.
- **Streaming delivery guarantees** — [Exactly-Once Semantics](../patterns/streaming/exactly-once-semantics.md)
  is really a consistency claim about the *output* of a pipeline under replay and
  failure, not about delivery of individual messages.
- **Query federation** — [Query Federation Across Engines](../patterns/query-systems/query-federation.md)
  often silently downgrades consistency, because a federated query can only be as
  consistent as its weakest source, regardless of what any single engine promises.

## The cost is not optional, only its distribution is

A useful discipline: stronger consistency doesn't eliminate cost, it just moves the cost
to write time and makes it visible as latency, instead of leaving it implicit and
showing up later as a stale-read incident. A system advertised as "fast" that skips
coordination hasn't avoided the cost of consistency — it has deferred it onto whoever
reads stale data and doesn't know it.

This is why the right question when evaluating a data platform's consistency model is
never "is it consistent," but "which operations pay for consistency, and does that match
where correctness actually matters" — a dashboard tolerating a five-second-stale
aggregate is a different problem than a feature store serving a value that must match
what the model saw during training.

## Connections to other foundations

[Partitioning & Data Locality](partitioning-and-data-locality.md) sets the stage:
replicas exist because a single copy can't be everywhere data needs to be read cheaply,
and consistency models are the rules for keeping those copies coherent enough to be
useful. [Event Time vs. Processing Time](event-time-vs-processing-time.md) is a
specialized instance of the same problem in streaming systems — reconciling what
happened, in what order, against what a given node has observed so far.
