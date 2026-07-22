# Serialization & Tungsten

> **One-liner:** Off-heap binary encoding avoids JVM object overhead and GC pressure, but constrains what operations can run without deserializing.

## Symptom

- Switching a job's serializer changes both its runtime and its garbage collection
  profile substantially, in the same direction.
- A user-defined function applied mid-pipeline causes a measurable slowdown
  disproportionate to the function's own computational cost.
- Memory usage per row is far higher than the row's logical schema would suggest,
  traceable to per-object JVM overhead rather than the data itself.
- A job's CPU profile shows significant time in (de)serialization rather than in the
  actual computation the job is meant to perform.

## Mechanism

A JVM-based engine's default object representation carries substantial per-object
overhead — object headers, pointers, boxing of primitive types — that has nothing to do
with the logical size of the data being represented. For high-throughput data
processing, where billions of small records are processed, this overhead dominates:
representing a handful of integers as full JVM objects can cost several times their
logical byte size in actual memory, and every one of those objects is something the
garbage collector has to track and eventually reclaim.

Tungsten-style off-heap, binary row encoding addresses this by packing data into a
compact, contiguous byte representation — closer to how a C struct lays out memory than
how a JVM object does — stored outside the JVM heap where the garbage collector doesn't
manage it. This directly attacks two problems at once: per-object memory overhead
(a binary-encoded row is close to its logical size) and GC pressure (data outside the
heap isn't traced by garbage collection at all, and even on-heap improvements reduce
object count and thus collection work).

The tradeoff is that binary-encoded data is opaque to ordinary code — you cannot
directly manipulate an off-heap binary row with arbitrary JVM logic (a UDF, for
instance) without first deserializing it back into a JVM object, doing the work, and
potentially re-serializing the result. Whole-stage code generation mitigates this for
built-in operators by generating code that works directly against the binary
representation without ever materializing a full JVM object — but this only applies to
operations the code generator understands. A UDF, being opaque to the engine, forces
deserialization at its boundary, which is exactly why a UDF's cost is often
disproportionate to its own logic: the surrounding (de)serialization, not the UDF body,
is doing unexpected work.

## Real-world sightings

The Tungsten project is described in Databricks engineering blog posts ("Project
Tungsten: Bringing Apache Spark Closer to Bare Metal") as targeting exactly this
problem: reducing memory overhead and GC pressure by moving data management off the JVM
heap and using whole-stage code generation to operate directly on binary encodings
without materializing full JVM objects for intermediate results.

The specific cost of UDFs forcing serialization boundaries — breaking the benefit of
whole-stage code generation for any operator chain that includes one — is documented in
Databricks' PySpark and UDF performance guidance, which consistently recommends
built-in SQL expressions or vectorized (Pandas) UDFs, which batch the
serialization boundary across many rows at once rather than paying it per row, as a
mitigation for exactly this overhead.

## Mitigations

### Preferring built-in expressions and whole-stage code generation

**What it is:** Express transformations using native SQL/DataFrame operators that the
engine's code generator understands, keeping data in its binary representation for as
much of the pipeline as possible.

**Cost:** Not all logic is naturally expressible this way; some genuinely custom logic
requires breaking out of the built-in operator set.

**How it backfires:** This isn't really a backfire so much as a hard limit — some
computations are legitimately custom, and no amount of preference for built-ins removes
the need for a UDF in those cases; the mitigation is about minimizing unnecessary UDF
use, not eliminating it entirely.

### Vectorized (batch) UDFs instead of row-at-a-time UDFs

**What it is:** Use vectorized UDF interfaces (e.g., Pandas UDFs) that amortize the
serialization boundary across a batch of rows rather than paying it per individual row.

**Cost:** Requires writing UDF logic against a columnar/batch interface (e.g., a Pandas
Series) rather than a simple per-row function, which is a different (if usually more
natural, for numeric work) programming model.

**How it backfires:** Vectorized UDFs still cross the binary/JVM-object boundary, just
less often — for UDFs applied to a small fraction of rows via a selective filter, the
batching amortization benefit is smaller, because most of the batch's rows never
needed the UDF in the first place.

### Profiling for serialization-boundary cost specifically

**What it is:** When a UDF-containing stage is slow, profile to distinguish
serialization/deserialization time from the UDF's own logical computation time, rather
than assuming the UDF's algorithm is the bottleneck.

**Cost:** Requires profiling tooling capable of this distinction, which isn't always
available or easy to set up for distributed jobs.

**How it backfires:** Without this distinction, engineers commonly over-optimize UDF
logic that was never the actual bottleneck, missing that removing the UDF (or
vectorizing it) would have addressed the real cost.

## Interactions

- [Catalyst Optimizer & Logical Plans](catalyst-optimizer.md) — UDFs are opaque to both
  Catalyst's pushdown optimizations and Tungsten's code generation, for the same
  underlying reason: the engine cannot see inside arbitrary user code.
- [Memory Management](memory-management.md) — off-heap binary encoding changes where
  memory pressure shows up, moving substantial data volume outside the JVM heap's
  GC-managed region.
- [Vectorized Execution](../sql-execution/vectorized-execution.md) — the SQL-execution-layer
  counterpart to Tungsten's row encoding: both trade a more specialized, batch-oriented
  code path for CPU efficiency over a naive row-at-a-time approach.

## References

- Databricks Engineering Blog. *Project Tungsten: Bringing Apache Spark Closer to Bare
  Metal*. The primary design description of off-heap binary encoding and whole-stage
  code generation.
- Databricks Engineering Blog. *Introducing Pandas UDF for PySpark*. Describes
  vectorized UDFs as a mitigation for per-row serialization boundary cost.
- Neumann, T. *Efficiently Compiling Efficient Query Plans for Modern Hardware*. VLDB
  2011. Foundational work on whole-stage code generation that Tungsten's approach draws
  on.
