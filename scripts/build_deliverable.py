"""Turns a generated Markdown report into the document a client receives.

A .md file is a working artefact, not a deliverable. This wraps the report in
a titled, dated, branded page with an explicit statement of what was and
wasn't measured — so nobody reads "content gaps" and assumes it included
keyword rankings we never bought data for.

Prints to PDF from the browser (Ctrl+P, Save as PDF). That's deliberate: a
real PDF library means heavy native dependencies that are awkward on Windows,
for output no better than what the browser already produces.

Run with:  .venv\\Scripts\\python scripts\\build_deliverable.py reports\\audit-2026-09-02.md clients\\pilot.json
"""

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import markdown

from storage.db import get_connection

TEMPLATE = ROOT / "templates" / "deliverable.html"
CONSULTANT = "The Competitor Dossier"


def build(report_path: Path, config_path: Path) -> Path:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    client = config["client"]["name"]
    competitors = ", ".join(c["name"] for c in config["competitors"])

    conn = get_connection()
    latest = conn.execute(
        "SELECT id FROM crawls WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    stats = conn.execute(
        "SELECT COUNT(*) AS pages, COUNT(DISTINCT site_name) AS sites FROM pages WHERE crawl_id = ?",
        (latest["id"],),
    ).fetchone()

    body = markdown.markdown(
        report_path.read_text(encoding="utf-8"),
        extensions=["tables", "sane_lists"],
    )

    html = TEMPLATE.read_text(encoding="utf-8").format(
        title=f"{client} — Competitor Content Audit",
        client=client,
        competitors=competitors,
        consultant=CONSULTANT,
        date=date.today().strftime("%d %B %Y"),
        body=body,
        pages_crawled=stats["pages"],
        site_count=stats["sites"],
    )

    out = report_path.with_suffix(".html")
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        reports = sorted(ROOT.joinpath("reports").glob("audit-*.md"))
        if not reports:
            sys.exit("No audit reports found. Run scripts/generate_report.py first.")
        report = reports[-1]
    else:
        report = Path(sys.argv[1])

    config = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "clients" / "pilot.json"

    out = build(report, config)
    print(f"Wrote {out}")
    print("Open it in a browser; Ctrl+P then 'Save as PDF' for the client copy.")
