"""Turns measured gaps into a written audit report.

The model is given only the evidence we retrieved, and told to cite the URLs
we supply. It is not asked to recall anything about these companies from its
training data: a report that mixes remembered facts with crawled evidence is
one a client can catch being wrong, and one wrong claim discredits the rest.
"""

import sqlite3
from typing import List

from synth.gaps import Gap, find_gaps
from synth.gemini import generate

PROMPT = """You are writing a competitor content audit for {client}.

Competitors analysed: {competitors}

Below is evidence gathered by crawling all of these sites. Each item shows
something a competitor publishes, and the closest thing found anywhere on
{client}'s site, with a similarity score from 0 to 1 (lower = {client} has
less comparable content).

{evidence}

Write a competitor content gap report in Markdown with these sections:

## Summary
Three to five sentences on the overall pattern in these gaps.

## Priority gaps
The most significant gaps, most important first. For each: what competitors
publish that {client} does not, why it matters, and a citation as a markdown
link to the competitor URL given in the evidence.

## Recommended actions
Concrete content {client} should create, tied to the gaps above.

Rules you must follow:
- Use ONLY the evidence above. Do not add facts about these companies from
  memory, and do not speculate about pages you were not shown.
- Every claim about a competitor must cite one of the URLs provided.
- If the evidence is thin or ambiguous for a point, say so plainly rather
  than filling the space.
- Do not invent metrics, traffic numbers, or rankings — none were measured.
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


def generate_report(conn: sqlite3.Connection, *, limit: int = 10) -> str:
    """Finds gaps, then asks the model to write them up. Returns Markdown."""
    gaps = find_gaps(conn, limit=limit)
    if not gaps:
        return "No gaps found — is the index built? Run scripts/build_index.py."

    client = conn.execute(
        "SELECT site_name FROM pages WHERE site_role = 'client' LIMIT 1"
    ).fetchone()["site_name"]
    competitors = sorted({g.competitor_name for g in gaps})

    prompt = PROMPT.format(
        client=client,
        competitors=", ".join(competitors),
        evidence=_format_evidence(gaps).replace("{client}", client),
    )
    return generate(prompt)
