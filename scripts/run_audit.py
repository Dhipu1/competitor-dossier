"""Runs a complete audit end to end, in the right order.

Delivering an audit by hand means running five scripts in sequence. Doing
that from memory is how a client gets a report built on stale data — the
same class of mistake as indexing two crawls at once, which produced a
report describing two different snapshots as if they were one.

The order is not arbitrary:
  crawl    - fetch pages (the only slow, network-heavy step)
  enrich   - on-page signals + sitemaps, needs pages to exist
  index    - chunk + embed, needs pages to exist
  report   - needs the index and the enrichment
  verify   - needs the report

Verification runs before the deliverable is built, and a failure stops the
run: a report citing pages that were never crawled must not reach a client.

Run with:  .venv\\Scripts\\python scripts\\run_audit.py clients\\pilot.json
Re-run the analysis without re-crawling with --no-crawl.
"""

import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def run_step(label: str, args: list) -> None:
    """Runs one pipeline step, stopping the whole audit if it fails."""
    print(f"\n{'=' * 62}\n{label}\n{'=' * 62}")
    result = subprocess.run([sys.executable, *args], cwd=ROOT)
    if result.returncode != 0:
        sys.exit(f"\nStep failed: {label} (exit {result.returncode}). Audit stopped.")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    config = args[0] if args else "clients/pilot.json"

    if not (ROOT / config).exists():
        sys.exit(f"Client config not found: {config}")

    started = time.time()

    if "--no-crawl" not in sys.argv:
        run_step("1/5  Crawling client + competitor sites", ["scripts/crawl_pilot.py", config])
    else:
        print("Skipping crawl (--no-crawl): using the most recent crawl on record.")

    run_step("2/5  Extracting on-page signals and sitemaps", ["scripts/enrich.py"])
    run_step("3/5  Chunking and embedding", ["scripts/build_index.py"])
    run_step("4/5  Measuring gaps and writing the report", ["scripts/generate_report.py"])

    report = ROOT / "reports" / f"audit-{date.today().isoformat()}.md"
    if not report.exists():
        sys.exit(f"Expected report not found: {report}")

    run_step("5/5  Verifying every citation", ["scripts/verify_citations.py", str(report)])
    run_step("Building the client deliverable", ["scripts/build_deliverable.py", str(report), config])

    print(f"\n{'=' * 62}")
    print(f"Audit complete in {time.time() - started:.0f}s")
    print(f"  report:      {report}")
    print(f"  deliverable: {report.with_suffix('.html')}")
