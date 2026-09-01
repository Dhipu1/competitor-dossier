"""Generates the audit report and writes it to reports/.

Run with:  .venv\\Scripts\\python scripts\\generate_report.py
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.db import get_connection
from synth.report import generate_report

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "reports"

if __name__ == "__main__":
    conn = get_connection()
    print("Finding gaps and generating report...")
    markdown = generate_report(conn)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / f"audit-{date.today().isoformat()}.md"
    out.write_text(markdown, encoding="utf-8")

    print(f"Wrote {out} ({len(markdown):,} chars)\n")
    print(markdown[:1500])
