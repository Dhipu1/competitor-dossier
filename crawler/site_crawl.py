"""Crawls a whole site by following its own internal links.

Starts at one URL, fetches it, looks at the links that page pointed to,
adds any new same-domain ones to a queue, and repeats — a breadth-first
search over the site's link graph. Stops once max_pages have been fetched
so we don't accidentally try to crawl an entire large site.
"""

from urllib.parse import urlparse

from crawler.fetch import Crawler, FetchedPage

# link paths that are never worth fetching as a "page" — files, not content
_SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".zip", ".mp4", ".mp3", ".css", ".js", ".xml", ".json",
)


def _normalize(url: str) -> str:
    """Drops the #fragment part of a URL — '/blog#comments' is the same page as '/blog'."""
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl()


def _domain_key(netloc: str) -> str:
    """Treats 'www.example.com' and 'example.com' as the same site."""
    return netloc.lower().removeprefix("www.")


def _is_crawlable(url: str, allowed_domain_key: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False  # skips mailto:, tel:, javascript:, etc.
    if _domain_key(parsed.netloc) != allowed_domain_key:
        return False  # stay on this one site — don't wander onto other domains
    if parsed.path.lower().endswith(_SKIP_EXTENSIONS):
        return False
    return True


def crawl_site(crawler: Crawler, start_url: str, *, max_pages: int = 15):
    """Yields FetchedPage objects for up to max_pages on the same site as start_url."""
    seen = {_normalize(start_url)}
    queue = [start_url]
    fetched = 0
    allowed_domain_key = None  # set once we know where start_url actually lands

    while queue and fetched < max_pages:
        url = queue.pop(0)
        page: FetchedPage = crawler.fetch(url)
        if page is None:
            continue

        # different URLs can land on the same page (redirects, or a trailing
        # slash) — dedupe on where we actually ended up, not what we asked for
        landed = _normalize(page.final_url)
        already_have = landed in seen and landed != _normalize(url)
        seen.add(landed)
        if already_have:
            continue

        fetched += 1
        yield page

        if allowed_domain_key is None:
            # sites commonly redirect https://example.com -> https://www.example.com;
            # anchor "same site" to where we landed, not where we started, so links
            # discovered on the (possibly www-prefixed) landing page still match
            allowed_domain_key = _domain_key(urlparse(page.final_url).netloc)

        for link in page.links:
            link = _normalize(link)
            if link in seen:
                continue
            if not _is_crawlable(link, allowed_domain_key):
                continue
            seen.add(link)
            queue.append(link)
