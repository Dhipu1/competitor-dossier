"""Manual check that the crawler works end-to-end against a real page.

Run with:  .venv\\Scripts\\python scripts\\smoke_test_crawl.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.fetch import Crawler
from storage.db import finish_crawl, get_connection, save_page, start_crawl

TEST_URL = "https://en.wikipedia.org/wiki/Web_scraping"

if __name__ == "__main__":
    with Crawler() as crawler:
        page = crawler.fetch(TEST_URL)

    if page is None:
        print("Fetch failed or was disallowed by robots.txt.")
        sys.exit(1)

    print(f"URL:   {page.final_url}")
    print(f"Title: {page.title}")
    print(f"HTML length:  {len(page.html):,} chars")
    print(f"Text length:  {len(page.text or ''):,} chars")
    print("\n--- first 400 chars of extracted text ---")
    print((page.text or "")[:400])

    conn = get_connection()
    crawl_id = start_crawl(conn)
    page_id = save_page(conn, crawl_id, page)
    finish_crawl(conn, crawl_id)
    print(f"\nSaved as page id {page_id} under crawl id {crawl_id} in dossier.db")
