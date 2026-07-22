# The Memory & I/O Hierarchy

> **Every layer of the storage hierarchy is roughly an order of magnitude slower — and
> an order of magnitude cheaper per byte — than the one above it.** Indexing, columnar
> formats, compaction, and caching are all, mechanically, strategies for keeping the hot
> path as high in this hierarchy as possible and pushing everything else down.

## The numbers, approximately

These vary by hardware generation and cloud provider, but the *ratios* between levels
have stayed roughly stable for a decade, which is what makes them useful as a mental
model rather than a spec sheet:

| Level | Latency | Relative cost/byte |
|---|---|---|
| CPU cache (L1/L2/L3) | ~1–20 ns | highest |
| Main memory (RAM) | ~100 ns | high |
| Local NVMe SSD | ~10–100 μs | moderate |
| Local network (same rack) | ~0.1–0.5 ms | — |
| Remote SSD / cross-AZ network | ~1–2 ms | — |
| Object store (S3-class) | ~10–100 ms per request | low |
| Cross-region network | tens–hundreds of ms | — |

The gap between adjacent levels is 10–1000x, not a constant factor — which is why
"just add a cache" or "just add an index" produces such disproportionate wins when it
moves a hot read up one level, and why the same technique produces nothing when the
bottleneck is actually one level further down.

## Why data platforms are built around this table, not around it

A data platform's entire physical design — file format, index structure, cache
placement, compaction schedule — is an argument about which reads deserve to sit higher
in this hierarchy:

**Columnar formats** exist because scanning a column means reading contiguous bytes
instead of skipping across a row's other fields — it turns a scan into fewer, larger
sequential reads instead of many small ones, which matters enormously on the
SSD/object-store rows of the table where per-request overhead dominates for small
reads. See [Row vs. Columnar File Formats](../patterns/storage/row-vs-columnar-file-formats.md).

**Indexes** exist to avoid touching data at a lower (slower) level at all — a bloom
filter answering "definitely not present" from a structure that fits in memory saves an
SSD or object-store read entirely. See
[Bloom Filters & Zone Maps](../patterns/indexing/bloom-filters-and-zone-maps.md).

**Caching and materialized views** exist to move the *result* of an expensive lower-level
computation up to memory, so the next reader pays the memory cost instead of the
storage cost. See [Result/Query Caching](../patterns/serving/result-and-query-caching.md).

**Compaction** exists because small, scattered files force a reader to pay the
per-request latency of the object-store row of the table repeatedly, once per file,
instead of once per larger merged file. See
[Compaction Strategies](../patterns/storage/compaction-strategies.md).

## The object store row is qualitatively different

Object stores (S3 and equivalents) don't fit cleanly into the local-disk mental model
most engineers carry from single-machine systems. Per-request latency is high and
roughly *constant* regardless of object size up to some threshold, throughput scales
with request parallelism rather than with a single stream's bandwidth, and — unlike a
local filesystem — listing objects is itself an expensive, sometimes-inconsistent
operation. A system designed against local-disk assumptions (many small files, frequent
metadata listing) will be correct against an object store and an order of magnitude
slower than it needs to be. See
[Object Store Characteristics](../patterns/storage/object-store-characteristics.md).

## A diagnostic use of this table

When a read path is slow, the useful question isn't "is this slow" but "which row of
the hierarchy is this actually landing on, and does it need to." A query scanning
Parquet files from an object store, with no partition pruning and no column pruning, is
paying object-store-row latency multiplied by every file and every column — often two or
three rows lower in the hierarchy than the workload requires. Most of the mitigations in
the Storage, Indexing, and SQL Execution pattern families are, underneath their
specifics, an argument for skipping levels of this table rather than descending through
all of them on every query.

## Connections to other foundations

[Partitioning & Data Locality](partitioning-and-data-locality.md) is the horizontal
analog of this vertical hierarchy — locality is about which *node* holds data, this
page is about which *medium* holds it. [The Cost Model of Shuffle](shuffle-cost-model.md)
is a direct application: a shuffle that spills is a shuffle that got pushed down a row
in this table it didn't plan to occupy.
