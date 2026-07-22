# Introduction

This is a field guide for engineers who build, operate, or debug high-throughput data
platforms — batch engines, streaming systems, storage layers, and the query/serving
infrastructure built on top of them.

## Who this is for

Engineers who already run data pipelines or query systems in production and are hitting
the problems that show up only at scale: shuffles that spill to disk and blow past their
SLA, joins that hang on one skewed key, streaming jobs whose state grows without bound,
compaction that can't keep up with ingest, or query planners that pick a plan two orders
of magnitude worse than the alternative.

This guide assumes you're comfortable with SQL and have run at least one batch or
streaming job against a real dataset. It does not assume you've read the internals of
any specific engine — the mechanism sections introduce just enough of that theory to
reason about the failure mode, and point to the engine-specific behavior (mostly
Spark, Kafka, and Trino/Presto-shaped systems) where it matters.

## What this guide is not

This is not a tutorial on any single engine, and it does not cover data modeling,
pipeline orchestration tools, or ML training infrastructure. It covers a specific set of
mechanical failure modes — the ones rooted in how data moves, gets indexed, and gets
queried at high throughput — and their mitigations.

It is also not a comprehensive survey of every technique in the literature. The patterns
included are those that appear repeatedly in production incidents, papers, and
engine-internals documentation. Selection bias toward patterns that bite engineers in
practice is intentional.

## Two reading modes

**Design mode** — read a pattern before you build. Each page describes the trap you're
trying to avoid and the mitigations available, including how each mitigation backfires
under specific conditions.

**Incident mode** — start at the [Symptom Index](symptom-index.md). Find your observable,
follow 2–4 candidate patterns, read the Mechanism section of the one that fits.

## How patterns are structured

Every page follows the same six-section template:

1. **Symptom** — what your dashboards, Spark UI, or query plan show, written for someone
   mid-incident.
2. **Mechanism** — why it happens, with the minimum theory needed to reason about it.
3. **Real-world sightings** — documented incidents, traceable to public sources. No
   fabricated examples.
4. **Mitigations** — what to do, what it costs, and **how it backfires** under specific
   conditions.
5. **Interactions** — which other patterns compound with this one and why.
6. **References** — 3–7 items, annotated.

The "how it backfires" entries matter. A mitigation that works as designed but on wrong
assumptions — a broadcast join threshold set for last year's data volume, a compaction
schedule tuned for last quarter's write rate — causes as many incidents as the absence
of any mitigation at all.

## Where to start

- If something is on fire right now: [Symptom Index](symptom-index.md)
- If you want the underlying concepts before reading patterns, or a refresher on
  Spark/SQL execution basics: [Foundations](foundations/spark-execution-model-basics.md)
- If you want to understand how patterns combine: [Interaction Map](interaction-map.md)
- If you're debugging a slow join or shuffle spill:
  [Joins & Shuffle patterns](patterns/joins-and-shuffle/index.md)
- If you're debugging a streaming job:
  [Streaming patterns](patterns/streaming/index.md)

## A note on real-world sightings

Each pattern page includes a "Real-world sightings" section. The standard for these
entries is verifiable public sources: peer-reviewed papers, published engineering blog
posts, or official documentation. Incidents described in these sections happened and
were reported publicly.

Where no strong public sighting exists, the section says so in one sentence rather than
fabricating a plausible-sounding incident. The absence of a cited sighting does not mean
the pattern is theoretical — it means no public documentation was found.
