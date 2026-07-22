# Read Replicas & Staleness

> **One-liner:** Replicas absorb read load but introduce a staleness window that's invisible until a caller depends on read-your-writes.

## Symptom

- A user updates a record and, on the very next request, sees the old value — the write
  succeeded, but the read that immediately followed hit a replica that hadn't yet
  applied it.
- Read replica lag (the delay between a write landing on the primary and appearing on
  a replica) is normally small but spikes unpredictably under write-heavy load, and
  callers have no visibility into how stale a given read actually is.
- A workflow that writes a record and immediately reads it back to confirm success
  passes in low-traffic testing but fails intermittently in production under higher
  write volume.
- Different replicas of the same data return different values for the same query
  issued at nearly the same time, because they're lagging the primary by different
  amounts.

## Mechanism

Read replicas exist to scale read throughput beyond what a single primary node can
serve, by maintaining one or more additional copies that clients can read from instead
of hitting the primary for every request. This works because most workloads are far
more read-heavy than write-heavy, so distributing reads across replicas relieves the
primary's load meaningfully while writes still go through a single, consistent path.

The mechanism that makes this possible — asynchronous replication of writes from the
primary to replicas — is also exactly what introduces staleness: a replica's view of
the data lags the primary by however long replication takes to propagate and apply a
given write, and this lag is not zero and not perfectly bounded. Under normal load,
replication lag might be milliseconds; under write-heavy load, replicas can fall
further behind, since they have to apply the same volume of writes the primary
received while also (usually) serving their own read traffic.

This directly produces the "read-your-writes" violation described in
[Consistency Models for Distributed Data](../../foundations/consistency-models-for-distributed-data.md):
a client that just wrote a value has every reason to expect its own subsequent read
reflects that write, but if that read is routed to a lagging replica, it may not. This
failure is intermittent and load-dependent — it's rare enough under light load that it
frequently escapes notice during development and testing, and common enough under
production write volume that it manifests as a hard-to-reproduce, load-correlated bug
report rather than a consistently failing test case.

## Real-world sightings

The general asynchronous primary-replica replication model and its consistency
implications are described extensively in distributed systems literature — Amazon's
Dynamo paper (DeCandia et al., "Dynamo: Amazon's Highly Available Key-value Store,"
SOSP 2007) is a foundational reference discussing the availability/consistency
tradeoffs of eventually-consistent replicated systems, explicitly motivated by exactly
this kind of read-scaling requirement.

Most major managed database services' documentation (read replicas for relational
databases, and equivalent features across NoSQL and analytical systems) explicitly
warns that replica reads may be stale relative to the primary and recommends routing
read-your-writes-sensitive queries to the primary rather than a replica — a
consistently repeated piece of guidance precisely because the alternative failure mode
(intermittent, load-dependent staleness bugs) is so easy to overlook until it appears
in production.

## Mitigations

### Routing read-your-writes-sensitive queries to the primary

**What it is:** For specific operations where a client needs to see its own just-written
data immediately, route that read explicitly to the primary rather than a replica.

**Cost:** Forfeits the read-scaling benefit for exactly those operations, concentrating
their load back on the primary.

**How it backfires:** Requires correctly identifying every code path that has this
requirement; a new feature added later that reads immediately after writing, without
this routing consideration in mind, silently reintroduces the staleness bug.

### Read-after-write consistency tokens

**What it is:** Have the write path return a version or timestamp token, and have
subsequent reads require a replica to have caught up to at least that token before
serving the request (waiting or falling back to the primary if not).

**Cost:** Adds latency (waiting for replica catch-up) or complexity (token
propagation through the application) compared to an unconditional replica read.

**How it backfires:** If the token isn't propagated correctly through every layer of
the application (a common integration gap when this pattern is added incrementally),
some code paths silently fall back to ordinary, potentially-stale replica reads.

### Monitoring and alerting on replication lag directly

**What it is:** Track replica lag as a first-class operational metric, and alert when
it exceeds a threshold that would make staleness-sensitive workflows unreliable.

**Cost:** Requires the replication mechanism to expose lag as a measurable metric,
which isn't universal across all replication implementations.

**How it backfires:** Even with monitoring, an alert on lag doesn't prevent the
staleness that already occurred during the lag spike — it's a detection mechanism, not
a mitigation for reads that already happened during the lagging window.

## Interactions

- [Consistency Models for Distributed Data](../../foundations/consistency-models-for-distributed-data.md) —
  the foundational concept (read-your-writes, eventual consistency) this pattern is a
  concrete, serving-layer instance of.
- [Replication & Erasure Coding](../storage/replication-and-erasure-coding.md) —
  replication for durability and replication for read scaling use related mechanisms
  but serve different purposes and have different consistency implications.
- [Feature Store Serving](feature-store-serving.md) — online/offline feature
  consistency is a related but distinct staleness problem, driven by pipeline
  materialization lag rather than replication lag specifically.

## References

- DeCandia, G. et al. *Dynamo: Amazon's Highly Available Key-value Store*. SOSP 2007.
  Foundational treatment of availability/consistency tradeoffs in replicated systems.
- Vogels, W. *Eventually Consistent*. Communications of the ACM, 2009. Accessible
  explanation of the consistency spectrum replicated systems occupy.
- PostgreSQL Documentation. *Streaming Replication*. Describes practical replication
  lag behavior and monitoring for a widely used relational database's read replica
  feature.
