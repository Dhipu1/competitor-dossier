"""Chunks every stored page and embeds the chunks.

Runs entirely off what's already in dossier.db — no crawling, so it's safe
to re-run whenever chunking or embedding changes.

Run with:  .venv\\Scripts\\python scripts\\build_index.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest.chunk import chunk_page
from ingest.embed import embed_texts
from storage.db import get_connection, save_chunks

if __name__ == "__main__":
    conn = get_connection()

    # rebuilding from scratch each run keeps this idempotent — re-running
    # can't leave stale chunks from an older chunking strategy behind
    conn.execute("DELETE FROM chunks")
    conn.commit()

    # index the most recent finished crawl only. Indexing every page ever
    # crawled would mix this month's snapshot with last month's and count the
    # same page repeatedly — an audit describes the sites as they are now.
    latest = conn.execute(
        "SELECT id FROM crawls WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if latest is None:
        sys.exit("No finished crawls found. Run scripts/crawl_pilot.py first.")

    pages = conn.execute(
        "SELECT id, site_name, title, text FROM pages WHERE crawl_id = ?", (latest["id"],)
    ).fetchall()
    print(f"Chunking {len(pages)} pages from crawl {latest['id']}...")

    all_chunks = []  # (page_id, chunk) pairs, embedded together in one batch
    for page in pages:
        for chunk in chunk_page(page["text"]):
            all_chunks.append((page["id"], chunk))

    print(f"{len(all_chunks)} chunks. Embedding (first run downloads the model)...")
    start = time.time()
    vectors = embed_texts([c.embedding_text() for _, c in all_chunks])
    print(f"Embedded in {time.time() - start:.1f}s -> {vectors.shape}")

    by_page = {}
    for (page_id, chunk), vec in zip(all_chunks, vectors):
        by_page.setdefault(page_id, ([], []))
        by_page[page_id][0].append(chunk)
        by_page[page_id][1].append(vec)

    for page_id, (chunks, vecs) in by_page.items():
        save_chunks(conn, page_id, chunks, vecs)

    print(f"Saved {len(all_chunks)} chunks across {len(by_page)} pages.")
