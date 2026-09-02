"""Extracts on-page SEO signals from HTML we already crawled.

None of this costs anything or touches the network: the raw HTML is already
in the database, so this reads what we stored. Paid SEO APIs sell ranking
and search-volume data, which genuinely can't be derived from a page. But a
lot of what an audit needs *is* sitting in the markup, and throwing it away
would mean paying for something we already have.

What these signals answer:
  - title / meta description: are they present, and the right length? Search
    engines truncate long ones, and a missing description means the engine
    writes its own snippet. Cheap, concrete fixes for a client.
  - h1: one per page is the convention. Zero means nothing states the page's
    subject; several means nothing stands out as the subject.
  - word count: content depth, the honest version — measured on extracted
    main content, not raw HTML, so navigation and scripts don't inflate it.
  - internal links: a site's own vote on which of its pages matter.
"""

import sqlite3
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse

import lxml.html


@dataclass
class PageSignals:
    title_tag: Optional[str]
    title_length: int
    meta_description: Optional[str]
    meta_description_length: int
    h1_count: int
    h1_text: Optional[str]
    h2_count: int
    word_count: int
    internal_links: int
    external_links: int
    has_canonical: bool
    has_structured_data: bool


@dataclass
class SiteSignals:
    """On-page signals averaged across the pages we sampled for one site."""
    site_name: str
    site_role: str
    pages: int
    avg_words: float
    pages_missing_description: int
    pages_missing_h1: int
    pages_multiple_h1: int
    pages_with_structured_data: int
    avg_internal_links: float


def aggregate_by_site(conn: sqlite3.Connection, crawl_id: int) -> List[SiteSignals]:
    """Rolls per-page signals up to one row per site, for report comparisons."""
    rows = conn.execute(
        """
        SELECT p.site_name, p.site_role,
               COUNT(*) AS pages,
               AVG(s.word_count) AS avg_words,
               SUM(CASE WHEN s.meta_description IS NULL OR s.meta_description = '' THEN 1 ELSE 0 END) AS no_desc,
               SUM(CASE WHEN s.h1_count = 0 THEN 1 ELSE 0 END) AS no_h1,
               SUM(CASE WHEN s.h1_count > 1 THEN 1 ELSE 0 END) AS multi_h1,
               SUM(s.has_structured_data) AS schema_pages,
               AVG(s.internal_links) AS avg_internal
        FROM page_signals s JOIN pages p ON p.id = s.page_id
        WHERE p.crawl_id = ?
        GROUP BY p.site_name, p.site_role
        ORDER BY p.site_role, p.site_name
        """,
        (crawl_id,),
    ).fetchall()

    return [
        SiteSignals(
            site_name=r["site_name"],
            site_role=r["site_role"],
            pages=r["pages"],
            avg_words=round(r["avg_words"] or 0, 1),
            pages_missing_description=r["no_desc"],
            pages_missing_h1=r["no_h1"],
            pages_multiple_h1=r["multi_h1"],
            pages_with_structured_data=r["schema_pages"],
            avg_internal_links=round(r["avg_internal"] or 0, 1),
        )
        for r in rows
    ]


def _first_text(nodes) -> Optional[str]:
    for node in nodes:
        text = " ".join((node.text_content() or "").split())
        if text:
            return text
    return None


def extract_signals(html: str, final_url: str, text: Optional[str]) -> PageSignals:
    """Reads on-page signals out of one page's stored HTML."""
    doc = lxml.html.fromstring(html)
    domain = urlparse(final_url).netloc.lower().removeprefix("www.")

    title_tag = _first_text(doc.xpath("//title"))

    description_nodes = doc.xpath("//meta[translate(@name,'DESCRIPTION','description')='description']/@content")
    meta_description = " ".join(description_nodes[0].split()) if description_nodes else None

    h1_nodes = doc.xpath("//h1")
    h1_text = _first_text(h1_nodes)

    internal = external = 0
    for href in doc.xpath("//a[@href]/@href"):
        parsed = urlparse(href)
        if parsed.scheme and parsed.scheme not in ("http", "https"):
            continue  # mailto:, tel:, javascript:
        if not parsed.netloc:
            internal += 1  # relative link, so same site by definition
        elif parsed.netloc.lower().removeprefix("www.") == domain:
            internal += 1
        else:
            external += 1

    return PageSignals(
        title_tag=title_tag,
        title_length=len(title_tag or ""),
        meta_description=meta_description,
        meta_description_length=len(meta_description or ""),
        h1_count=len(h1_nodes),
        h1_text=h1_text,
        h2_count=len(doc.xpath("//h2")),
        word_count=len((text or "").split()),
        internal_links=internal,
        external_links=external,
        has_canonical=bool(doc.xpath("//link[@rel='canonical']/@href")),
        has_structured_data=bool(doc.xpath("//script[@type='application/ld+json']")),
    )
