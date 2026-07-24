# Source-data manifest

## Corpus used for the committed extraction

| Property | Value |
|---|---|
| Contents | Seven Harry Potter novels concatenated in publication order |
| Format | Plain text |
| Size | 6,458,601 bytes |
| Lines | 59,073 |
| Words reported by `wc` | 1,107,823 |
| SHA-256 | `4d5b67df663128588d255f871d296c745c8aac8c387b5687b8f43b8125dac331` |

The full corpus is not distributed because the novels remain copyrighted.
This manifest makes it possible to verify that two local extractions used the
same input without publishing the prose.

## Provide the raw input locally

Place a legally obtained corpus anywhere on your machine and pass its path to
the extractor:

```bash
python scripts/extract_graph.py /absolute/path/to/book.txt
```

By default, the derived graph is written to `app/data/graph.json`. The input
path itself is never copied into the repository. `data/book.txt` is explicitly
excluded by `.gitignore` to prevent accidental publication.

Verify the source file used for the committed results:

```bash
shasum -a 256 /absolute/path/to/book.txt
```

## Public derived data

Every node and relation is included in `app/data/graph.json`. Relation fields
include canonical source and target IDs, paragraph co-occurrence count,
per-book evidence counts, confidence, sentiment score and label, evidence
window count, and sentiment method.

No source paragraph or lengthy excerpt is retained in the derived file.

