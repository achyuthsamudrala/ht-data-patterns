# Event-Driven / Streaming Systems

Streaming patterns address the failure modes that emerge when a system must process an unbounded, out-of-order sequence of events under a latency budget. The meta-pattern: correctness properties that are free in batch (exactly-once, complete results) require deliberate design in streaming.

## Reading order

[Watermarks & Late Data](watermarks-and-late-data.md) first — it's the foundation for reasoning about completeness. Then [Backpressure in Streaming](backpressure-in-streaming.md) for what happens when production outpaces consumption, and [Exactly-Once Semantics](exactly-once-semantics.md) for the delivery guarantees layered on top of both.

## Patterns in this section

- [Kafka Partitioning & Consumer Groups](kafka-partitioning-and-consumer-groups.md)
- [Exactly-Once Semantics](exactly-once-semantics.md)
- [Watermarks & Late Data](watermarks-and-late-data.md)
- [Windowing Strategies](windowing-strategies.md)
- [Backpressure in Streaming](backpressure-in-streaming.md)
- [Stateful Processing & State Stores](stateful-processing-and-state-stores.md)
- [Micro-batch vs. Continuous Processing](microbatch-vs-continuous.md)
- [Checkpointing & Fault Tolerance](checkpointing-and-fault-tolerance.md)
