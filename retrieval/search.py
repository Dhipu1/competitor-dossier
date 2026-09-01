"""Finds the chunks most relevant to a question.

How it works: embed the question into a vector, then compare it against every
stored chunk vector and keep the closest. Because all vectors are unit length,
"closeness" is a single multiply-and-add per chunk (a dot product), scored
0-1 where higher means more similar in meaning.

Comparing against every chunk sounds wasteful, but at this scale it's
microseconds. Dedicated vector databases start earning their complexity in
the millions of chunks; we're in the hundreds.
"""

import sqlite3
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from ingest.embed import embed_query, from_blob


@dataclass
class SearchResult:
    score: float
    site_name: str
    site_role: str
    url: str
    page_title: Optional[str]
    heading: Optional[str]
    text: str


def search(
    conn: sqlite3.Connection,
    query: str,
    *,
    top_k: int = 5,
    site_role: Optional[str] = None,
    site_name: Optional[str] = None,
) -> List[SearchResult]:
    """Returns the top_k chunks closest in meaning to `query`.

    site_role / site_name narrow the search to one side of the comparison —
    which is the whole point of a competitor audit: ask the same question of
    the client's content and the competitors' content, then compare answers.
    """
    sql = """
        SELECT c.heading, c.text, c.embedding,
               p.site_name, p.site_role, p.final_url, p.title
        FROM chunks c
        JOIN pages p ON p.id = c.page_id
    """
    conditions, params = [], []
    if site_role:
        conditions.append("p.site_role = ?")
        params.append(site_role)
    if site_name:
        conditions.append("p.site_name = ?")
        params.append(site_name)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return []

    matrix = np.vstack([from_blob(r["embedding"]) for r in rows])
    scores = matrix @ embed_query(query)  # one dot product per chunk, vectorised

    best = np.argsort(scores)[::-1][:top_k]
    return [
        SearchResult(
            score=float(scores[i]),
            site_name=rows[i]["site_name"],
            site_role=rows[i]["site_role"],
            url=rows[i]["final_url"],
            page_title=rows[i]["title"],
            heading=rows[i]["heading"],
            text=rows[i]["text"],
        )
        for i in best
    ]
