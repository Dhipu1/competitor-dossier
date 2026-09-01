"""Checks a site's robots.txt before we crawl it.

robots.txt is a plain-text file site owners publish at /robots.txt to say
which pages bots may or may not fetch. We ask permission before every page.
"""

import urllib.error
import urllib.request
from functools import lru_cache
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

USER_AGENT = "CompetitorDossierBot/0.1 (+contact: sridhipthan@gmail.com)"


@lru_cache(maxsize=None)
def _parser_for(origin: str) -> RobotFileParser:
    """One robots.txt fetch per site, then reused for every page on that site.

    We fetch the file ourselves (with our real User-Agent) rather than letting
    RobotFileParser.read() do it: that method sends Python's generic default
    User-Agent, which some sites (Wikipedia included) block with a 403 — and
    Python's parser treats a failed fetch as "disallow everything", which is
    the opposite of what we want when a site simply has no robots.txt rules
    against us.
    """
    parser = RobotFileParser()
    parser.set_url(f"{origin}/robots.txt")

    request = urllib.request.Request(
        f"{origin}/robots.txt", headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
        parser.parse(body.splitlines())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            parser.disallow_all = True  # explicitly forbidden from even checking
        # any other error (e.g. 404) leaves the parser with no rules, which
        # RobotFileParser correctly treats as "everything allowed"
    except OSError:
        pass  # network failure — default to allowing, same reasoning as above

    return parser


def can_fetch(url: str) -> bool:
    """True if robots.txt allows our bot to fetch this specific URL."""
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return _parser_for(origin).can_fetch(USER_AGENT, url)


def crawl_delay(url: str) -> float:
    """Seconds robots.txt asks us to wait between requests to this site (0 if unspecified)."""
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    delay = _parser_for(origin).crawl_delay(USER_AGENT)
    return float(delay) if delay else 0.0
