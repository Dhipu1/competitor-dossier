"""Finds topics competitors cover that the client doesn't.

The measurement, deliberately, is not an LLM judgement call. For every
competitor chunk we ask: what's the closest thing on the client's site?
If the closest match is still distant, competitors are covering ground the
client isn't — that's a gap, and it's backed by a number and a source URL
rather than by a model's opinion.

The LLM's job comes later: explaining gaps that were already found this way.
Asking a model to invent a gap list would produce confident, unverifiable
fiction — exactly the failure mode that loses a client's trust.
"""

import sqlite3
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from ingest.embed import from_blob

# Nav menus that survived content extraction. These are links, not content,
# and would otherwise show up as "gaps" in the client's coverage of menus.
_BOILERPLATE_MARKERS = ("skip to content", "open menu", "close menu")


@dataclass
class Gap:
    topic: str                      # the competitor's own heading for this material
    competitor_name: str
    competitor_url: str
    competitor_excerpt: str
    client_best_score: float        # 0-1; how close the client's nearest content is
    client_best_url: Optional[str]
    client_best_excerpt: Optional[str]

    @property
    def gap_size(self) -> float:
        return 1.0 - self.client_best_score


def _is_boilerplate(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _BOILERPLATE_MARKERS)


def _load(conn: sqlite3.Connection, role: str):
    rows = conn.execute(
        """
        SELECT c.heading, c.text, c.embedding, p.site_name, p.final_url, p.title
        FROM chunks c JOIN pages p ON p.id = c.page_id
        WHERE p.site_role = ?
        """,
        (role,),
    ).fetchall()
    return [r for r in rows if not _is_boilerplate(r["text"])]


def find_gaps(
    conn: sqlite3.Connection,
    *,
    limit: int = 10,
    max_per_topic: int = 1,
) -> List[Gap]:
    """Returns the competitor material least covered by the client, worst gap first."""
    competitor_rows = _load(conn, "competitor")
    client_rows = _load(conn, "client")
    if not competitor_rows or not client_rows:
        return []

    competitor_matrix = np.vstack([from_blob(r["embedding"]) for r in competitor_rows])
    client_matrix = np.vstack([from_blob(r["embedding"]) for r in client_rows])

    # every competitor chunk against every client chunk in one multiplication;
    # for each competitor chunk we keep only its single closest client match
    similarity = competitor_matrix @ client_matrix.T
    best_index = similarity.argmax(axis=1)
    best_score = similarity.max(axis=1)

    gaps = []
    for i, row in enumerate(competitor_rows):
        match = client_rows[best_index[i]]
        gaps.append(
            Gap(
                topic=row["heading"] or row["title"] or "(untitled section)",
                competitor_name=row["site_name"],
                competitor_url=row["final_url"],
                competitor_excerpt=row["text"],
                client_best_score=float(best_score[i]),
                client_best_url=match["final_url"],
                client_best_excerpt=match["text"],
            )
        )

    gaps.sort(key=lambda g: g.gap_size, reverse=True)

    # one entry per topic, so a single long competitor page can't fill the
    # whole report with variations of the same finding
    seen, deduped = {}, []
    for gap in gaps:
        key = (gap.competitor_name, gap.topic)
        if seen.get(key, 0) >= max_per_topic:
            continue
        seen[key] = seen.get(key, 0) + 1
        deduped.append(gap)
        if len(deduped) >= limit:
            break

    return deduped
