# Event Time vs. Processing Time

> **A stream processor never observes the world; it observes messages about the world,
> arriving late and out of order.** Every windowing, watermark, and late-data pattern in
> this guide exists to reconcile the time an event happened (event time) with the time a
> system found out about it (processing time) — and the gap between them is unbounded
> in the general case.

## Two clocks, not one

**Event time** is when something actually happened in the real world — when a sensor
reading was taken, when a user clicked, when a transaction was authorized. It's embedded
in the data itself (a timestamp field) and doesn't change no matter when the record is
processed.

**Processing time** is when the stream processor observes and handles the record. It's
a property of the system, not the data, and it's what you get "for free" if you don't
do anything special — group-by-processing-time is trivial because it just means "group
by whatever arrived in this interval."

These two clocks agree only under an assumption that's false at any real scale: that
events arrive in the order they occurred, with a fixed, small delay. In practice,
mobile clients buffer and batch-upload events written offline hours earlier, distributed
producers experience clock skew, network partitions delay some partitions and not
others, and retries reorder what was originally sequential. Event time and processing
time diverge, and the divergence is not a bounded, well-behaved quantity — it can be
seconds or days depending on the source.

## Why this forces windowing to make a bet

A windowed aggregation (`sum of X per 5-minute window`) needs to decide, at some point,
that a window is "done" and emit a result. If windows were defined and closed strictly
by processing time, the result would be correct relative to *when the system happened to
see data*, but wrong relative to what actually occurred — events that happened within
the window but arrived late would either be excluded or force a correction after the
fact.

A watermark is the mechanism that makes this bet explicit rather than implicit: it's an
assertion of the form "we believe no more event-time data older than T will arrive." Once
the watermark passes a window's end, the window is considered closed and its result is
emitted — final, unless the pipeline explicitly supports retractions for data that
arrives after all. See
[Watermarks & Late Data](../patterns/streaming/watermarks-and-late-data.md) and
[Windowing Strategies](../patterns/streaming/windowing-strategies.md).

## The tradeoff a watermark encodes

Every watermark strategy is a position on a single tradeoff: how long to wait for
straggling event-time data before declaring a window complete.

- **Aggressive watermark (short wait):** low latency, but late-arriving data past the
  watermark is dropped or handled as a separate correction — completeness suffers.
- **Conservative watermark (long wait):** high completeness, but every window's result
  is delayed by however long the watermark waits — latency suffers.

There is no watermark setting that is simply "correct" — it's a statement about the
tail latency of the event sources feeding the pipeline, and that tail is a property of
the producers (mobile clients, IoT devices, upstream retry behavior), not something the
stream processor can control or improve on its own.

## Why this generalizes beyond streaming

The event-time/processing-time gap is a special case of a more general problem:
reconciling "when something became true" against "when a given observer found out."
Batch systems dodge this by defining "done" as "the input file set doesn't change
anymore" — but the same gap resurfaces the moment a batch pipeline ingests
late-arriving corrections (a backfilled row for yesterday's partition), and the same
question applies: does yesterday's already-computed aggregate get corrected, and if
so, how far back does the correction propagate?

## Connections to other foundations

[Batch vs. Streaming](batch-vs-streaming-spectrum.md) frames this as the consistency
axis of that spectrum — a watermark is the streaming-specific mechanism for making an
explicit completeness claim. [Consistency Models for Distributed Data](consistency-models-for-distributed-data.md)
frames the same underlying gap — staleness between what happened and what an observer
has seen — as it applies to replicated state rather than to time-ordered events.
