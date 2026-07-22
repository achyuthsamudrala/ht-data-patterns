# Replication & Erasure Coding

> **One-liner:** Durability schemes trade storage overhead for recovery speed and blast radius under correlated failure.

## Symptom

- A storage system's actual storage overhead (raw bytes stored per logical byte) is
  much higher or lower than expected for its configured durability guarantee, and it's
  unclear whether that's appropriate for the workload.
- Recovery time after a node or disk failure varies dramatically between two systems
  claiming similar nominal durability guarantees.
- A correlated failure (an entire rack or availability zone going down together) causes
  data loss or unavailability despite a replication factor that should, in principle,
  have tolerated the number of individual node failures involved.
- Write latency is noticeably higher on a system using erasure coding compared to one
  using simple replication, for data of the same logical size.

## Mechanism

Both replication and erasure coding protect against data loss from node or disk
failure, but they make different tradeoffs between storage overhead, write cost, and
recovery cost. **Replication** stores complete copies of data on multiple nodes — a
replication factor of 3 means three full copies exist, tolerating up to two
simultaneous failures (for that data) at the cost of 3x storage overhead. Recovery from
a lost replica is simple and fast: copy one of the remaining full replicas.
**Erasure coding** splits data into fragments and computes additional parity fragments,
such that the original data can be reconstructed from any sufficient subset of the
total fragments (data plus parity) — this achieves comparable fault tolerance at
substantially lower storage overhead than full replication (e.g., an erasure-coded
scheme storing 1.5x the logical data volume can tolerate as many failures as a
much higher-overhead replication scheme), but reconstructing lost data from surviving
fragments requires more computation than simply copying a full replica, making recovery
slower and more CPU-intensive.

This is why systems typically use replication for data with high, frequent access
(where recovery speed and read/write simplicity matter more than storage cost) and
erasure coding for colder, less frequently accessed data (where the storage cost
savings outweigh the recovery-speed penalty, since recovery events for cold data are —
by definition of being cold — infrequent enough that occasional slower recovery is an
acceptable trade).

Both schemes share a critical, easy-to-overlook assumption: their failure tolerance
math assumes failures are *independent*. A replication factor of 3, or an erasure code
tolerating 2 simultaneous fragment losses, is calculated against the assumption that any
given failure doesn't make other failures more likely. Correlated failures — an entire
rack losing power, an availability zone experiencing a network partition, a software
bug that corrupts data identically across all replicas because they ran the same
buggy code — violate this assumption directly, and neither replication factor nor
erasure-coding overhead protects against a failure mode that takes out multiple
replicas or fragments simultaneously for a shared reason. This is why durability
schemes are typically combined with explicit failure-domain awareness (placing replicas
or fragments across different racks, power domains, or availability zones deliberately)
rather than relying on redundancy count alone.

## Real-world sightings

The Google File System paper (Ghemawat, Gobioff, and Leung, "The Google File System,"
SOSP 2003) and the subsequent Google Colossus system design discussions describe
exactly this replication-for-hot / erasure-coding-for-cold split, motivated directly by
the storage-cost-versus-recovery-cost tradeoff described above, at a scale where the
storage overhead difference between the two schemes translates into very large
absolute cost differences.

Amazon's S3 and other major object stores' durability documentation explicitly
describes distributing redundant data across multiple, independent facilities/
availability zones specifically to address correlated failure — a design response
directly motivated by the observation that a naive redundancy count within a single
facility does not protect against a facility-level correlated event, which is a
recurring theme in post-incident write-ups from cloud providers describing multi-AZ
outages that affected services relying on single-AZ redundancy.

## Mitigations

### Explicit failure-domain-aware placement

**What it is:** Deliberately place replicas or erasure-coded fragments across distinct
failure domains (racks, power circuits, availability zones) rather than relying on
redundancy count alone to imply independence.

**Cost:** Cross-failure-domain placement (especially cross-availability-zone or
cross-region) typically adds write latency due to greater physical/network distance
between replicas.

**How it backfires:** Failure-domain placement policies configured once can silently
stop reflecting actual infrastructure topology if the underlying infrastructure changes
(a cloud provider's internal zone mapping shifts, a new rack is added without updating
placement logic) without a corresponding policy update.

### Matching redundancy scheme to access frequency

**What it is:** Use replication for frequently accessed, latency-sensitive data and
erasure coding for infrequently accessed, cost-sensitive data, rather than a single
scheme applied uniformly regardless of access pattern.

**Cost:** Requires classifying data by access pattern and potentially migrating data
between schemes as its access pattern changes over its lifetime (see
[Storage Tiering](storage-tiering.md) for the related access-frequency-based
migration problem).

**How it backfires:** Data whose access pattern shifts from cold to hot (an archived
dataset suddenly needed for an urgent analysis) is now erasure-coded and subject to
slower recovery exactly when recovery speed matters more, if the redundancy scheme
isn't re-evaluated alongside the access-pattern shift.

### Explicitly modeling correlated failure scenarios

**What it is:** Evaluate durability guarantees against realistic correlated-failure
scenarios (an entire zone or rack failing together), not just independent single-node
failure counts.

**Cost:** Requires infrastructure and failure-domain knowledge beyond simple
replication-factor arithmetic, and modeling correlated scenarios accurately requires
understanding the actual physical/logical topology of the underlying infrastructure.

**How it backfires:** None specific to doing this correctly — the entire failure mode
this pattern describes is precisely what happens when this modeling is skipped in
favor of a simpler, independence-assuming calculation.

## Interactions

- [Storage Tiering](storage-tiering.md) — the access-frequency dimension both patterns
  are sensitive to; cold data suited to tiering is often also suited to
  erasure coding for the same underlying reason.
- [Consistency Models for Distributed Data](../../foundations/consistency-models-for-distributed-data.md) —
  replication for durability and replication for read scaling (see
  [Read Replicas & Staleness](../serving/read-replicas-and-staleness.md)) are related
  but distinct concerns, often implemented using overlapping infrastructure. The
  independence assumption behind both replication factor and erasure-coding overhead
  is the same one that underlies most distributed-durability arithmetic generally.

## References

- Ghemawat, S., Gobioff, H., and Leung, S-T. *The Google File System*. SOSP 2003.
  Describes replication-based durability and the design considerations behind
  redundancy placement across failure domains.
- Dean, J. (Google). Discussions of Colossus and erasure coding at scale (various
  public talks and engineering blog posts) describing the storage-cost motivation for
  erasure coding over full replication for colder data.
- Amazon Web Services Documentation. *Amazon S3 Durability and Data Protection*.
  Describes multi-facility redundant storage design for correlated-failure resilience.
