"""Checks that every URL cited in a report is a page we actually crawled.

The plan names hallucination as a top risk: one fabricated claim and a client
stops trusting the whole report. This is the cheap mechanical half of that
defence — a cited URL that was never crawled is a fabrication, no judgement
required. Run it on every report before sending.

Run with:  .venv\\Scripts\\python scripts\\verify_citations.py reports\\audit-2026-09-01.md
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.db import get_connection

LINK = re.compile(r"\]\((https?://[^)\s]+)\)")


def _normalize(url: str) -> str:
    """'/about/' and '/about' are the same page on essentially every site."""
    return url.rstrip("/").lower()


def verify(report_path: Path) -> bool:
    """Fails only on citations to pages we never crawled.

    A URL the model reworded slightly (a trailing slash, different casing)
    still points at a real page we saw, so flagging it as a fabrication would
    be a false alarm — and a check that cries wolf is a check people stop
    reading. Those are reported separately as rewritten, without failing.
    """
    cited = set(LINK.findall(report_path.read_text(encoding="utf-8")))
    conn = get_connection()
    crawled = {r["final_url"] for r in conn.execute("SELECT final_url FROM pages")}
    crawled_normalized = {_normalize(u) for u in crawled}

    fabricated, rewritten = [], []
    for url in sorted(cited):
        if url in crawled:
            print(f"  ok          {url}")
        elif _normalize(url) in crawled_normalized:
            rewritten.append(url)
            print(f"  rewritten   {url}  (real page, model altered the URL)")
        else:
            fabricated.append(url)
            print(f"  FABRICATED  {url}")

    print(
        f"\n{len(cited)} cited, {len(fabricated)} fabricated, "
        f"{len(rewritten)} rewritten but real"
    )
    return not fabricated


if __name__ == "__main__":
    if len(sys.argv) < 2:
        reports = sorted(Path("reports").glob("*.md"))
        if not reports:
            sys.exit("No reports found.")
        path = reports[-1]
    else:
        path = Path(sys.argv[1])

    print(f"Verifying {path}\n")
    sys.exit(0 if verify(path) else 1)
