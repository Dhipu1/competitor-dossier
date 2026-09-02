# The Competitor Dossier

A pipeline that crawls a client's site and their named competitors, then uses
an LLM to answer: what topics are we missing, where is our content thin, what
changed since last month.

Sold two ways: a one-time competitor gap audit, and a monthly monitoring
retainer that re-runs the same pipeline and reports only what changed.

## How it works

```
crawl  ->  enrich  ->  chunk  ->  embed  ->  retrieve  ->  measure gaps  ->  write report
```

Gaps are measured rather than guessed: for every competitor chunk, the
pipeline finds the closest thing on the client's site. A distant nearest
match means competitors cover ground the client doesn't. The LLM only
explains findings that already exist in the data, and must cite the URLs
it was given.

## Setup

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
```

Then create a `.env` file (never committed) with:

```
GEMINI_API_KEY=your-key-here
```

## Running an audit

One command runs the whole thing, in dependency order, stopping on failure:

```
.venv\Scripts\python scripts\run_audit.py clients\pilot.json
```

It produces `reports\audit-<date>.md` and a client-ready
`reports\audit-<date>.html` (open it and Ctrl+P → Save as PDF). Citation
verification runs before the deliverable is built, so a report citing pages
that were never crawled cannot become a document.

Add `--no-crawl` to redo the analysis on the last crawl without re-fetching.

The individual steps, if you need to run one on its own:

```
.venv\Scripts\python scripts\crawl_pilot.py clients\pilot.json   # crawl the sites
.venv\Scripts\python scripts\enrich.py                            # on-page signals + sitemaps
.venv\Scripts\python scripts\build_index.py                       # chunk + embed
.venv\Scripts\python scripts\generate_report.py                   # write the report
.venv\Scripts\python scripts\verify_citations.py                  # check for fabricated links
.venv\Scripts\python scripts\build_deliverable.py                 # styled HTML/PDF
```

## Monitoring

```
.venv\Scripts\python scripts\monitor_run.py clients\pilot.json          # one run now
.venv\Scripts\python scripts\schedule_monitoring.py clients\pilot.json  # set up a schedule
```

The scheduler prints the Task Scheduler command and only registers it if you
pass `--install`.

Crawling is the only step that touches other people's servers (bar one small
sitemap request per site). Raw HTML is stored, so enrichment, chunking,
embedding, and report changes all re-run for free.

## What is and isn't measured

Everything reported is counted from pages we fetched: content depth, title
and meta description coverage, heading structure, internal links, structured
data, plus site scale and publishing cadence from each site's own sitemap.

Search volume, keyword rankings, and traffic are **not** measured — they
can't be derived from a page and need a paid API (DataForSEO or similar).
Reports are instructed never to invent them. Sites publishing no sitemap are
reported as unknown scale, never as zero.

## Layout

- `crawler/` — robots.txt checks, browser fetch, whole-site link following
- `enrichment/` — on-page SEO signals, sitemap inventory and cadence
- `ingest/` — splitting pages into chunks, turning chunks into vectors
- `retrieval/` — semantic search over stored chunks
- `synth/` — gap measurement, prompts, Gemini client
- `storage/` — SQLite schema and writes
- `jobs/` — crawl diffing for monitoring, generated scheduler launchers
- `clients/` — per-client config: which sites, how many pages
- `templates/` — the client deliverable template
- `docs/` — the offer one-pager, onboarding checklist, sample audit
- `scripts/` — the commands above

## Selling it

- [`docs/one-pager.md`](docs/one-pager.md) — the four offers and what's in each
  (rates are invented for this practice project)
- [`docs/onboarding.md`](docs/onboarding.md) — what to collect from a client
  before the first crawl, and why each item matters
- [`docs/sample-audit.md`](docs/sample-audit.md) — real pipeline output with the
  subjects anonymised, regenerate with `scripts\anonymize_sample.py`

## Client config

`clients/pilot.json` names the client site and its competitors. The current
pilot uses game studios: Supergiant Games as the client, Team Cherry and
Klei Entertainment as competitors.
