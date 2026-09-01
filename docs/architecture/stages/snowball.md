# Snowball (Citation-Graph Expansion)

The snowball stage runs between [ranking](ranking.md) and
[relevance scoring](relevance-scoring.md). It expands the ranked set one hop
along the citation graph: the top-ranked papers seed a lookup of the works
they cite (references) and the most-cited works that cite them (citations).
New candidates are merged with the ranked set, deduplicated and reconciled,
then re-ranked, so the relevance filter downstream sees the enriched pool.

Seminal papers that keyword search misses are usually one citation hop away
from whatever search did find — snowballing recovers them without any change
to the user's query.

## Graph source

OpenAlex serves as the citation graph:

- **References** — OpenAlex work objects retrieved during search already
  carry `referenced_works` IDs in their raw metadata, so references cost a
  single batched ID lookup (up to 50 works per request).
- **Citations** — fetched per seed with the `cites:` filter, sorted by
  citation count so the most influential citing papers arrive first.
- **Non-OpenAlex seeds** — resolved through their DOI when available; seeds
  without either an OpenAlex ID or a DOI contribute no graph edges.

Snowballed papers carry a `citation-snowball` marker in their
`found_by_queries` provenance, so reports and debugging can distinguish them
from search results.

## Configuration

The stage is governed by the `snowball` section (see the
[YAML reference](../../configuration/yaml-reference.md)):

| Key | Default | Meaning |
|-----|---------|---------|
| `enabled` | `true` | Toggle the stage without changing the pipeline |
| `max_seed_papers` | `5` | Top-ranked papers used as seeds |
| `per_seed_citations` | `5` | Citing papers fetched per seed |
| `max_reference_fetch` | `25` | Total referenced works fetched per run |
| `max_new_papers` | `30` | Cap on candidates entering re-ranking |
| `request_timeout_seconds` | `30` | Per-request timeout against OpenAlex |

The stage can also be disabled through `pipeline.enabled_stages.snowball`.

## Failure behavior

Snowballing never blocks a run. Network failures pass the original ranking
through unchanged with a warning; if the embedding backend is unavailable at
re-ranking time, the stage falls back to keyword-only ranking, matching the
behavior of the ranking stage itself. Stage metrics record seeds used,
candidates fetched, duplicates removed, and papers added.
