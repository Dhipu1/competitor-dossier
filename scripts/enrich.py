"""Adds the free enrichment layer to a crawl.

Two parts:
  on-page signals — read from HTML already in the database, so no network
  sitemap inventory — one small request per site, for scale and cadence

Safe to re-run any time you change what gets extracted.

Run with:  .venv\\Scripts\\python scripts\\enrich.py
Skip the sitemap fetch (fully offline) with --no-sitemap.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from enrichment.inventory import summarize
from enrichment.onpage import extract_signals
from enrichment.sitemap import fetch_inventory
from storage.db import get_connection, save_signals, save_sitemap_urls

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

    if "--no-sitemap" not in sys.argv:
        print("\nFetching sitemaps...")
        sites = conn.execute(
            """
            SELECT site_name, site_role, MIN(final_url) AS any_url
            FROM pages WHERE crawl_id = ? GROUP BY site_name, site_role
            """,
            (latest["id"],),
        ).fetchall()

        for site in sites:
            entries = fetch_inventory(site["any_url"])
            save_sitemap_urls(conn, latest["id"], site["site_name"], site["site_role"], entries)
            if entries:
                print(f"  {site['site_name']}: {len(entries)} URLs listed")
            else:
                # not an error: plenty of sites publish no sitemap at all
                print(f"  {site['site_name']}: no sitemap published")

    print("\nInventory:")
    for inv in summarize(conn, latest["id"]):
        if not inv.has_sitemap:
            print(f"  {inv.site_name:<22} no sitemap — scale unknown, crawl sample only")
            continue
        newest = inv.newest.date() if inv.newest else "unknown"
        print(
            f"  {inv.site_name:<22} {inv.total_urls:>4} URLs | "
            f"last 30d: {inv.published_30d:>3} | 90d: {inv.published_90d:>3} | "
            f"365d: {inv.published_365d:>3} | newest: {newest}"
        )
