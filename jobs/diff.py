"""Compares two crawls to find what changed on the monitored sites.

This is what makes the monitoring retainer economically different from the
audit. A full audit reasons over every chunk of every site. A monitoring run
reasons only over pages that actually changed — usually a handful — so the
LLM cost of a monthly check is a fraction of the initial audit, while the
crawl cost stays roughly the same.

Comparison is by content_hash, the fingerprint stored with each page. Equal
hashes mean identical text, so unchanged pages are ruled out without
comparing a single word.
"""

import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Tuple

NEW = "new"
CHANGED = "changed"
REMOVED = "removed"
NOT_CHECKED = "not_checked"  # absent this run, but the page is still live


@dataclass
class PageChange:
    status: str            # new | changed | removed
    site_name: str
    site_role: str
    url: str
    title: Optional[str]
    previous_text: Optional[str]
    current_text: Optional[str]


def latest_two_crawls(conn: sqlite3.Connection) -> Tuple[Optional[int], Optional[int]]:
    """Returns (current_crawl_id, previous_crawl_id); either may be None."""
    rows = conn.execute(
        "SELECT id FROM crawls WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 2"
    ).fetchall()
    current = rows[0]["id"] if rows else None
    previous = rows[1]["id"] if len(rows) > 1 else None
    return current, previous


def _pages_by_url(conn: sqlite3.Connection, crawl_id: int) -> dict:
    rows = conn.execute(
        """
        SELECT site_name, site_role, final_url, title, text, content_hash
        FROM pages WHERE crawl_id = ?
        """,
        (crawl_id,),
    ).fetchall()
    return {r["final_url"]: r for r in rows}


def diff_crawls(conn: sqlite3.Connection, current_id: int, previous_id: int) -> List[PageChange]:
    """Lists pages added, removed, or edited between two crawls."""
    current = _pages_by_url(conn, current_id)
    previous = _pages_by_url(conn, previous_id)

    changes = []

    for url, page in current.items():
        before = previous.get(url)
        if before is None:
            changes.append(
                PageChange(NEW, page["site_name"], page["site_role"], url,
                           page["title"], None, page["text"])
            )
        elif before["content_hash"] != page["content_hash"]:
            changes.append(
                PageChange(CHANGED, page["site_name"], page["site_role"], url,
                           page["title"], before["text"], page["text"])
            )

    for url, page in previous.items():
        if url not in current:
            changes.append(
                PageChange(REMOVED, page["site_name"], page["site_role"], url,
                           page["title"], page["text"], None)
            )

    # competitors first: a competitor publishing something new is the signal
    # the client pays to hear about
    order = {NEW: 0, CHANGED: 1, REMOVED: 2, NOT_CHECKED: 3}
    changes.sort(key=lambda c: (c.site_role != "competitor", order[c.status], c.site_name))
    return changes


def verify_removals(changes: List[PageChange], crawler) -> List[PageChange]:
    """Re-fetches pages that look removed, to confirm they actually are.

    A page missing from this crawl usually means we simply didn't reach it:
    crawls stop at max_pages, and which pages fit varies run to run. Reporting
    that as "your competitor deleted a page" would be a false alarm, and a
    monitoring retainer that cries wolf every month is worth nothing.

    So we go and look. Still live -> not_checked. Actually gone -> removed.
    """
    verified = []
    for change in changes:
        if change.status != REMOVED:
            verified.append(change)
            continue

        still_live = crawler.fetch(change.url) is not None
        verified.append(
            PageChange(
                NOT_CHECKED if still_live else REMOVED,
                change.site_name,
                change.site_role,
                change.url,
                change.title,
                change.previous_text,
                change.current_text,
            )
        )
    return verified


def summarize(changes: List[PageChange]) -> str:
    counts = {NEW: 0, CHANGED: 0, REMOVED: 0, NOT_CHECKED: 0}
    for change in changes:
        counts[change.status] += 1
    return (
        f"{counts[NEW]} new, {counts[CHANGED]} changed, {counts[REMOVED]} removed"
        f" ({counts[NOT_CHECKED]} not reached this run)"
    )
