"""Fetches pages with a real browser and extracts their main content.

Why a real browser instead of a plain HTTP request (e.g. `requests.get`)?
Many sites render their actual content with JavaScript after the initial
HTML loads. A plain request only sees the empty shell; Playwright waits
for the page to actually finish rendering, like a human's browser would.
"""

import time
from dataclasses import dataclass
from typing import Optional

import trafilatura
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from crawler.robots import USER_AGENT, can_fetch, crawl_delay


@dataclass
class FetchedPage:
    url: str          # the URL we asked for
    final_url: str     # where we ended up, after any redirects
    html: str           # raw rendered HTML
    title: Optional[str]
    text: Optional[str]  # main content only — nav/ads/footers stripped out
    links: list           # every <a href> on the page, as absolute URLs


class Crawler:
    """Opens one browser and reuses it for every page you fetch.

    Use as a context manager so the browser always gets closed, even if
    something raises partway through a crawl:

        with Crawler() as crawler:
            page = crawler.fetch("https://example.com")
    """

    def __init__(self, headless: bool = True):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=headless)

    def fetch(self, url: str, *, timeout_ms: int = 30_000) -> Optional[FetchedPage]:
        """Loads `url` and returns its content, or None if we shouldn't/can't fetch it."""
        if not can_fetch(url):
            print(f"[skip] robots.txt disallows: {url}")
            return None

        delay = crawl_delay(url)
        if delay:
            time.sleep(delay)

        page = self._browser.new_page(user_agent=USER_AGENT)
        try:
            # "networkidle" (wait for zero network activity) sounds ideal but
            # times out on plenty of real sites — analytics beacons, chat
            # widgets, and polling connections mean network activity often
            # never fully stops. "load" (the browser's load event) is what
            # every plain browser waits for and is far more reliable.
            response = page.goto(url, wait_until="load", timeout=timeout_ms)
            if response is None or not response.ok:
                status = response.status if response else "no response"
                print(f"[fail] {url} -> {status}")
                return None
            html = page.content()
            final_url = page.url
            # asks the already-loaded page for every link's fully-resolved
            # absolute URL, the same as reading each <a href> ourselves but
            # letting the browser do the relative-URL math for us
            links = page.eval_on_selector_all("a[href]", "els => els.map(el => el.href)")
        except PlaywrightTimeoutError:
            print(f"[fail] {url} -> timed out")
            return None
        finally:
            page.close()

        extracted = trafilatura.extract(
            html, url=final_url, include_comments=False, with_metadata=True
        )
        metadata = trafilatura.extract_metadata(html, default_url=final_url)
        title = metadata.title if metadata else None

        return FetchedPage(
            url=url, final_url=final_url, html=html, title=title, text=extracted, links=links
        )

    def close(self):
        self._browser.close()
        self._playwright.stop()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
