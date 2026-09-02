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

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL REFERENCES pages(id),
    ordinal INTEGER NOT NULL,
    heading TEXT,
    text TEXT NOT NULL,
    embedding BLOB NOT NULL  -- float32 vector, packed as raw bytes
);

-- derived from stored HTML, so it can be recomputed any time without
-- re-crawling. One row per page; re-running enrichment replaces it.
CREATE TABLE IF NOT EXISTS page_signals (
    page_id INTEGER PRIMARY KEY REFERENCES pages(id),
    title_tag TEXT,
    title_length INTEGER,
    meta_description TEXT,
    meta_description_length INTEGER,
    h1_count INTEGER,
    h1_text TEXT,
    h2_count INTEGER,
    word_count INTEGER,
    internal_links INTEGER,
    external_links INTEGER,
    has_canonical INTEGER,
    has_structured_data INTEGER
);

-- every URL a site lists in its own sitemap. Far wider than what we crawl:
-- the crawl samples pages, this records the site's whole declared inventory.
CREATE TABLE IF NOT EXISTS sitemap_urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_id INTEGER NOT NULL REFERENCES crawls(id),
    site_name TEXT NOT NULL,
    site_role TEXT NOT NULL,
    url TEXT NOT NULL,
    lastmod TEXT
);

CREATE INDEX IF NOT EXISTS idx_sitemap_crawl ON sitemap_urls(crawl_id, site_name);
CREATE INDEX IF NOT EXISTS idx_chunks_page_id ON chunks(page_id);
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


def save_chunks(conn: sqlite3.Connection, page_id: int, chunks, embeddings) -> int:
    """Stores a page's chunks alongside their embedding vectors."""
    from ingest.embed import to_blob

    conn.executemany(
        "INSERT INTO chunks (page_id, ordinal, heading, text, embedding) VALUES (?, ?, ?, ?, ?)",
        [
            (page_id, c.ordinal, c.heading, c.text, to_blob(vec))
            for c, vec in zip(chunks, embeddings)
        ],
    )
    conn.commit()
    return len(chunks)


def save_signals(conn: sqlite3.Connection, page_id: int, signals) -> None:
    """Stores one page's on-page SEO signals. `signals` is enrichment.onpage.PageSignals."""
    conn.execute(
        """
        INSERT OR REPLACE INTO page_signals
            (page_id, title_tag, title_length, meta_description, meta_description_length,
             h1_count, h1_text, h2_count, word_count, internal_links, external_links,
             has_canonical, has_structured_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            page_id,
            signals.title_tag,
            signals.title_length,
            signals.meta_description,
            signals.meta_description_length,
            signals.h1_count,
            signals.h1_text,
            signals.h2_count,
            signals.word_count,
            signals.internal_links,
            signals.external_links,
            int(signals.has_canonical),
            int(signals.has_structured_data),
        ),
    )
    conn.commit()


def save_sitemap_urls(conn, crawl_id: int, site_name: str, site_role: str, entries) -> int:
    """Replaces this crawl's sitemap inventory for one site."""
    conn.execute(
        "DELETE FROM sitemap_urls WHERE crawl_id = ? AND site_name = ?", (crawl_id, site_name)
    )
    conn.executemany(
        "INSERT INTO sitemap_urls (crawl_id, site_name, site_role, url, lastmod) VALUES (?, ?, ?, ?, ?)",
        [
            (crawl_id, site_name, site_role, e.url, e.lastmod.isoformat() if e.lastmod else None)
            for e in entries
        ],
    )
    conn.commit()
    return len(entries)


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
