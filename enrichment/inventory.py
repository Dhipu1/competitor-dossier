"""Turns raw sitemap URLs into the scale and cadence numbers an audit uses.

Two questions this answers that a page sample never can:
  how much have they published, and how recently.

Everything here is measured from data we collected. Where a site publishes
no sitemap, that is reported as unknown rather than guessed at — an audit
that quietly treats "we couldn't measure it" as "they have nothing" is an
audit that will eventually be wrong in front of a client.
"""

import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import urlparse


@dataclass
class SiteInventory:
    site_name: str
    site_role: str
    total_urls: int
    dated_urls: int
    published_30d: int
    published_90d: int
    published_365d: int
    newest: Optional[datetime]
    top_sections: List[tuple]     # (section, count), biggest first

    @property
    def has_sitemap(self) -> bool:
        return self.total_urls > 0


def _section(url: str) -> str:
    """First path segment — '/blog/silksong-patch-5' -> 'blog'. Site's own grouping."""
    parts = [p for p in urlparse(url).path.split("/") if p]
    return parts[0] if parts else "(home)"


def summarize(conn: sqlite3.Connection, crawl_id: int) -> List[SiteInventory]:
    """One inventory summary per site in this crawl."""
    sites = conn.execute(
        "SELECT DISTINCT site_name, site_role FROM pages WHERE crawl_id = ? ORDER BY site_role, site_name",
        (crawl_id,),
    ).fetchall()

    now = datetime.now(timezone.utc)
    summaries = []

    for site in sites:
        rows = conn.execute(
            "SELECT url, lastmod FROM sitemap_urls WHERE crawl_id = ? AND site_name = ?",
            (crawl_id, site["site_name"]),
        ).fetchall()

        dates = []
        for row in rows:
            if row["lastmod"]:
                try:
                    dates.append(datetime.fromisoformat(row["lastmod"]))
                except ValueError:
                    pass

        def within(days: int) -> int:
            cutoff = now - timedelta(days=days)
            return sum(1 for d in dates if d >= cutoff)

        summaries.append(
            SiteInventory(
                site_name=site["site_name"],
                site_role=site["site_role"],
                total_urls=len(rows),
                dated_urls=len(dates),
                published_30d=within(30),
                published_90d=within(90),
                published_365d=within(365),
                newest=max(dates) if dates else None,
                top_sections=Counter(_section(r["url"]) for r in rows).most_common(5),
            )
        )

    return summaries
