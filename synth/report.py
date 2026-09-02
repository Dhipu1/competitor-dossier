"""Turns measured gaps into a written audit report.

The model is given only the evidence we retrieved, and told to cite the URLs
we supply. It is not asked to recall anything about these companies from its
training data: a report that mixes remembered facts with crawled evidence is
one a client can catch being wrong, and one wrong claim discredits the rest.
"""

import sqlite3
from typing import List

from enrichment.inventory import summarize
from enrichment.onpage import aggregate_by_site
from synth.gaps import Gap, find_gaps
from synth.gemini import generate

PROMPT = """You are writing a competitor content audit for {client}.

Competitors analysed: {competitors}

Below is evidence gathered by crawling all of these sites. Each item shows
something a competitor publishes, and the closest thing found anywhere on
{client}'s site, with a similarity score from 0 to 1 (lower = {client} has
less comparable content).

{evidence}

We also measured each site directly. These numbers are counted facts, not
estimates:

{site_facts}

Write a competitor content gap report in Markdown with these sections:

## Summary
Three to five sentences on the overall pattern in these gaps.

## Priority gaps
The most significant gaps, most important first. For each: what competitors
publish that {client} does not, why it matters, and a citation as a markdown
link to the competitor URL given in the evidence.

## Content depth and technical findings
What the measured numbers show, including anywhere {client} is ahead. Quote
the actual figures. Cover publishing cadence where it was measurable, and
concrete on-page fixes (missing descriptions, missing or duplicated H1s,
absent structured data) where the counts show them.

## Recommended actions
Concrete content {client} should create, tied to the gaps above.

Rules you must follow:
- Use ONLY the evidence and measurements above. Do not add facts about these
  companies from memory, and do not speculate about pages you were not shown.
- Every claim about a competitor must cite one of the URLs provided.
- If the evidence is thin or ambiguous for a point, say so plainly rather
  than filling the space.
- Do not invent traffic numbers, keyword rankings, or search volumes. None
  were measured, and no data above contains them.
- Where a measurement is marked unknown, say it is unknown. Never treat "we
  could not measure it" as "they have none".
- Page counts labelled "sampled" come from a limited crawl, not the whole
  site. Do not present them as the site's total size.
- {client} being ahead on a measure is a finding worth stating, not
  something to omit because the report is about gaps.
"""


def _format_evidence(gaps: List[Gap]) -> str:
    blocks = []
    for i, gap in enumerate(gaps, 1):
        competitor_text = " ".join(gap.competitor_excerpt.split())[:700]
        client_text = " ".join((gap.client_best_excerpt or "").split())[:300]
        blocks.append(
            f"""### Evidence {i}: "{gap.topic}" ({gap.competitor_name})
Competitor URL: {gap.competitor_url}
Competitor content: {competitor_text}
Closest content on {{client}}'s site (similarity {gap.client_best_score:.2f}): {client_text}
Closest page URL: {gap.client_best_url}"""
        )
    return "\n\n".join(blocks)


def _format_site_facts(conn: sqlite3.Connection, crawl_id: int) -> str:
    """Measured per-site facts: on-page signals plus sitemap scale and cadence."""
    inventories = {inv.site_name: inv for inv in summarize(conn, crawl_id)}
    blocks = []

    for site in aggregate_by_site(conn, crawl_id):
        inventory = inventories.get(site.site_name)
        lines = [
            f"### {site.site_name} ({site.site_role})",
            f"Pages sampled by our crawl: {site.pages} (a sample, not the site's full size)",
            f"Average words of main content per sampled page: {site.avg_words}",
            f"Sampled pages missing a meta description: {site.pages_missing_description}",
            f"Sampled pages with no H1 heading: {site.pages_missing_h1}",
            f"Sampled pages with more than one H1: {site.pages_multiple_h1}",
            f"Sampled pages carrying structured data: {site.pages_with_structured_data}",
            f"Average internal links per sampled page: {site.avg_internal_links}",
        ]

        if inventory and inventory.has_sitemap:
            newest = inventory.newest.date().isoformat() if inventory.newest else "unknown"
            sections = ", ".join(f"{name} ({count})" for name, count in inventory.top_sections)
            lines += [
                f"Total URLs the site lists in its own sitemap: {inventory.total_urls}",
                f"Of those, carrying a last-modified date: {inventory.dated_urls}",
                f"Pages published or updated in the last 30 days: {inventory.published_30d}",
                f"Pages published or updated in the last 90 days: {inventory.published_90d}",
                f"Pages published or updated in the last 365 days: {inventory.published_365d}",
                f"Most recent page update: {newest}",
                f"Largest sections of the site: {sections}",
            ]
        else:
            lines.append(
                "Total site size and publishing cadence: UNKNOWN — this site "
                "publishes no sitemap, so only the crawled sample can be described. "
                "Not evidence that the site is small or inactive."
            )

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def generate_report(conn: sqlite3.Connection, *, limit: int = 10) -> str:
    """Finds gaps, then asks the model to write them up. Returns Markdown."""
    gaps = find_gaps(conn, limit=limit)
    if not gaps:
        return "No gaps found — is the index built? Run scripts/build_index.py."

    latest = conn.execute(
        "SELECT id FROM crawls WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()

    client = conn.execute(
        "SELECT site_name FROM pages WHERE site_role = 'client' LIMIT 1"
    ).fetchone()["site_name"]
    competitors = sorted({g.competitor_name for g in gaps})

    prompt = PROMPT.format(
        client=client,
        competitors=", ".join(competitors),
        evidence=_format_evidence(gaps).replace("{client}", client),
        site_facts=_format_site_facts(conn, latest["id"]),
    )
    return generate(prompt)
