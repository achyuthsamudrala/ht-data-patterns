# Point Lookups vs. Analytical Scans

> **One-liner:** An engine tuned for scanning millions of rows and one tuned for fetching a single row by key optimize for opposite access patterns.

## Symptom

- A columnar analytical database performs a single-row lookup by primary key far more
  slowly than a row-oriented key-value store handling the same request, on
  comparable hardware.
- An OLTP-style database struggles to keep up when asked to scan and aggregate a large
  fraction of a table, a workload it wasn't designed for.
- A team migrates a serving workload onto an analytical engine (attracted by its
  existing pipeline integration) and finds p99 latency for simple lookups
  unacceptably high compared to their previous key-value store.
- Provisioning capacity for "the same data" behaves completely differently depending on
  whether the dominant query shape is lookups or scans, and a capacity plan built
  around one access pattern badly under- or over-provisions for the other.

## Mechanism

Point lookups and analytical scans represent genuinely opposite access patterns, and
storage/execution engines optimized for one are structurally mismatched for the other.

A point lookup needs to find one specific row (or a small number of rows) by key as
fast as possible — this favors row-oriented storage (all of that row's fields
contiguous, so a single seek retrieves everything needed) and index structures
optimized for fast, individual key lookups (see
[B-Tree vs. LSM-Tree Tradeoffs](../indexing/btree-vs-lsm-tree.md)). Retrieving one row
from a columnar store (see [Columnar Storage Formats](../sql-execution/columnar-storage-formats.md))
requires touching every column's separate physical location for that row — the exact
inverse of what columnar layout was designed to make efficient, since columnar's whole
premise is that a scan reads column-contiguous data for many rows at once, not scattered
single-row lookups across many columns.

An analytical scan needs to read and aggregate across a large fraction of a table's
rows, favoring columnar storage (read only the needed columns, contiguous and
compressible), vectorized execution (see
[Vectorized Execution](../sql-execution/vectorized-execution.md)), and pushdown-based
pruning. A row-oriented, lookup-optimized engine applied to this workload has to read
every column of every row it touches (no projection pruning benefit from row layout)
and lacks the batch-oriented execution model that makes scanning efficient at scale.

This means "point lookups vs. analytical scans" isn't a spectrum where one engine can
simply be tuned to cover both reasonably well — the two workloads want opposite
physical data layouts and opposite execution strategies, which is why serving
architectures commonly use two different, purpose-built systems (a key-value or
row-oriented OLTP-style store for lookups, an OLAP engine for scans) rather than
attempting to serve both from one, and why a workload that starts as purely
analytical but later accrues point-lookup-style serving traffic (or vice versa) is a
common source of the mismatch described in the symptom list — the original engine
choice was correct for the original workload, and became wrong as usage diversified.

## Real-world sightings

The architectural split between OLTP-optimized (row-oriented, point-lookup-favoring)
and OLAP-optimized (columnar, scan-favoring) database systems is one of the most
foundational distinctions in database systems design, discussed extensively across
both academic literature and vendor documentation for systems on either side of the
divide (e.g., traditional row-store RDBMSs and key-value stores versus Vertica,
ClickHouse, Druid, and other columnar analytical engines).

Feature store architectures (see
[Feature Store Serving](feature-store-serving.md)) are a widely discussed real-world
instance of needing to bridge exactly this gap deliberately: an "offline" feature store
computed from analytical (scan-heavy) batch pipelines has to be materialized into an
"online" feature store backed by a low-latency, point-lookup-optimized store (commonly
a key-value database) before it can serve real-time inference requests, precisely
because the two access patterns can't be efficiently served from the same underlying
storage engine.

## Mitigations

### Using separate, purpose-built systems for each access pattern

**What it is:** Serve point-lookup-heavy workloads from a row-oriented or key-value
store and analytical-scan-heavy workloads from a columnar OLAP engine, rather than
forcing one engine to serve both.

**Cost:** Requires operating and keeping consistent two separate storage systems for
what may be logically related data, adding data-movement and consistency-management
overhead between them.

**How it backfires:** The synchronization pipeline moving data from the
analytical/offline system to the lookup/online system becomes a new point of failure
and staleness (see [Feature Store Serving](feature-store-serving.md) for the specific
online/offline consistency risk this introduces).

### Recognizing workload drift before it causes a latency crisis

**What it is:** Monitor a serving system's actual query shape distribution
(lookup-like vs. scan-like) over time, so a shift in dominant access pattern is
caught before it manifests as a broad, hard-to-diagnose latency regression.

**Cost:** Requires classifying and tracking query shapes, which most systems don't
expose as a first-class metric by default.

**How it backfires:** None specific — the absence of this monitoring is itself the
failure mode, since without it, workload drift is discovered only once it's already
degraded production latency.

### Hybrid engines with explicit acknowledgment of their tradeoff boundary

**What it is:** Where using an engine advertised as supporting both patterns (some
modern "HTAP" — hybrid transactional/analytical — systems aim for this), explicitly
validate its actual lookup and scan performance against the specific workload's
requirements rather than assuming "supports both" means "optimal at both."

**Cost:** Requires benchmarking against real workload characteristics rather than
relying on vendor claims of hybrid capability.

**How it backfires:** A hybrid engine's compromise design can be adequate for
moderate load on both access patterns but fail to match a purpose-built engine's
performance at the extremes of either, which only becomes apparent once load grows
enough to matter.

## Interactions

- [Columnar Storage Formats](../sql-execution/columnar-storage-formats.md) — the
  storage-layer root of why analytical engines struggle with point lookups.
- [B-Tree vs. LSM-Tree Tradeoffs](../indexing/btree-vs-lsm-tree.md) — the index
  structures underlying most point-lookup-optimized systems.
- [Feature Store Serving](feature-store-serving.md) — a concrete, widely-encountered
  instance of needing to bridge this exact gap between analytical and lookup-serving
  systems.

## References

- Stonebraker, M. et al. *C-Store: A Column-oriented DBMS*. VLDB 2005. Foundational
  paper contrasting column-store and row-store design tradeoffs for analytical vs.
  transactional workloads.
- Apache Druid Documentation. *Druid Architecture*. Describes design choices favoring
  scan-heavy analytical workloads over point-lookup patterns.
- Uber Engineering Blog / various feature store engineering posts. Describe the
  online/offline store split as a direct response to this access-pattern mismatch.
