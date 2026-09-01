"""Writes the monthly "what changed" brief for the monitoring retainer.

Only new and changed pages reach the model. Unchanged pages are excluded by
the hash comparison before we spend a single token, which is what makes a
monitoring run cost a fraction of a full audit — the crawl costs the same,
but the synthesis only reasons about what moved.
"""

from typing import List

from jobs.diff import CHANGED, NEW, NOT_CHECKED, PageChange
from synth.gemini import generate

PROMPT = """You are writing a monitoring update for {client}, covering what
changed on their site and their competitors' sites since the last check.

Below are only the pages that changed. Pages that stayed the same were
excluded before you saw them.

{evidence}

Write a short Markdown brief with these sections:

## What changed
The changes that matter, most significant first. Lead with competitor
activity — that is what the client is paying to hear about. Cite each page
as a markdown link using the URLs given.

## What it means for {client}
Brief, practical read on how these changes affect {client}'s position.

Rules you must follow:
- Use ONLY the material above. Do not add facts from memory or speculate
  about pages you were not shown.
- Every claim must cite one of the URLs provided.
- Describe changes at the level of substance, not wording. If a change is
  trivial or looks like a rendering artifact rather than an edit, say so.
- Do not invent metrics, rankings, or traffic figures — none were measured.
- If nothing here is materially significant, say that plainly. A short
  honest brief is worth more than a padded one.
"""


def _excerpt(text: str, limit: int) -> str:
    return " ".join((text or "").split())[:limit]


def _format_changes(changes: List[PageChange], client: str) -> str:
    blocks = []
    for change in changes:
        if change.status == NEW:
            blocks.append(
                f"""### NEW PAGE on {change.site_name} ({change.site_role})
Title: {change.title}
URL: {change.url}
Content: {_excerpt(change.current_text, 700)}"""
            )
        elif change.status == CHANGED:
            blocks.append(
                f"""### EDITED PAGE on {change.site_name} ({change.site_role})
Title: {change.title}
URL: {change.url}
Text before: {_excerpt(change.previous_text, 450)}
Text now: {_excerpt(change.current_text, 450)}"""
            )
        else:  # REMOVED
            blocks.append(
                f"""### REMOVED PAGE on {change.site_name} ({change.site_role})
Title: {change.title}
URL: {change.url}
It previously said: {_excerpt(change.previous_text, 300)}"""
            )
    return "\n\n".join(blocks).replace("{client}", client)


def generate_change_report(changes: List[PageChange], client: str) -> str:
    """Writes the brief. Returns Markdown."""
    reportable = [c for c in changes if c.status != NOT_CHECKED]
    if not reportable:
        return (
            f"# Monitoring update for {client}\n\n"
            "No changes detected on any monitored site since the last check.\n"
        )

    prompt = PROMPT.format(client=client, evidence=_format_changes(reportable, client))
    return generate(prompt)
