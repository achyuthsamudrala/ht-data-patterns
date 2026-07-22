# Indexing Systems

Indexing patterns address the structures that make lookups fast — and the costs, mostly paid on the write path, that every index imposes in exchange.

## Reading order

[B-Tree vs. LSM-Tree Tradeoffs](btree-vs-lsm-tree.md) first — it's the foundational choice underneath most of the others. Then [Secondary Indexes & Write Amplification](secondary-indexes-and-write-amplification.md) for what adding an index costs beyond storage.

## Patterns in this section

- [B-Tree vs. LSM-Tree Tradeoffs](btree-vs-lsm-tree.md)
- [Secondary Indexes & Write Amplification](secondary-indexes-and-write-amplification.md)
- [Bloom Filters & Zone Maps](bloom-filters-and-zone-maps.md)
- [Sort Keys & Z-Ordering](sort-keys-and-z-ordering.md)
- [Inverted Indexes for Search/Log Data](inverted-indexes.md)
- [Index Maintenance vs. Compaction Interplay](index-maintenance-vs-compaction.md)
