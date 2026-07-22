# Bucketing & Co-partitioning

> **One-liner:** Pre-partitioning data on the join key at write time can eliminate shuffle at read time — until the bucketing assumptions drift.

## Symptom

- A join that used to skip a shuffle stage in the execution plan (`SortMergeJoin`
  without a preceding `Exchange`) suddenly shows a full shuffle after an unrelated
  upstream change.
- Two tables that are supposed to be bucketed identically produce a shuffle join anyway,
  and the execution plan shows the bucketing optimization wasn't applied.
- A table write job takes noticeably longer or produces far more output files after
  bucketing was introduced, without a clear corresponding read-side benefit yet.
- Adding a column, changing a partition scheme, or migrating a table to a different
  storage format silently drops a previously-working bucketing-based join
  optimization.

## Mechanism

Every join between two large tables ordinarily requires a shuffle to co-locate matching
keys (see [Partitioning & Data Locality](../../foundations/partitioning-and-data-locality.md)).
Bucketing pays this cost once, at write time, instead of once per query: rows are
pre-partitioned into a fixed number of buckets by hashing the intended join key, and
that bucket assignment is written into the table's physical layout as metadata. If two
tables are bucketed on the same key, with the same hash function, and the same bucket
count, a query joining them can skip the shuffle entirely — each bucket's data is
already co-located, and the engine can join bucket-for-bucket without an `Exchange`
step.

This optimization is contingent on three things staying exactly aligned: the join key,
the hash function, and the bucket count. If any of the three tables diverges — a bucket
count changed during a later rewrite, a schema migration introduced a slightly
different hash for the same logical key, or the query joins on a different (even
semantically equivalent) key — the planner cannot prove co-location and falls back to a
full shuffle join, silently. There is no error; the optimization just doesn't apply, and
the query still returns correct results, just without the speedup bucketing was
introduced for.

The cost of bucketing is paid at write time: writing bucketed output requires an
internal shuffle to route rows to the correct bucket, which is itself
[shuffle-cost-model](../../foundations/shuffle-cost-model.md)-shaped work. This is a
worthwhile trade only when a table is written once (or infrequently) and read — joined
— many times, since each read then skips the shuffle that the write already paid.

## Real-world sightings

Bucketing's fragility to metadata mismatch is documented directly in Spark's own SQL
documentation and Databricks engineering guidance, which specifically calls out that
bucket count and bucketing columns must match exactly between two tables for the
shuffle-free join (`SortMergeJoin` without `Exchange`) to be applied, and that this
matching is checked structurally rather than semantically — two tables bucketed
identically in intent but with different declared bucket counts get no benefit.

The broader pattern — investing shuffle cost at write time to save it at read time — is
also the design rationale behind co-partitioned storage layouts in data warehouse
systems generally (e.g., Hive's bucketing, which Spark's implementation is directly
descended from), and is frequently discussed in vendor tuning guides as a technique that
pays off specifically for slowly-changing dimension tables joined repeatedly against
a much larger, frequently-updated fact table.

## Mitigations

### Enforcing bucketing metadata as a schema contract

**What it is:** Treat bucket count, bucketing columns, and hash function as part of a
table's schema contract, validated at write time, rather than as an incidental physical
detail.

**Cost:** Adds governance overhead — someone has to own and enforce that contract
across every team writing to a bucketed table.

**How it backfires:** Without automated validation, this is a social contract, not a
technical one, and it erodes the same way any undocumented invariant does: silently,
under a well-intentioned but uncoordinated schema change.

### Monitoring for bucketing optimization drop-off

**What it is:** Track whether known bucketed joins are actually skipping the shuffle
stage in their execution plans, as an ongoing check rather than a one-time
verification.

**Cost:** Requires plan introspection tooling that most pipelines don't have by
default — this isn't a metric exposed passively by most job schedulers.

**How it backfires:** Even with monitoring, the fix for detected drift is manual —
rewriting or re-bucketing the divergent table — so monitoring surfaces the problem
without resolving it.

### Preferring dynamic co-partitioning over static bucketing

**What it is:** Rely on runtime shuffle optimization (AQE partition coalescing, dynamic
partition pruning) rather than static, write-time bucketing, accepting the recurring
shuffle cost in exchange for not depending on a fragile metadata contract.

**Cost:** Gives up the "pay once at write time" benefit entirely — every join pays its
own shuffle cost, every time.

**How it backfires:** For a table joined very frequently against a stable dimension,
this trades a one-time, upfront cost for a recurring cost that, summed over enough
reads, exceeds what bucketing would have cost — the right choice depends on read
frequency, which is easy to underestimate for tables that start as one-off analyses and
become long-lived pipeline inputs.

## Interactions

- [Broadcast vs. Shuffle Join](broadcast-vs-shuffle-join.md) — bucketing is only worth
  the write-time cost for tables too large to simply broadcast; for a small dimension
  table, broadcast join gets the same shuffle-free benefit with none of the metadata
  fragility.
- [Partitioning & Data Locality](../../foundations/partitioning-and-data-locality.md) —
  bucketing is the concrete, storage-layer application of the general co-location
  principle described there.
- [Table Formats & Metadata Layers](../storage/table-formats-and-metadata-layers.md) —
  modern lakehouse table formats track additional metadata (partition transforms, sort
  order) that can interact with or supersede classic bucketing depending on the format.

## References

- Apache Spark Documentation. *Bucketing in Spark SQL*. Describes the requirements for
  bucket-count and column matching to trigger shuffle-free joins.
- Databricks Engineering Blog. *Introducing Bucketing in Apache Spark*. Covers the
  write-time cost tradeoff and common misconfiguration pitfalls.
- Apache Hive Documentation. *Bucketed Tables*. The original bucketing design that
  Spark's implementation extends, including the hash-function and count-matching
  requirements.
