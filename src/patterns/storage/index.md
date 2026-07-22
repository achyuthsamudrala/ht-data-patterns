# Storage Systems

Storage patterns address how data at rest is laid out, compacted, and tiered — decisions made once at write time that determine every subsequent read's cost, often invisibly until a system is at production scale.

## Reading order

[Row vs. Columnar File Formats](row-vs-columnar-file-formats.md) first, then [Table Formats & Metadata Layers](table-formats-and-metadata-layers.md) for how modern lakehouse formats add transactions and schema evolution on top.

## Patterns in this section

- [Row vs. Columnar File Formats](row-vs-columnar-file-formats.md)
- [Table Formats & Metadata Layers](table-formats-and-metadata-layers.md)
- [Compaction Strategies](compaction-strategies.md)
- [Partition Layout & Pruning](partition-layout-and-pruning.md)
- [Storage Tiering](storage-tiering.md)
- [Object Store Characteristics](object-store-characteristics.md)
- [Replication & Erasure Coding](replication-and-erasure-coding.md)
