# The Competitor Dossier

A pipeline that crawls a client's site and their named competitors, then uses
an LLM to answer: what topics are we missing, where is our content thin, what
changed since last month.

Sold two ways: a one-time competitor gap audit, and a monthly monitoring
retainer that re-runs the same pipeline and reports only what changed.

## Status

Early build — see commit history for progress. Being built incrementally,
one pipeline stage at a time.

## Setup

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
```

## Layout

- `crawler/` — fetches pages with a real browser, extracts main content
- `storage/` — SQLite database: crawled pages, crawl history
- (more stages added as the pipeline grows)
