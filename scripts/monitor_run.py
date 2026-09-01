"""One monitoring run: re-crawl, diff against last time, report what changed.

This is the command a scheduler calls on a cadence (Windows Task Scheduler
or cron). Everything it needs is in the client config and the database.

Run with:  .venv\\Scripts\\python scripts\\monitor_run.py clients\\pilot.json
Skip the crawl and just report on the last two crawls with --no-crawl.
"""

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.fetch import Crawler
from crawler.site_crawl import crawl_site
from jobs.diff import diff_crawls, latest_two_crawls, summarize, verify_removals
from storage.db import finish_crawl, get_connection, save_page, start_crawl
from synth.changes import generate_change_report

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "reports"


def recrawl(conn, config):
    targets = [(config["client"], "client")]
    targets += [(c, "competitor") for c in config["competitors"]]
    max_pages = config.get("max_pages_per_site", 10)

    crawl_id = start_crawl(conn)
    with Crawler() as crawler:
        for site, role in targets:
            print(f"  crawling {site['name']}...")
            for page in crawl_site(crawler, site["start_url"], max_pages=max_pages):
                save_page(conn, crawl_id, page, site_name=site["name"], site_role=role)
    finish_crawl(conn, crawl_id)
    return crawl_id


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    config_path = Path(args[0]) if args else Path("clients/pilot.json")
    config = json.loads(config_path.read_text())
    client = config["client"]["name"]

    conn = get_connection()

    if "--no-crawl" not in sys.argv:
        print("Re-crawling monitored sites...")
        recrawl(conn, config)

    current, previous = latest_two_crawls(conn)
    if previous is None:
        sys.exit("Only one crawl on record — nothing to compare against yet.")

    print(f"Comparing crawl {previous} -> {current}")
    changes = diff_crawls(conn, current, previous)

    if any(c.status == "removed" for c in changes):
        print("Verifying pages that look removed...")
        with Crawler() as crawler:
            changes = verify_removals(changes, crawler)

    print(summarize(changes))

    markdown = generate_change_report(changes, client)
    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / f"monitoring-{date.today().isoformat()}.md"
    out.write_text(markdown, encoding="utf-8")
    print(f"\nWrote {out}\n")
    print(markdown[:1200])
