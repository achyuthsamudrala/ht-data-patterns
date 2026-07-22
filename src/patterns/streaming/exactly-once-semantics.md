# Exactly-Once Semantics

> **One-liner:** "Exactly-once" describes end-to-end effect, not delivery — achieving it requires idempotency or transactional writes, not just a config flag.

## Symptom

- A pipeline configured for "exactly-once" processing still produces duplicate rows or
  double-counted aggregates in its output after a consumer restart or rebalance.
- Enabling an "exactly-once" configuration flag has no visible effect on output
  correctness for a sink that isn't itself transactional.
- A retried write (after a transient failure whose success status was ambiguous)
  produces a duplicate effect downstream — a double charge, a double-counted event —
  despite delivery guarantees being configured as strong as the messaging layer allows.
- Two pipelines both configured identically for "exactly-once" behave differently under
  failure, because one writes to an idempotent sink and the other doesn't.

## Mechanism

"Exactly-once" is a claim about the *net effect* of a pipeline — each input event
influences the output as if it had been processed exactly one time — not a claim about
message delivery in isolation. This distinction matters because the underlying network
and processing layers cannot, in general, guarantee that a message is delivered exactly
once at the transport level: a producer that doesn't receive an acknowledgment for a
send cannot distinguish "the message was lost" from "the message was delivered but the
acknowledgment was lost," and the only safe response to that ambiguity is to retry,
which risks delivering the same message twice.

Exactly-once *effect* is achieved not by preventing duplicate delivery (which is
generally impractical to guarantee end-to-end) but by making the processing of a
duplicate delivery harmless. Two mechanisms accomplish this: **idempotent writes**,
where reprocessing the same input produces the same output state regardless of how many
times it's applied (an upsert keyed by a stable ID, rather than an unconditional
increment); and **transactional writes**, where the messaging system and the sink
participate in a transaction that atomically commits both the "this message was
processed" marker and the resulting output, so a failure partway through never leaves a
processed-but-unrecorded or recorded-but-unprocessed state.

The critical operational point: an "exactly-once" configuration flag on the processing
engine only controls the processing engine's own internal bookkeeping (offset commits,
checkpoint coordination). It cannot make an arbitrary downstream sink idempotent or
transactional on its own — if the sink is a plain, non-transactional external system
(an HTTP call to an unrelated service, a non-idempotent database increment), the
end-to-end guarantee degrades to at-least-once regardless of what the processing
engine's configuration claims, because the last mile of the guarantee depends on
properties of the sink, not the stream processor.

## Real-world sightings

Kafka's idempotent producer and transactional API, described in the Kafka Improvement
Proposals KIP-98 ("Exactly Once Delivery and Transactional Messaging") and the
accompanying design documentation, explicitly frame the feature as solving producer-side
duplicate delivery and multi-partition atomic writes — and explicitly scope the
guarantee to Kafka-to-Kafka pipelines, noting that end-to-end exactly-once for an
arbitrary external sink requires that sink to cooperate (via idempotent writes or a
two-phase commit protocol), a point reiterated across Kafka Streams documentation
discussing exactly-once semantics for stream processing topologies.

A widely referenced engineering discussion of this distinction is Jay Kreps' "Exactly-
once Semantics are Possible" post from the Confluent/Kafka engineering blog, explaining
precisely why exactly-once is achievable for the well-defined case of Kafka-to-Kafka
transactional writes but requires additional cooperation from any non-Kafka sink to
extend the guarantee further downstream.

## Mitigations

### Designing sinks to be idempotent

**What it is:** Structure downstream writes so reprocessing the same event (with the
same key or idempotency token) produces the same result, regardless of how many times
it's applied — typically an upsert or conditional write rather than a blind append or
increment.

**Cost:** Requires the sink to support keyed upserts or conditional writes, and
requires the pipeline to carry a stable, deterministic key or idempotency token through
every stage.

**How it backfires:** If the idempotency key itself is derived from something
non-deterministic (a locally generated timestamp or random ID assigned per attempt
rather than per logical event), retries produce a *new* key each time and the
idempotency protection silently does nothing.

### Transactional writes spanning source offset and sink output

**What it is:** Where supported, commit the source's consumed offset and the sink's
written output as a single atomic transaction, so a failure can't leave one committed
without the other.

**Cost:** Requires both the source and sink to support participating in the same
transactional protocol, which significantly narrows the set of compatible sink
technologies.

**How it backfires:** Transactional coordination adds latency and throughput overhead
compared to fire-and-forget writes, and a sink that claims transactional support but
implements it incorrectly (a common integration bug) provides no actual protection
while looking configured correctly.

### Scoping the guarantee explicitly to what's actually covered

**What it is:** Document and communicate precisely which hop of a pipeline
"exactly-once" actually applies to (e.g., "exactly-once from Kafka topic A to Kafka
topic B," not "exactly-once end-to-end to the final external system"), rather than
letting the term be assumed to cover the whole pipeline.

**Cost:** Requires discipline in how the guarantee is described to downstream
consumers and stakeholders, resisting the temptation to oversimplify.

**How it backfires:** None specific to correctly scoping the claim — the failure mode
this addresses is entirely the result of *not* doing this and letting "exactly-once"
be assumed to mean more than it actually guarantees.

## Interactions

- [Checkpointing & Fault Tolerance](checkpointing-and-fault-tolerance.md) — the
  mechanism that makes offset-and-state atomicity possible within the processing
  engine itself, which exactly-once semantics build on.
- [Stateful Processing & State Stores](stateful-processing-and-state-stores.md) — a
  stateful aggregation's exactly-once correctness depends on its state updates being
  part of the same atomic commit as its offset advancement.
- [Consistency Models for Distributed Data](../../foundations/consistency-models-for-distributed-data.md) —
  exactly-once semantics is a specific, output-effect-oriented consistency guarantee,
  distinct from but related to the general consistency models described there.

## References

- Apache Kafka KIP-98. *Exactly Once Delivery and Transactional Messaging*. The primary
  design document for Kafka's idempotent producer and transaction API.
- Kreps, J. *Exactly-once Semantics are Possible: Here's How Kafka Does It*. Confluent
  Engineering Blog. Explains the scope and mechanism of Kafka's exactly-once guarantee.
- Akidau, T. et al. *The Dataflow Model: A Practical Approach to Balancing Correctness,
  Latency, and Cost in Massive-Scale, Unbounded, Out-of-Order Data Processing*. VLDB
  2015. Broader treatment of correctness guarantees in streaming systems.
