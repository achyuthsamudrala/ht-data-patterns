# Interaction Map

Patterns rarely fail in isolation. This map shows which patterns compound and why.

> **Status:** skeleton only — edges get added to `src/interactions.yml` as each pattern
> family is written, then this Mermaid block is regenerated. Run `make check-interactions`
> to validate.

---

```mermaid
graph TD
    placeholder["Edges land here as pattern families are written"]
```

---

## High-value compounds

Entries land here as pattern pages are written and their `Interactions` sections
identify compounding pairs — for example, data skew compounding with spill-to-disk, or
backpressure compounding with checkpointing latency in streaming jobs.
