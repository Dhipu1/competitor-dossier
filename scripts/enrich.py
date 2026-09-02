"""Extracts on-page SEO signals from pages already in the database.

Costs nothing and touches no one's server — it reads the HTML we stored
during the crawl. Safe to re-run any time you change what gets extracted.

Run with:  .venv\\Scripts\\python scripts\\enrich.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from enrichment.onpage import extract_signals
from storage.db import get_connection, save_signals

if __name__ == "__main__":
    conn = get_connection()

    latest = conn.execute(
        "SELECT id FROM crawls WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if latest is None:
        sys.exit("No finished crawls found. Run scripts/crawl_pilot.py first.")

    pages = conn.execute(
        "SELECT id, site_name, final_url, html, text FROM pages WHERE crawl_id = ?",
        (latest["id"],),
    ).fetchall()

    print(f"Extracting signals from {len(pages)} pages in crawl {latest['id']}...")

    done = failed = 0
    for page in pages:
        if not page["html"]:
            failed += 1
            continue
        try:
            signals = extract_signals(page["html"], page["final_url"], page["text"])
        except Exception as e:  # a malformed page shouldn't stop the run
            print(f"  [skip] {page['final_url']}: {type(e).__name__}")
            failed += 1
            continue
        save_signals(conn, page["id"], signals)
        done += 1

    print(f"Extracted {done} pages ({failed} skipped).")
