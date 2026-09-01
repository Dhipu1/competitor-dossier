"""SQLite storage for crawled pages.

Two tables:
  crawls - one row per crawl run (a timestamp, basically a batch marker)
  pages  - one row per page fetched during a crawl

Why a content_hash column? Later (monitoring retainer, Phase 5) we need to
answer "did this page change since last month?" without diffing the full
text of every page against every past version. A hash is a short fixed-
length fingerprint of the text — same input always produces the same hash,
and any change to the input, even one character, produces a completely
different hash. So "did it change?" becomes a cheap string comparison
instead of comparing potentially thousands of words of text.
"""

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "dossier.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS crawls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_id INTEGER NOT NULL REFERENCES crawls(id),
    site_name TEXT NOT NULL,
    site_role TEXT NOT NULL,  -- 'client' or 'competitor'
    url TEXT NOT NULL,
    final_url TEXT NOT NULL,
    title TEXT,
    html TEXT,   -- raw page HTML, kept so we can re-extract/re-chunk later
    text TEXT,   -- main content, nav/ads/footers stripped
    content_hash TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url);
CREATE INDEX IF NOT EXISTS idx_pages_content_hash ON pages(content_hash);
CREATE INDEX IF NOT EXISTS idx_pages_site_name ON pages(site_name);
"""


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # lets us access columns by name, e.g. row["title"]
    conn.executescript(SCHEMA)
    return conn


def hash_text(text: Optional[str]) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def start_crawl(conn: sqlite3.Connection) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute("INSERT INTO crawls (started_at) VALUES (?)", (now,))
    conn.commit()
    return cursor.lastrowid


def finish_crawl(conn: sqlite3.Connection, crawl_id: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("UPDATE crawls SET finished_at = ? WHERE id = ?", (now, crawl_id))
    conn.commit()


def save_page(conn: sqlite3.Connection, crawl_id: int, page, *, site_name: str, site_role: str) -> int:
    """Stores one fetched page. `page` is a crawler.fetch.FetchedPage."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO pages
            (crawl_id, site_name, site_role, url, final_url, title, html, text,
             content_hash, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            crawl_id,
            site_name,
            site_role,
            page.url,
            page.final_url,
            page.title,
            page.html,
            page.text,
            hash_text(page.text),
            now,
        ),
    )
    conn.commit()
    return cursor.lastrowid
