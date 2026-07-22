# Object Store Characteristics

> **One-liner:** S3-like object stores have listing, consistency, and request-rate characteristics that behave nothing like a filesystem, and engines that assume otherwise fail unpredictably.

## Symptom

- Listing a directory-equivalent prefix in an object store takes noticeably longer as
  the number of objects under that prefix grows, in a way a traditional filesystem's
  directory listing wouldn't.
- A job writing many files under keys sharing a common prefix experiences throttling or
  elevated latency that a similarly-sized write to keys with more varied prefixes does
  not.
- A reader immediately following a writer occasionally sees a stale or incomplete view
  of just-written data, in an object store or configuration without strong read-after-write
  consistency.
- A job designed around frequent small "rename" or "move" operations (a pattern natural
  on a POSIX filesystem) performs far worse than expected, because the object store has
  no true atomic rename — a "move" is implemented as a copy followed by a delete.

## Mechanism

Object stores are frequently treated, in application design, as if they were a
networked filesystem — because the API often resembles one (keys that look like
paths, a "list files under this prefix" operation) — but several of their actual
operational characteristics diverge sharply from filesystem semantics, and systems
built on the filesystem mental model hit these divergences unpredictably.

**Listing is not free and not necessarily fast.** Object stores are conceptually flat
key-value stores; "directories" are an illusion constructed from common key prefixes.
Listing all keys under a prefix requires the store to scan and paginate through
matching keys, and this cost scales with the number of matching objects, unlike a
filesystem directory listing which is typically a fast, size-bounded metadata
operation. A table with many small files (see
[Compaction Strategies](compaction-strategies.md)) pays this listing cost on every
query that needs to enumerate its files, compounding the small-file problem with an
extra layer of listing latency beyond the per-file read overhead already discussed
there.

**Request rate can be prefix-sensitive.** Historically (and still relevant for some
providers and configurations), object stores partition request handling internally by
key prefix, meaning a large number of objects sharing a common prefix — a natural
consequence of time-based partitioning, like `year=2024/month=01/day=01/` — could
concentrate requests onto a narrow internal partition range and trigger throttling,
even when aggregate request volume across the whole bucket was well within overall
capacity. Modern object stores have substantially improved automatic partition scaling,
but workloads with very high, spiky request concurrency against a narrow key range can
still surface this behavior.

**Consistency has historically varied, and still varies by configuration.**
Read-after-write consistency (a reader immediately seeing data a writer just
committed) is now standard for the dominant object stores' basic operations, but
list operations, cross-region replication, and some managed layers built on top of
object storage can still have weaker consistency windows — and applications assuming
uniformly strong consistency across every operation type can be surprised by a stale
listing or a delayed cross-region read.

**There is no atomic rename.** A filesystem rename is typically an atomic metadata
operation; an object store "move" is a copy-then-delete, which is neither atomic
(a failure between the copy and the delete leaves both copies, or neither, depending on
where it failed) nor cheap (copying an entire object's data rather than just
updating a metadata pointer). Table formats' reliance on atomic commit operations (see
[Table Formats & Metadata Layers](table-formats-and-metadata-layers.md)) has to work
around this limitation explicitly, typically via conditional-write primitives rather
than relying on rename semantics at all.

## Real-world sightings

Amazon's own S3 documentation on "request rate and performance guidelines" historically
described prefix-based internal partitioning and recommended randomizing key prefixes
to spread request load, before later documentation updates describing substantially
improved automatic scaling that reduced (though didn't necessarily eliminate for all
access patterns) the need for manual prefix randomization — the evolution of this
guidance over time is itself evidence of how significant the original constraint was in
practice.

The absence of atomic rename and its implications for building transactional table
formats on object storage is explicitly discussed in the Delta Lake paper (Armbrust et
al., VLDB 2020), which describes the specific mechanisms (conditional put operations,
or an external coordination service where the underlying object store lacks
conditional writes) needed to implement atomic commits without a native atomic rename
primitive.

## Mitigations

### Designing key/prefix schemes with request distribution in mind

**What it is:** For workloads with very high write or read concurrency against a
narrow set of keys, structure key prefixes to distribute load rather than
concentrating it (e.g., avoiding a purely sequential timestamp as the leading part of
every key).

**Cost:** A distributed-prefix key scheme can make certain listing or range-scan
operations less convenient than a purely sequential scheme would be.

**How it backfires:** Over-applying this mitigation to a workload that never actually
had enough request concurrency to trigger prefix-based throttling adds needless key
design complexity for no benefit.

### Minimizing unnecessary listing operations

**What it is:** Maintain and consult metadata (a table format's manifest, an external
index) rather than repeatedly listing object-store prefixes directly to discover a
table's current file set.

**Cost:** Requires maintaining that metadata layer's own consistency, which is exactly
what table formats (see [Table Formats & Metadata Layers](table-formats-and-metadata-layers.md))
are built to do.

**How it backfires:** A metadata layer that itself falls out of sync with actual
object-store state (from a partial or failed write) can cause queries to reference
files that don't exist or miss files that do, trading a listing-performance problem for
a correctness problem if not implemented carefully.

### Using conditional writes instead of relying on rename semantics

**What it is:** Implement atomic commit logic using the object store's conditional
write / compare-and-swap primitives (where available) rather than assuming filesystem
rename semantics.

**Cost:** Requires the object store to support conditional writes, and requires
application logic explicitly designed around this primitive rather than a simpler
rename-based mental model.

**How it backfires:** An object store or storage layer lacking native conditional
writes requires an external coordination mechanism (a separate consistent metadata
store) to achieve the same atomicity, adding another operational component and another
potential point of failure.

## Interactions

- [The Memory & I/O Hierarchy](../../foundations/the-memory-and-io-hierarchy.md) — the
  foundational reference for why object-store request latency and listing cost behave
  so differently from local disk.
- [Compaction Strategies](compaction-strategies.md) — small-file accumulation
  compounds directly with object-store listing cost, since more files means more
  listing overhead on top of more per-file read overhead.
- [Table Formats & Metadata Layers](table-formats-and-metadata-layers.md) — the
  metadata layer that lets query engines avoid direct, repeated object-store listing
  and work around the lack of atomic rename.

## References

- Amazon Web Services Documentation. *Best Practices Design Patterns: Optimizing
  Amazon S3 Performance*. Describes request-rate characteristics and key design
  guidance.
- Armbrust, M. et al. *Delta Lake: High-Performance ACID Table Storage over Cloud
  Object Stores*. VLDB 2020. Describes the atomicity challenges of building
  transactional guarantees over object storage lacking atomic rename.
- Google Cloud Documentation. *Cloud Storage Consistency*. Describes read-after-write
  and list consistency guarantees and their scope.
