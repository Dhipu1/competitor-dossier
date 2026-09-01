"""Crawls the client + competitor sites listed in a client config file.

Run with:  .venv\\Scripts\\python scripts\\crawl_pilot.py clients\\pilot.json
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.fetch import Crawler
from crawler.site_crawl import crawl_site
from storage.db import finish_crawl, get_connection, save_page, start_crawl


def run(config_path: Path):
    config = json.loads(config_path.read_text())
    max_pages = config.get("max_pages_per_site", 10)

    targets = [(config["client"], "client")]
    targets += [(c, "competitor") for c in config["competitors"]]

    conn = get_connection()
    crawl_id = start_crawl(conn)

    with Crawler() as crawler:
        for site, role in targets:
            print(f"\n=== Crawling {site['name']} ({role}) ===")
            start = time.time()
            count = 0
            for page in crawl_site(crawler, site["start_url"], max_pages=max_pages):
                save_page(conn, crawl_id, page, site_name=site["name"], site_role=role)
                count += 1
                print(f"  [{count}] {page.title or '(no title)'} — {page.final_url}")
            elapsed = time.time() - start
            print(f"  -> {count} pages in {elapsed:.1f}s")

    finish_crawl(conn, crawl_id)
    print(f"\nDone. crawl_id={crawl_id}, saved in dossier.db")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("clients/pilot.json")
    run(path)
