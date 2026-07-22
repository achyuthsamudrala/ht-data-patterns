# Batch vs. Streaming: The Latency/Throughput/Consistency Spectrum

> **Batch and streaming are the same problem — process data, produce results — at
> different points on a latency/throughput/consistency tradeoff curve, not two
> different problems.** Micro-batching, continuous processing, and classic batch are
> all points on that curve, and most "should we use Spark or Flink/Kafka Streams"
> debates are really unstated disagreements about which point the workload needs.

## The three axes

**Latency** — how long after an event occurs does its effect appear in a result. Batch
systems answer in the time it takes a job to run (minutes to hours); streaming systems
answer in the time it takes a record to be processed (milliseconds to seconds).

**Throughput** — how much data can be processed per unit of resource. Batch systems
amortize fixed overhead (job startup, plan optimization, connection setup) over a large
input, which is efficient per byte but only after the whole input is assembled.
Streaming systems pay that overhead continuously in smaller increments, which is less
efficient per byte but doesn't require waiting for a batch boundary.

**Consistency / completeness** — whether a result reflects *all* the data that will
ever belong to it, or only the data seen so far. A batch job over a fixed input has an
unambiguous answer to "is this complete." A streaming aggregation over an unbounded
input has to define completeness explicitly — via a watermark — because there's no
natural end of input to wait for. See
[Event Time vs. Processing Time](event-time-vs-processing-time.md).

## Why you can't maximize all three

These axes trade against each other, not independently:

- Lowering latency (processing smaller increments, faster) means paying per-increment
  overhead more often, which lowers throughput efficiency.
- Increasing completeness confidence (waiting longer for late data) directly increases
  latency, because the result can't be emitted until the wait is over.
- Increasing throughput by batching more aggressively (bigger batches, less frequent
  processing) directly increases latency, because results wait for the batch to fill.

A system tuned for one axis is, by construction, not tuned for the other two. This is
why "just make streaming as fast as batch throughput" and "just make batch as low
latency as streaming" are both usually the wrong ask — the request is really for a
different point on the same curve, which requires trading away whichever axis currently
looks fine.

## Where common architectures sit

**Classic batch** (nightly Spark/Hive jobs) — high throughput, high latency, trivial
completeness (bounded input). Correct by construction once the input is fixed; the
entire cost is paid once, amortized, and known in advance.

**Micro-batch streaming** (Spark Structured Streaming's default mode) — processes small,
bounded batches on a fixed interval. This inherits batch's simpler fault-tolerance model
(each micro-batch is itself a small bounded job that can be retried atomically) at the
cost of latency at least as large as the batch interval. See
[Micro-batch vs. Continuous Processing](../patterns/streaming/microbatch-vs-continuous.md).

**Continuous/record-at-a-time streaming** (Flink's native mode, Kafka Streams) —
processes each record as it arrives, with no batch interval floor on latency. This
requires a fundamentally different fault-tolerance mechanism (distributed snapshots,
checkpoint barriers) because there's no natural retry unit smaller than "replay from
the last checkpoint." See
[Checkpointing & Fault Tolerance](../patterns/streaming/checkpointing-and-fault-tolerance.md).

## The consistency axis is where most incidents live

Latency and throughput problems are usually visible immediately — a job runs slow, a
consumer lags. Completeness problems are quieter: a streaming aggregation can emit a
plausible-looking, wrong number, because a watermark fired before all the relevant data
arrived, and nothing in the output signals that it was incomplete. This is why
[Watermarks & Late Data](../patterns/streaming/watermarks-and-late-data.md) and
[Windowing Strategies](../patterns/streaming/windowing-strategies.md) matter more, in
practice, than tuning either of the other two axes — a fast, high-throughput, wrong
answer is worse than a slow, correct one for most downstream consumers.

## Connections to other foundations

[The Cost Model of Shuffle](shuffle-cost-model.md) applies identically in both modes,
but streaming systems pay it continuously in small increments (rebalancing a consumer
group, redistributing state on scale-out) rather than once at job start.
[Consistency Models for Distributed Data](consistency-models-for-distributed-data.md)
generalizes the completeness axis described here to non-temporal data as well —
replication lag and watermark lag are the same underlying phenomenon, staleness against
a moving target, applied to different kinds of "target."
