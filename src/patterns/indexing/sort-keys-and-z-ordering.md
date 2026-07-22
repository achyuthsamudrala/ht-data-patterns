# Sort Keys & Z-Ordering

> **One-liner:** Physically clustering data by sort key or space-filling curve makes range pruning effective for the columns it was built for, and useless for the ones it wasn't.

## Symptom

- Zone-map-based pruning (see [Bloom Filters & Zone Maps](bloom-filters-and-zone-maps.md))
  works well for queries filtering on a table's sort key, but provides no benefit for
  queries filtering on a different, uncorrelated column.
- A table clustered by a single sort key shows excellent pruning for single-column
  filters on that key, but multi-column filters combining the sort key with another
  column see only partial pruning benefit.
- Re-clustering (re-sorting or re-organizing) a large table to optimize for a new,
  different query pattern is a substantial, expensive rewrite operation, not an
  incremental adjustment.
- Z-ordering across several columns improves multi-column filter pruning compared to a
  single linear sort key, but the improvement is markedly better for some column
  combinations than others.

## Mechanism

Sort keys and space-filling curves like Z-ordering both aim to physically arrange data
so that rows with similar values in the clustered column(s) end up stored near each
other, which is the precondition [Bloom Filters & Zone Maps](bloom-filters-and-zone-maps.md)'
zone-map pruning depends on: min/max ranges per chunk are only useful when a chunk's
values are a narrow subset of the column's full range, which only happens if the data
is actually clustered by that column.

A simple **linear sort key** clusters data effectively for range queries on that one
key — consecutive values end up in the same or adjacent chunks — but provides
essentially no clustering benefit for any other column, since sorting by one column
does nothing to control how a different, independent column's values are distributed
across chunks.

**Z-ordering** (interleaving the bits of multiple columns' values into a single
space-filling curve, then sorting by that combined value) attempts to give reasonable
locality across *several* columns simultaneously, rather than perfect locality for one.
This is a genuine improvement for multi-column filters over an arbitrary, unclustered
layout, but it's a compromise, not a solution that fully replicates single-key sorting's
locality for every included dimension — a space-filling curve's locality-preservation
quality varies by how the dimensions interact and by which specific corner of the
multi-dimensional space a query's filter happens to target, meaning some column
combinations see much better pruning improvement from Z-ordering than others, and this
variation is a property of the curve's geometry, not something that's obviously
predictable without empirical testing against representative queries.

The re-clustering cost described in the symptom list follows directly from this being a
physical layout property: unlike an index, which can typically be added or dropped
without touching the underlying table's primary data layout, changing a table's
clustering (its sort key or Z-order columns) requires physically rewriting the data in
the new order — there's no way to incrementally adjust existing files' clustering
without a rewrite, which is why clustering decisions, once a table is large, are
comparatively expensive to revisit relative to adding an index.

## Real-world sightings

Z-ordering as a multi-dimensional clustering technique is explicitly described and
recommended in Databricks' Delta Lake documentation ("OPTIMIZE ZORDER BY") as a
mechanism for improving data-skipping (zone-map-style pruning) effectiveness across
multiple columns simultaneously, with the documentation explicitly noting that
Z-ordering's benefit varies by column combination and recommending it be applied based
on actual, measured query filter patterns rather than applied uniformly.

The general space-filling curve approach to multi-dimensional data locality predates
any specific lakehouse implementation — Morton (Z-order) curves and Hilbert curves are
both long-studied in spatial database and geographic information systems literature as
techniques for preserving multi-dimensional locality in a one-dimensional storage
ordering, each with documented tradeoffs in how uniformly they preserve locality across
different dimensional combinations.

## Mitigations

### Choosing clustering columns from measured, dominant filter patterns

**What it is:** Select sort key or Z-order columns based on the actual, most common
multi-column filter patterns real queries use against a table, rather than clustering
speculatively.

**Cost:** Requires knowing query patterns at clustering-design time, and re-clustering
later (if patterns shift) is an expensive rewrite, not an incremental change.

**How it backfires:** Query patterns evolve, and a clustering choice optimized for
historical query patterns can become a poor fit for new, emerging patterns without a
corresponding re-clustering — the cost of noticing and acting on this drift is real and
often deferred.

### Periodic re-clustering as new dominant patterns emerge

**What it is:** Treat clustering as a maintenance operation to be periodically
revisited (similar in cadence, if not mechanism, to compaction) as query patterns
evolve, rather than a one-time table-design decision.

**Cost:** Re-clustering a large table is a substantial rewrite, consuming significant
compute and I/O, and isn't something to do casually or frequently.

**How it backfires:** The expense of re-clustering creates a real incentive to defer
it past the point where the original clustering has stopped serving current query
patterns well, since the cost of the fix is high relative to the (gradual, not acute)
cost of not fixing it.

### Empirically validating Z-order column combination effectiveness

**What it is:** Measure actual pruning effectiveness for the specific column
combinations a table's queries use, rather than assuming Z-ordering improves pruning
uniformly across all included columns.

**Cost:** Requires representative query testing against the specific clustering choice
before committing to it at scale.

**How it backfires:** None specific to doing this validation — the absence of it is
the failure mode: assuming Z-ordering "just helps" without checking which column
combinations it actually helps for.

## Interactions

- [Bloom Filters & Zone Maps](bloom-filters-and-zone-maps.md) — the pruning mechanism
  whose effectiveness this pattern's clustering choices directly determine.
- [Partition Layout & Pruning](../storage/partition-layout-and-pruning.md) — partition
  layout is a coarser, directory-level clustering decision; sort keys and Z-ordering
  operate at a finer grain within partitions.
- [Compaction Strategies](../storage/compaction-strategies.md) — re-clustering and
  compaction are related maintenance operations, and are sometimes combined into a
  single rewrite pass for efficiency.

## References

- Databricks Documentation. *Data Skipping with Z-Order Indexes for Delta Lake*.
  Describes practical Z-ordering configuration and its column-combination-dependent
  effectiveness.
- Morton, G. M. *A Computer Oriented Geodetic Data Base and a New Technique in File
  Sequencing*. IBM, 1966. The original Z-order (Morton curve) space-filling curve
  design.
- Moerkotte, G. *Small Materialized Aggregates: A Light Weight Index Structure for Data
  Warehousing*. VLDB 1998. Discusses the clustering precondition for zone-map-style
  pruning effectiveness.
