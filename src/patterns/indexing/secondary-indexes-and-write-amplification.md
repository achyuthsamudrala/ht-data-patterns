# Secondary Indexes & Write Amplification

> **One-liner:** Every secondary index is a second write on every mutation, and that multiplier is easy to undercount when indexes are added incrementally.

## Symptom

- Write throughput drops noticeably after adding a new secondary index, disproportionate
  to what the index's own storage footprint would suggest.
- A table with several secondary indexes shows write latency several times higher than
  an equivalent table with only a primary index, for logically similar data volume.
- Removing an unused or rarely-queried secondary index measurably improves write
  throughput, revealing that its ongoing cost had gone unnoticed relative to its query
  benefit.
- Adding indexes incrementally, one at a time over a table's lifetime, produces a
  write-throughput regression whose magnitude, in aggregate, wasn't obvious from any
  single index addition considered in isolation.

## Mechanism

A secondary index maintains an additional, separately queryable ordering of a table's
data — by a column other than the primary key — to make lookups and range queries on
that column fast without scanning the whole table. This benefit is not free: every
insert, update, or delete against the table has to be reflected not just in the
primary storage structure, but in every secondary index as well, since each index is,
structurally, its own separate data structure that has to stay consistent with the
underlying table.

This means a table with N secondary indexes pays roughly N+1 writes for every logical
mutation — one for the primary structure, one for each secondary index — a
multiplication that's easy to lose track of because indexes are typically added
incrementally, one at a time, each addition looking individually reasonable ("just one
more index for this one query pattern") without anyone tracking the cumulative write
multiplier across a table's full index set.

The cost compounds further depending on the underlying storage engine. For a
B-tree-backed secondary index (see [B-Tree vs. LSM-Tree Tradeoffs](btree-vs-lsm-tree.md)),
each index update is a random write to that index's own structure, with all the
in-place-update cost that implies. For an LSM-tree-backed secondary index, the
secondary index write is itself an append (cheaper per write) but still adds to the
overall write volume the storage engine has to compact, so the secondary index
contributes its own compaction burden on top of the primary structure's.

Deletions have a subtler cost: removing a row requires removing its entries from every
secondary index too, and if any of those index-removal operations don't happen
atomically with the primary deletion (a consistency risk in some implementations), a
secondary index can end up referencing rows that no longer exist in the primary
structure — a dangling reference that either has to be tolerated (with query-time
filtering) or is a correctness bug depending on the storage engine's guarantees.

## Real-world sightings

The write-amplification cost of secondary indexes is a widely documented,
extensively discussed operational consideration across relational and NoSQL database
documentation alike — most database vendors' schema design guidance explicitly warns
against adding secondary indexes speculatively or "just in case," recommending index
addition be driven by actual, measured query patterns specifically because of this
compounding write cost.

Apache Cassandra's documentation on secondary indexes explicitly discusses their
write-amplification and consistency tradeoffs in a distributed, LSM-backed context,
generally recommending alternative denormalization strategies (maintaining a
separately structured table rather than a secondary index) for high-write-volume
tables where index maintenance cost would be prohibitive relative to its query
benefit.

## Mitigations

### Adding indexes based on measured query patterns, not speculation

**What it is:** Only add a secondary index once an actual, measured query pattern
justifies its ongoing write cost, rather than adding indexes preemptively for
anticipated future query needs.

**Cost:** Requires accepting slower queries temporarily (or query patterns that can't
yet be efficiently served) until the index is justified and added.

**How it backfires:** None specific to disciplined index addition — the risk this
mitigation addresses is the opposite: unjustified, speculative indexes accumulating
write cost with no corresponding query benefit.

### Periodically auditing index usage against write cost

**What it is:** Regularly review which secondary indexes are actually being used by
queries, and remove ones whose query benefit no longer justifies their ongoing write
cost.

**Cost:** Requires query-pattern instrumentation capable of attributing query
performance to specific index usage, which isn't always straightforward to obtain.

**How it backfires:** Removing an index that's used rarely but critically (a
compliance or audit query run infrequently but requiring acceptable performance when it
does run) trades ongoing write savings for a query that becomes unacceptably slow on
the rare occasions it actually runs.

### Denormalization instead of secondary indexing for high-write-volume tables

**What it is:** For tables with very high write volume where secondary index
maintenance cost is prohibitive, maintain a separately structured, denormalized table
for the alternative query pattern instead of an index on the primary table.

**Cost:** Requires maintaining consistency between the primary table and the
denormalized copy, typically via an asynchronous pipeline rather than a
synchronous index update.

**How it backfires:** The asynchronous consistency mechanism between the primary table
and its denormalized copy introduces its own staleness window, directly analogous to
the read-replica staleness problem described in
[Read Replicas & Staleness](../serving/read-replicas-and-staleness.md).

## Interactions

- [B-Tree vs. LSM-Tree Tradeoffs](btree-vs-lsm-tree.md) — the underlying storage
  engine's write characteristics directly determine how expensive each secondary
  index's maintenance actually is.
- [Index Maintenance vs. Compaction Interplay](index-maintenance-vs-compaction.md) —
  secondary index maintenance and storage compaction compete for the same I/O budget,
  compounding this pattern's cost with that one's.
- [Compaction Strategies](../storage/compaction-strategies.md) — each secondary index
  adds its own compaction burden on top of the primary structure's, for LSM-backed
  storage.

## References

- Apache Cassandra Documentation. *Secondary Indexes*. Describes write-amplification
  and consistency tradeoffs for secondary indexes in a distributed, LSM-backed
  system.
- Comer, D. *The Ubiquitous B-Tree*. ACM Computing Surveys, 1979. Foundational
  reference on index maintenance cost for B-tree-backed structures.
- O'Neil, P. et al. *The Log-Structured Merge-Tree (LSM-Tree)*. Acta Informatica, 1996.
  Describes the append-and-compact cost model that secondary index writes are also
  subject to in LSM-backed engines.
