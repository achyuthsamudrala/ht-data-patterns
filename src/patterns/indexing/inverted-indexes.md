# Inverted Indexes for Search/Log Data

> **One-liner:** Term-to-document indexes make full-text and log search fast at the cost of index size that can exceed the source data several times over.

## Symptom

- An index built over a log or text corpus occupies significantly more disk space than
  the source data it indexes, sometimes several times as much.
- Indexing throughput becomes the bottleneck for high-volume log ingestion, with the
  indexing step lagging behind the raw ingestion rate.
- Query latency for common, high-frequency terms is noticeably worse than for rare
  terms, despite both being served by the same index structure.
- A search index's freshness lags the underlying data by a variable, sometimes
  significant amount, especially during periods of high ingestion volume.

## Mechanism

An inverted index maps each distinct term (a word, a token, a log field value) to the
list of documents (or log records) containing it — the inverse of the natural
document-to-terms mapping, hence the name. This is what makes "find all documents
containing term X" fast: rather than scanning every document to check for the term,
the index directly returns the (typically much smaller) list of documents already
known to contain it.

This structure has real, unavoidable overhead. Every distinct term in the corpus needs
an entry, and every document containing that term needs a reference in that entry's
postings list — for text or log data with high lexical diversity (many distinct
tokens, especially after including numeric values, identifiers, and other
high-cardinality fields common in structured log data), the total size of all postings
lists combined can exceed the size of the original data, particularly once additional
per-posting metadata (term position, for phrase queries; term frequency, for
relevance scoring) is included.

**Term frequency skew** directly causes the query-latency asymmetry in the symptom
list: common terms (natural-language stop words, or common log field values like a
status code that appears in most records) have very long postings lists, and a query
involving such a term has to process a correspondingly large list even though the term
provides comparatively little discriminating power — this is precisely why relevance
scoring and term-frequency-based weighting exist, to down-weight low-information,
high-frequency terms rather than simply making the underlying data structure work
harder for them.

**Indexing throughput vs. query freshness** is a direct tradeoff: building and merging
the postings lists for freshly ingested documents is itself computationally
significant work, structurally similar to LSM-tree compaction (see
[B-Tree vs. LSM-Tree Tradeoffs](btree-vs-lsm-tree.md)) — many search and log indexing
systems are, internally, built on an LSM-style architecture for exactly this reason,
appending new documents' postings as new segments and periodically merging them. Under
high ingestion volume, if indexing (segment creation and merging) can't keep pace with
ingestion, index freshness lags, and — as with any falling-behind maintenance
operation — the lag can compound if the backlog itself makes subsequent merges more
expensive.

## Real-world sightings

Elasticsearch and Apache Solr (both built on Apache Lucene's inverted index
implementation) document index size overhead relative to source data explicitly in
their sizing and capacity-planning guidance, generally recommending capacity
planning account for index size potentially exceeding raw source data size by a
significant factor depending on the specific text analysis and indexing configuration
used (stored fields, term vectors, and other optional per-document metadata all add to
this overhead).

Lucene's underlying segment-based architecture — new documents indexed into small,
immutable segments that are periodically merged in the background — is explicitly
LSM-style, and Lucene's and Elasticsearch's own documentation on segment merging
policies discusses the same throughput/latency tradeoff described for LSM compaction
generally: more aggressive merging improves query-time efficiency (fewer segments to
check per query) at the cost of more background merge I/O competing with ongoing
indexing throughput.

## Mitigations

### Excluding low-value fields from full indexing

**What it is:** Selectively index only the fields actually needed for search, rather
than indexing every field of every document by default, reducing both index size and
indexing cost.

**Cost:** Requires knowing in advance which fields will actually be searched on, and a
field excluded from indexing can't later be searched without reindexing.

**How it backfires:** A field excluded because it wasn't expected to be searched can
become relevant to a new, unanticipated query requirement, forcing either a
significant reindex or acceptance that the new query need can't be efficiently served.

### Term-frequency-aware relevance scoring

**What it is:** Use relevance scoring (TF-IDF, BM25, or similar) to down-weight the
contribution of high-frequency, low-discriminating terms, rather than treating every
term match with equal weight.

**Cost:** Adds scoring computation overhead per query compared to simple boolean
term matching.

**How it backfires:** Scoring parameters tuned for one corpus's term-frequency
distribution can behave unexpectedly on a different corpus (or the same corpus after
its content mix shifts significantly), requiring periodic re-tuning.

### Tuning segment merge policy for the ingestion/query balance

**What it is:** Configure how aggressively background segment merging runs, trading
indexing throughput against per-query segment-checking overhead, based on the actual
priorities of a specific workload.

**Cost:** Requires understanding the tradeoff and periodically revisiting it as
ingestion volume or query latency requirements change.

**How it backfires:** A merge policy tuned for a lower ingestion volume can allow
segment count (and thus per-query overhead) to grow unmanageably once ingestion volume
increases, in the same falling-behind pattern general compaction debt exhibits.

## Interactions

- [B-Tree vs. LSM-Tree Tradeoffs](btree-vs-lsm-tree.md) — inverted index
  implementations are frequently built on the same segment-append-and-merge
  architecture as LSM-trees, inheriting a related write/read amplification tradeoff.
- [Compaction Strategies](../storage/compaction-strategies.md) — segment merging in a
  search index is structurally the same falling-behind risk as general storage
  compaction.
- [Index Maintenance vs. Compaction Interplay](index-maintenance-vs-compaction.md) —
  segment merging for an inverted index competes for the same I/O budget as any other
  concurrent storage maintenance operation on the same infrastructure.

## References

- Elasticsearch Documentation. *Size Your Shards* and *Mapping*. Discusses index size
  overhead and field-inclusion tradeoffs for capacity planning.
- Manning, C. D., Raghavan, P., and Schütze, H. *Introduction to Information Retrieval*.
  Cambridge University Press, 2008. Foundational treatment of inverted indexes, term
  frequency, and relevance scoring.
- Apache Lucene Documentation. *Index File Formats* and *Segment Merging*. Describes
  the segment-based architecture and merge policy configuration.
