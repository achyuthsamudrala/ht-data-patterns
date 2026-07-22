# Hot Partition Handling in Serving

> **One-liner:** A serving layer partitioned for average load concentrates all the risk on whichever partition a skewed access pattern happens to hit.

## Symptom

- One partition or shard in a serving system shows dramatically higher latency and
  resource utilization than its neighbors, while overall cluster-wide metrics look
  healthy.
- A single popular entity (a viral piece of content, a large customer account, a widely
  referenced record) causes a serving hot spot even though the system's total
  provisioned capacity comfortably exceeds aggregate demand.
- Adding more nodes or shards to the serving layer doesn't relieve the observed
  slowdown, because the hot key's traffic is still concentrated on whichever single
  partition owns it.
- A serving system that scales cleanly for most traffic experiences repeated,
  unpredictable latency incidents traceable each time to a different single key
  becoming momentarily hot.

## Mechanism

Partitioning a serving layer (whether by hash of a key, or a range) distributes both
data and, implicitly, request load across partitions — but that distribution assumes
request load per key is roughly uniform, an assumption that's frequently false in
production for the same reasons described in
[Data Skew & Salting](../joins-and-shuffle/data-skew-and-salting.md): real-world access
patterns follow power laws, and a small number of keys can receive a disproportionate
share of requests.

Unlike batch processing skew, where the cost is a slow task that eventually completes,
serving-layer hot partitions have an ongoing, live-traffic cost: the partition (and the
single node or set of nodes serving it) absorbs a disproportionate share of read (or
write) load continuously, for as long as that key remains hot, degrading latency for
every request hitting that partition — including requests for *other*, non-hot keys
that happen to be co-located on the same partition through the ordinary hash or range
assignment. This means a hot key doesn't just degrade its own requests; it can degrade
service for an entire partition's worth of otherwise-unrelated keys sharing that
partition purely by partitioning coincidence.

Because the serving layer's total capacity is typically provisioned for aggregate,
expected load, a hot partition is a case where the *system* is not overloaded but a
*specific partition* is — a distinction that matters because generic capacity scaling
(adding more nodes) doesn't help unless the scaling mechanism can actually redistribute
the hot key's load across more resources, which simple hash or range partitioning
cannot do for a single key by definition, since a key by construction maps to exactly
one partition.

## Real-world sightings

Amazon's DynamoDB documentation explicitly discusses hot partition handling, including
its adaptive capacity feature, which detects disproportionately accessed partition keys
and reallocates additional throughput capacity to the specific partition serving them
— an explicit acknowledgment that uniform partition-level provisioning is
insufficient once real-world access skew is accounted for.

The general concept of "shuffle sharding" — assigning each client or key to a
randomized, overlapping subset of the serving fleet rather than a single fixed
partition — is described in AWS's own architecture guidance (notably in discussions of
Route 53's and other AWS services' shuffle sharding design) as a mitigation for
exactly this blast-radius problem: even when a specific key or client becomes hot, its
impact is spread across a wider, randomized subset of the fleet rather than
concentrated on one fixed partition and its co-located neighbors.

## Mitigations

### Adaptive or dynamic capacity allocation per partition

**What it is:** Detect disproportionately accessed partitions at runtime and
dynamically allocate additional serving capacity specifically to them, rather than
relying on uniform per-partition provisioning.

**Cost:** Requires the serving system to support dynamic, per-partition capacity
reallocation, which is more operationally complex than static, uniform partitioning.

**How it backfires:** Reallocating capacity to a hot partition draws that capacity from
somewhere — if the reallocation mechanism doesn't account for genuine, simultaneous
hot spots on multiple partitions, it can rob one legitimately busy partition to relieve
another.

### Splitting or isolating known hot keys

**What it is:** Detect specific, individual hot keys and give them dedicated serving
resources (a cache layer specifically for them, or explicit key-level sharding)
separate from the general partitioning scheme.

**Cost:** Requires ongoing detection of which keys are currently hot, since hotness is
often transient (a viral moment, a temporary spike) rather than a permanent property of
the key.

**How it backfires:** A hot-key isolation mechanism tuned to react to sustained
hotness can be too slow to help during a sudden, short-lived spike, and one tuned to
react instantly can add unnecessary overhead reacting to noise rather than genuine,
sustained hot keys.

### Shuffle sharding to bound blast radius

**What it is:** Assign each key or client to a randomized, overlapping subset of the
serving fleet rather than a single fixed partition, so a hot key's impact is spread
thin across many nodes rather than concentrated on one.

**Cost:** Adds routing complexity (determining and maintaining each key's randomized
shard assignment) compared to simple, deterministic partitioning.

**How it backfires:** Shuffle sharding reduces blast radius but doesn't eliminate the
underlying hot-key load — a sufficiently hot key can still degrade every node in its
randomized shard set, just a wider (and hopefully less concentrated) set than a single
fixed partition would have been.

## Interactions

- [Data Skew & Salting](../joins-and-shuffle/data-skew-and-salting.md) — the same
  power-law access distribution problem, applied to live serving traffic rather than
  batch shuffle partitions.
- [Read Replicas & Staleness](read-replicas-and-staleness.md) — read replicas are one
  way to add capacity for hot read traffic, but introduce their own staleness tradeoff
  in exchange.
- [Partitioning & Data Locality](../../foundations/partitioning-and-data-locality.md) —
  the foundational hash/range partitioning mechanism whose fixed key-to-partition
  mapping is exactly what this pattern's mitigations work around.

## References

- Amazon Web Services Documentation. *DynamoDB Adaptive Capacity*. Describes automatic
  detection and mitigation of disproportionately accessed partition keys.
- Amazon Web Services Documentation / Architecture Blog. *Shuffle Sharding: Massive and
  Magical Fault Isolation*. Describes shuffle sharding as a blast-radius mitigation
  applicable to hot-key and hot-partition scenarios.
- DeCandia, G. et al. *Dynamo: Amazon's Highly Available Key-value Store*. SOSP 2007.
  Discusses partitioning and load distribution challenges in a large-scale key-value
  serving system.
