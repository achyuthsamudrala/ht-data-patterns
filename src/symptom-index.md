# Symptom Index

The incident-mode entry point. Find your observable below, then follow the discriminators
to the most likely candidate patterns.

> **Status:** skeleton only — categories are laid out, entries get filled in as each
> pattern family's pages are written (see the family phases). Run `make check-symptoms`
> to see which pattern pages aren't linked here yet.

---

## Batch job is slow

### One task takes far longer than the rest

- Single key dominates a partition → data skew
- One executor/node is consistently slow, others fine → straggler, not skew

### Job spends most of its time in shuffle

- Large shuffle write/read relative to input size → shuffle partitioning strategy
- Disk spill visible in stage metrics → spill to disk

### Job is slow after a schema or data-volume change

- Join strategy flipped from broadcast to shuffle → broadcast vs. shuffle join
- Plan looks the same but runs slower → stale statistics, cost-based optimization

---

## Batch job fails

### Executor OOM during shuffle or join

- Large partition, single key → data skew
- Memory fraction misconfigured relative to spill threshold → memory management

### Job fails only on full production data, not in staging

- Cardinality-dependent join strategy chosen at small scale doesn't hold at full scale

---

## Query plan chooses badly

### Query is correct but far slower than expected

- Wrong join order chosen → join ordering
- Full scan where a filter should prune → predicate/projection pushdown not applied
- Row-at-a-time execution on a large scan → vectorized execution

### Plan changes after a routine data refresh

- Table statistics stale or not recomputed → statistics and cardinality estimation

---

## Streaming job falls behind

### Consumer lag growing steadily

- Backpressure not applied, buffers filling → backpressure in streaming
- Partition count too low for throughput → Kafka partitioning

### State size grows without bound

- Window or state TTL not configured → stateful processing and state stores

### Late-arriving data is silently dropped or double-counted

- Watermark too aggressive or too lax → watermarks and late data
- Delivery semantics assumed but not actually exactly-once → exactly-once semantics

---

## Storage layer is unhealthy

### Small-file problem: too many tiny files, listing is slow

- Compaction not keeping up with ingest rate → compaction strategies
- Object store listing cost dominating → object store characteristics

### Query touches far more data than it should

- Partition layout doesn't match query filters → partition layout and pruning

---

## Serving layer is slow or stale

### Point lookups are slow despite an OLAP-shaped backend

- Analytical engine used for a serving workload → point lookups vs. analytical scans

### Read replicas return stale data under load

- Replication lag not surfaced to callers → read replicas and staleness

---

## Query system is congested

### Queries queue for a long time before running

- No admission control or workload isolation → query admission control
- One tenant's queries starve others → query queueing and fair scheduling
