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


def verify(report_path: Path) -> bool:
    cited = set(LINK.findall(report_path.read_text(encoding="utf-8")))
    conn = get_connection()
    crawled = {r["final_url"] for r in conn.execute("SELECT final_url FROM pages")}

    fabricated = sorted(cited - crawled)
    for url in sorted(cited):
        print(("  FABRICATED " if url in fabricated else "  ok         ") + url)

    print(f"\n{len(cited)} cited, {len(fabricated)} not found in crawled pages")
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
