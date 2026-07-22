# High-Throughput Data Platforms: A Field Guide

A practitioner's reference for operational patterns in high-throughput data
platforms — batch engines, streaming systems, storage layers, and the query/serving
infrastructure built on top of them.

**Read the field guide →** *(link live once deployed)*

## How to use this

Two entry points:

- **Design mode** — browse by section (Joins & Shuffle, Spark Internals, Streaming, …)
  before you build.
- **Incident mode** — start at the [Symptom Index](src/symptom-index.md): find your
  observable, follow 2–4 candidate patterns, read the Mechanism that fits.

## Contributing a scar

If you hit a variant of a pattern in production, open an issue using the template in
[CONTRIBUTING.md](CONTRIBUTING.md). The guide gets better with real operational specifics.

## Local development

Requires [mdBook](https://rust-lang.github.io/mdBook/) and
[mdbook-mermaid](https://github.com/badboy/mdbook-mermaid).

```
make serve        # live-reloading local preview
make build        # one-shot build → book/
make figures      # regenerate all SVG figures from sims/
make new-pattern SECTION=joins-and-shuffle NAME=my-pattern
make check-symptoms
make check-interactions
make check-template
```

## License

Prose (src/): [CC BY-SA 4.0](LICENSE).
Code (sims/, scripts/, Makefile): [MIT](LICENSE).
