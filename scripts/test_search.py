"""Checks retrieval quality against known-answer questions.

The queries deliberately avoid the exact words used on the pages — if
keyword overlap were doing the work, embeddings wouldn't be earning
their keep.

Run with:  .venv\\Scripts\\python scripts\\test_search.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.search import search
from storage.db import get_connection

QUERIES = [
    "who founded the studio and where are they based",
    "are they hiring, what roles are open",
    "what did they say about a recent patch or update",
    "do they sell physical merchandise",
]

if __name__ == "__main__":
    conn = get_connection()
    for query in QUERIES:
        print(f"\n=== {query!r}")
        for r in search(conn, query, top_k=3):
            snippet = " ".join(r.text.split())[:100]
            print(f"  {r.score:.3f}  [{r.site_name}] {r.heading or r.page_title}")
            print(f"         {snippet}...")
