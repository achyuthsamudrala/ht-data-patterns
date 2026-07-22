# Index Maintenance vs. Compaction Interplay

> **One-liner:** Index maintenance and storage compaction compete for the same I/O budget, and scheduling them independently can starve both.

## Symptom

- Storage compaction and index rebuild/merge jobs scheduled independently
  occasionally overlap, and both run slower during the overlap than either would running
  alone.
- A system's overall I/O saturates during a maintenance window, even though neither
  compaction nor index maintenance alone would saturate it if run in isolation.
- Delaying index maintenance to let compaction finish first causes index-based query
  pruning effectiveness to degrade in the interim, compounding with whatever data
  volume compaction itself is addressing.
- Increasing parallelism for one maintenance operation (compaction or index
  maintenance) to speed it up unexpectedly slows the other down, revealing they were
  sharing a resource pool that wasn't obviously shared from either operation's own
  configuration.

## Mechanism

Storage compaction (see [Compaction Strategies](../storage/compaction-strategies.md))
and index maintenance (rebuilding or merging zone maps, bloom filters, sort-order
clustering, or inverted index segments) are both I/O- and compute-intensive background
operations that read and rewrite substantial data. When a table or dataset has both
kinds of maintenance running — which is the normal case, since indexes are typically
built over the same underlying data compaction manages — they compete for the same
underlying disk I/O, network bandwidth (for distributed storage), and CPU resources,
even though each is usually configured and scheduled as if it were the only
maintenance operation running.

This competition is easy to overlook precisely because each operation is often owned
and tuned independently — a storage/compaction configuration set by one team or
component, an indexing configuration set by another — with no shared awareness of the
combined I/O demand both will place on the underlying infrastructure at the same time.
The result, when they do overlap, isn't a clean, additive slowdown; because both are
competing for finite I/O bandwidth (and modern storage devices have inherent
sequential-vs-random-access performance characteristics that interact with concurrent,
differently-patterned workloads), simultaneous execution can produce worse combined
throughput than either operation's standalone benchmark would predict.

There's also a *causal* interplay, not just a resource-contention one: index
effectiveness (zone map pruning, sort-order clustering — see
[Bloom Filters & Zone Maps](bloom-filters-and-zone-maps.md) and
[Sort Keys & Z-Ordering](sort-keys-and-z-ordering.md)) often depends on the data being
in a compacted, well-organized state, meaning delaying compaction to prioritize index
maintenance (or vice versa) can actively degrade the *other* operation's effectiveness,
not just its scheduling convenience — an index rebuilt against un-compacted, fragmented
data may need to be rebuilt again shortly after compaction finally runs, effectively
doubling the index maintenance cost for data that will change layout again soon anyway.

## Real-world sightings

Cassandra's and other LSM-based systems' documentation on compaction and secondary
index maintenance explicitly discusses both operations sharing the same underlying
I/O and compaction thread pools, and recommends coordinating (or at least being aware
of) their combined resource demand rather than tuning each in isolation — a
recurring theme in production tuning guides for these systems, generally framed around
avoiding "compaction storms" that also starve concurrent index rebuild activity.

Elasticsearch's documentation on segment merging (the LSM-style maintenance underlying
its inverted indexes — see [Inverted Indexes for Search/Log Data](inverted-indexes.md))
explicitly recommends against running large, concurrent merge operations alongside
other I/O-intensive maintenance on the same node, for exactly this shared-resource-
contention reason, and provides throttling controls specifically to prevent merge
activity from starving other operations sharing the same disk.

## Mitigations

### Coordinating maintenance scheduling across compaction and indexing

**What it is:** Schedule compaction and index maintenance with explicit awareness of
each other, rather than as independently configured, uncoordinated background jobs.

**Cost:** Requires cross-team or cross-component coordination that isn't necessary
when each maintenance operation is naively configured in isolation.

**How it backfires:** Coordinated scheduling that works for today's data volume and
maintenance duration can drift out of sync as either operation's duration grows with
data volume, silently reintroducing the overlap this mitigation was meant to prevent.

### Explicit I/O budget allocation between maintenance operations

**What it is:** Allocate and enforce separate I/O or throughput budgets for compaction
versus index maintenance, so neither can fully starve the other even if both happen to
run concurrently.

**Cost:** Requires the underlying storage engine or orchestration layer to support
per-operation I/O throttling, which not every system exposes.

**How it backfires:** A fixed budget split tuned for a given data volume and access
pattern can become poorly balanced (starving whichever operation's workload grew more)
as either compaction backlog or index rebuild frequency changes independently over
time.

### Sequencing compaction before dependent index rebuilds

**What it is:** Where index effectiveness depends on compacted, well-organized data,
explicitly sequence compaction to complete before triggering the dependent index
rebuild, rather than running both on independent schedules.

**Cost:** Sequencing adds latency to the overall maintenance pipeline compared to
running both concurrently (when contention allows it) or independently.

**How it backfires:** A sequencing dependency, if not robustly implemented, can create
a cascading delay: if compaction runs late or fails, the dependent index rebuild is
delayed as well, compounding one maintenance operation's schedule slip into another's.

## Interactions

- [Compaction Strategies](../storage/compaction-strategies.md) — the storage-side
  maintenance operation this pattern's index-side counterpart competes with for shared
  resources.
- [Bloom Filters & Zone Maps](bloom-filters-and-zone-maps.md) and
  [Sort Keys & Z-Ordering](sort-keys-and-z-ordering.md) — the specific index
  structures whose effectiveness depends on the compacted, clustered state this
  pattern's sequencing mitigations address.
- [Inverted Indexes for Search/Log Data](inverted-indexes.md) — a widely encountered
  real-world instance of index maintenance (segment merging) directly competing with
  general storage maintenance for the same I/O.

## References

- Apache Cassandra Documentation. *Compaction* and *Secondary Indexes*. Discusses
  shared thread pool and I/O contention between compaction and index maintenance.
- Elasticsearch Documentation. *Tune for Indexing Speed* and *Merge*. Describes segment
  merge throttling to avoid starving concurrent I/O-intensive operations.
- O'Neil, P. et al. *The Log-Structured Merge-Tree (LSM-Tree)*. Acta Informatica, 1996.
  The shared architectural basis (append-and-merge) underlying both compaction and much
  index maintenance, explaining why they compete for the same resources.
