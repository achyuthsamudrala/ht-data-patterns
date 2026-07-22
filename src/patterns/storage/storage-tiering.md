# Storage Tiering

> **One-liner:** Moving cold data to cheaper tiers saves cost until a query needs it back, at which point tiering becomes a latency problem.

## Symptom

- A query touching data that was recently moved to a colder storage tier takes far
  longer than an equivalent query over data still in the hot tier, disproportionate to
  the data volume difference.
- Storage cost drops significantly after a tiering policy takes effect, but a query
  that was previously fast (touching recent data) becomes intermittently slow as its
  data ages into a colder tier, without an obvious code or query change.
- A "restore from cold storage" operation blocks a query for minutes to hours, and the
  query has no way to signal this delay is expected versus a genuine failure.
- Reporting jobs that periodically re-scan a full historical range (e.g., a
  trailing-12-months report) become significantly more expensive to run once enough of
  that range has aged into a colder tier, without the report's logic having changed.

## Mechanism

Storage tiering exploits the fact that most data's access frequency drops sharply as it
ages: yesterday's data is queried constantly, last year's data rarely. Moving aged data
to a cheaper, slower storage tier (object-store infrequent-access classes, or archival
tiers requiring an explicit restore step before read) captures real cost savings for
data that genuinely isn't accessed often — but it converts what was a pure cost decision
into a latency decision the moment any query does touch that data.

This is a direct instance of the general storage hierarchy tradeoff described in
[The Memory & I/O Hierarchy](../../foundations/the-memory-and-io-hierarchy.md): moving
data to a cheaper tier necessarily moves it further down that hierarchy, and every
level down is an order of magnitude (or more) slower to access. Archival tiers can
require an explicit, asynchronous restore operation before the data is even readable —
not just slower access, but access on a completely different latency regime (minutes to
hours instead of milliseconds to seconds), and a query engine unaware of this
distinction can time out or fail outright rather than simply running slowly, because it
was never designed to wait on a multi-hour restore operation as part of a single query.

Tiering policies are typically defined by a simple age threshold ("move data older than
90 days to cold storage"), which is a reasonable default but doesn't account for
access-pattern exceptions: a periodic report that intentionally re-reads a full
historical window, a compliance audit that touches years-old records, or a backfill job
correcting historical data all touch "cold" data in ways an age-based policy has no way
to anticipate or exempt. The tiering decision made for the common case (recent data
matters, old data doesn't) silently penalizes the uncommon but real cases where old data
does matter.

## Real-world sightings

Cloud object storage providers' documentation for infrequent-access and archival
storage classes (e.g., S3 Glacier and its retrieval tiers) explicitly describes the
tradeoff between storage cost and retrieval latency/cost, including the multi-hour
retrieval windows for the coldest archival tiers — this tradeoff is a first-class,
explicitly documented part of the product design, not an incidental side effect.

Data lake and warehouse vendor documentation on lifecycle management policies (moving
data between storage classes based on age) consistently recommends aligning tiering
thresholds with actual, measured query access patterns rather than an arbitrary
default, and explicitly calls out periodic full-history reports and compliance/audit
queries as common exceptions that naive age-based tiering policies fail to
accommodate.

## Mitigations

### Setting tiering thresholds from measured access patterns, not defaults

**What it is:** Determine the age threshold for tiering based on actual observed query
access frequency by data age, rather than an arbitrary or vendor-recommended default.

**Cost:** Requires access-pattern instrumentation and periodic re-validation, since
access patterns can shift as reporting requirements or business needs change.

**How it backfires:** A threshold set once and left unrevisited becomes miscalibrated
as access patterns evolve — a report that starts querying a longer historical window
than it used to will begin hitting tiered-cold data without any corresponding update to
the tiering policy.

### Explicit exemptions for known recurring cold-data access

**What it is:** Identify specific, recurring access patterns that touch old data (a
periodic full-history report, an audit process) and exempt the data those patterns
touch from tiering, or pre-warm it ahead of the known access.

**Cost:** Requires maintaining an explicit exemption list, which is additional
operational bookkeeping.

**How it backfires:** New recurring cold-data access patterns emerge (a new report, a
new compliance requirement) that weren't anticipated when the exemption list was
built, and nothing alerts on this until the new access pattern actually incurs an
unexpected retrieval delay.

### Application-level awareness of tiering latency

**What it is:** Design query and reporting systems to explicitly detect and handle
(rather than time out on) archival-tier retrieval delays — issuing an async restore
request and polling for completion rather than blocking as if the data were hot.

**Cost:** Requires building this awareness into query tooling, which most engines
don't provide out of the box for arbitrary archival storage classes.

**How it backfires:** Without this awareness, the failure mode isn't graceful
degradation — it's an outright query failure or timeout, which is a worse outcome than
a slow-but-successful query, and can be mistaken for a systemic outage rather than an
expected consequence of the tiering policy.

## Interactions

- [The Memory & I/O Hierarchy](../../foundations/the-memory-and-io-hierarchy.md) — the
  foundational cost/latency tradeoff this pattern is a direct, storage-layer
  application of.
- [Object Store Characteristics](object-store-characteristics.md) — tiering is
  typically implemented as different object-store storage classes with different
  request latency and consistency characteristics.
- [Read Replicas & Staleness](../serving/read-replicas-and-staleness.md) — a related but
  distinct latency-vs-cost tradeoff: replication trades consistency for read
  availability, tiering trades access latency for storage cost.

## References

- Amazon Web Services Documentation. *S3 Storage Classes and Glacier Retrieval Options*.
  Describes the cost/latency tradeoff across storage tiers and archival retrieval
  timing.
- Google Cloud Documentation. *Object Lifecycle Management*. Describes age-based
  tiering policy configuration and its query-time implications.
- Databricks Documentation. *Data Lifecycle Management on the Lakehouse*. Discusses
  aligning tiering policy with measured access patterns.
