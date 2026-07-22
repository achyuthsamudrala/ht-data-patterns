# Feature Store Serving

> **One-liner:** Online and offline feature computation must agree exactly, or a model sees different features at training time and serving time.

## Symptom

- A model's live production performance is measurably worse than its offline
  evaluation metrics suggested, with no change to the model itself — the discrepancy
  traces back to feature values differing between training and serving.
- A feature computed via a slightly different code path or aggregation window for
  online serving than for offline training produces subtly different values for what's
  supposed to be the same logical feature.
- A newly added feature works correctly in offline batch evaluation but returns null or
  a default value in online serving, because the online feature computation path
  wasn't updated to compute it.
- Online feature freshness lags the true current value by an amount that varies
  depending on how recently the offline-to-online materialization pipeline last ran.

## Mechanism

A feature store's purpose is to compute and serve the same logical features
consistently across two very different contexts: **offline**, where features are
computed in batch over historical data to train a model, and **online**, where the same
features must be computed (or retrieved) for a single entity at low latency to serve a
real-time prediction. These two contexts have opposite performance requirements — see
[Point Lookups vs. Analytical Scans](point-lookups-vs-analytical-scans.md) — which is
why they're typically backed by entirely different storage and compute systems: an
analytical, scan-optimized store for offline feature computation, and a low-latency,
point-lookup-optimized store (a key-value database, typically) for online serving.

This split creates the central risk the pattern name describes: **training-serving
skew**. If the offline feature computation logic and the online feature computation
logic diverge — even subtly, such as a slightly different time window for an
aggregation, a different definition of "most recent," or a code path that was updated
in one place but not the other — the model sees systematically different feature
values at serving time than it was trained on. This isn't a crash or an obvious error;
the model still produces predictions, just based on inputs that don't match what it
learned to expect, degrading prediction quality in a way that's easy to misattribute to
model quality rather than feature-computation inconsistency.

**Point-in-time correctness** compounds this: offline training data has to be
constructed as if each training example only had access to feature values as they
existed *at the time* that example occurred, not using future information a live model
would never have had access to at serving time (a subtle form of label/feature
leakage). Getting this right requires the offline feature computation to be genuinely
time-aware, joining each training example against the feature values that were valid at
that example's timestamp — a materially harder computation than simply joining against
the latest feature values, and one that's easy to get wrong in ways that inflate
offline evaluation metrics without a corresponding real improvement in online
performance.

**Online feature freshness** is a related but distinct concern: features computed in
batch and materialized into the online store are only as current as the last
materialization run, meaning a feature's online value can lag its true current value by
however long that pipeline's refresh interval is — directly analogous to the
freshness lag described in [OLAP Serving Layer](olap-serving-layer.md), applied here to
model-serving inputs rather than dashboard aggregates.

## Real-world sightings

The training-serving skew problem is explicitly named and discussed in Google's
"Rules of Machine Learning" engineering guidance and in numerous feature-store-specific
engineering blog posts from companies operating large-scale ML platforms (Uber's
Michelangelo, Airbnb's Zipline, and other published internal ML platform
architectures), consistently identifying divergent online/offline feature computation
logic as a leading, often silent cause of production model underperformance relative to
offline evaluation.

Point-in-time correctness for offline training data construction ("time-travel joins")
is a first-class, explicitly documented design concern in most modern feature store
frameworks (Feast, Tecton, and the platform-specific systems referenced above),
generally implemented via an as-of join against a feature's full historical value
timeline rather than a simple join against current values, specifically to avoid the
future-information leakage described above.

## Mitigations

### Sharing feature computation logic between offline and online paths

**What it is:** Define feature computation logic once (a shared transformation
definition) and use the same logic to generate both the offline training dataset and
the online serving values, rather than maintaining two independently written
implementations.

**Cost:** Requires a feature computation framework capable of generating both batch
and low-latency online outputs from a single definition, which is a nontrivial
engineering investment to build or adopt.

**How it backfires:** Even with shared logic, if the *inputs* available differ between
contexts (an upstream data source that's available in batch but not in real time), the
shared logic can still produce different results, because the divergence has moved
from the transformation code to the underlying data availability.

### Point-in-time-correct offline joins

**What it is:** Construct training datasets using as-of joins against each feature's
historical value at each training example's specific timestamp, rather than joining
against current feature values.

**Cost:** Point-in-time joins are computationally more expensive than simple joins
against current state, and require maintaining a full historical timeline of feature
values rather than just the latest snapshot.

**How it backfires:** A point-in-time join implemented incorrectly (off-by-one in the
time boundary, or using processing time instead of event time — see
[Event Time vs. Processing Time](../../foundations/event-time-vs-processing-time.md))
can silently reintroduce leakage while appearing, superficially, to be doing the
correct thing.

### Explicit online feature freshness monitoring

**What it is:** Track the actual freshness (materialization lag) of online feature
values as an operational metric, distinct from monitoring the materialization
pipeline's success/failure alone.

**Cost:** Requires instrumenting freshness specifically, since a pipeline can succeed
on schedule while still producing features that are stale relative to a model's actual
latency requirements.

**How it backfires:** None specific — the absence of this monitoring means freshness
degradation is discovered only through degraded model performance, which is a much
noisier and slower signal than direct freshness monitoring would provide.

## Interactions

- [Point Lookups vs. Analytical Scans](point-lookups-vs-analytical-scans.md) — the
  underlying access-pattern mismatch that necessitates separate online and offline
  feature stores in the first place.
- [OLAP Serving Layer](olap-serving-layer.md) — the freshness-lag tradeoff described
  there applies directly to online feature materialization as a specific instance.
- [Event Time vs. Processing Time](../../foundations/event-time-vs-processing-time.md) —
  point-in-time-correct joins depend directly on correctly distinguishing event time
  from processing time.

## References

- Google. *Rules of Machine Learning: Best Practices for ML Engineering*. Discusses
  training-serving skew as a named, common production ML failure mode.
- Uber Engineering Blog. *Michelangelo: Uber's Machine Learning Platform*. Describes
  feature store design addressing online/offline consistency at scale.
- Feast Documentation. *Point-in-Time Joins*. Describes the mechanics of
  point-in-time-correct offline training data construction.
