"""Reads a site's sitemap to learn its full content inventory and cadence.

This is the highest-value free signal in the whole pipeline. Our crawl only
samples a handful of pages per site, so it cannot tell you whether a
competitor has 12 pages or 1,200. A sitemap is the site's own list of every
URL it wants indexed, and most include a lastmod date per URL.

That gives an audit two things no amount of crawling a sample can:
  - scale:   "they publish 340 pages, you have 45"
  - cadence: "they shipped 22 pages in the last 90 days, you shipped 1"

Cadence is often the finding that lands hardest with a client, because it
reframes a content gap as a trend that is still widening.

Caveats worth stating in a report: sitemaps are self-declared, may be
incomplete, and lastmod is set by the site's own CMS — a site-wide template
change can restamp every page. Treat these as strong indicators, not gospel.
"""

import gzip
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse

import lxml.etree

from crawler.robots import USER_AGENT, sitemaps_for

# Sitemaps use an XML namespace; every tag we want is inside it.
_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

_MAX_SITEMAPS = 25       # a sitemap index can point at hundreds; sample enough
_MAX_URLS = 5_000        # big sites publish huge sitemaps — we only need scale


@dataclass
class SitemapEntry:
    url: str
    lastmod: Optional[datetime]


def _parse_lastmod(value: Optional[str]) -> Optional[datetime]:
    """Sitemap dates may be '2026-04-01' or a full timestamp with a timezone."""
    if not value:
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    # compare everything in UTC; dates without a timezone are assumed UTC
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _fetch(url: str) -> Optional[bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read()
    except (urllib.error.URLError, OSError):
        return None
    # sitemaps are commonly served gzipped, sometimes without a helpful header
    if url.endswith(".gz") or body[:2] == b"\x1f\x8b":
        try:
            body = gzip.decompress(body)
        except OSError:
            return None
    return body


def _parse(body: bytes):
    """Parses sitemap XML from an untrusted third-party server.

    Entities and network access are disabled: XML parsers that resolve
    external entities can be talked into reading local files or hammering
    other hosts on the document's say-so. We only need plain elements here,
    so the safest parser is also the sufficient one.
    """
    parser = lxml.etree.XMLParser(
        resolve_entities=False, no_network=True, huge_tree=False, recover=True
    )
    try:
        return lxml.etree.fromstring(body, parser=parser)
    except lxml.etree.XMLSyntaxError:
        return None


def _candidate_sitemaps(start_url: str) -> List[str]:
    """Sitemaps advertised in robots.txt, else the conventional location."""
    advertised = sitemaps_for(start_url)
    if advertised:
        return advertised
    parsed = urlparse(start_url)
    return [f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"]


def fetch_inventory(start_url: str) -> List[SitemapEntry]:
    """Returns every URL a site lists in its sitemap(s), following index files."""
    queue = _candidate_sitemaps(start_url)
    seen_sitemaps = set()
    entries: List[SitemapEntry] = []

    while queue and len(seen_sitemaps) < _MAX_SITEMAPS and len(entries) < _MAX_URLS:
        sitemap_url = queue.pop(0)
        if sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)

        body = _fetch(sitemap_url)
        if body is None:
            continue
        root = _parse(body)
        if root is None:
            continue

        # A sitemap index lists other sitemaps rather than pages; queue those.
        nested = root.xpath("//sm:sitemap/sm:loc/text()", namespaces=_NS)
        for child in nested:
            queue.append(child.strip())

        for node in root.xpath("//sm:url", namespaces=_NS):
            loc = node.xpath("sm:loc/text()", namespaces=_NS)
            if not loc:
                continue
            lastmod = node.xpath("sm:lastmod/text()", namespaces=_NS)
            entries.append(
                SitemapEntry(
                    url=loc[0].strip(),
                    lastmod=_parse_lastmod(lastmod[0] if lastmod else None),
                )
            )
            if len(entries) >= _MAX_URLS:
                break

    return entries
