"""Wraps the site source into a standalone HTML file you can open from disk.

site/index.html is written for the Artifact host, which supplies the
document skeleton itself — so the source deliberately has no <!doctype>,
<html>, <head>, or <body> tags of its own.

Browsers will happily infer those when you open the file directly, but not
the character encoding. Without a declared charset a local file:// load
guesses, and every em dash and curly quote on the page can come out as
mojibake. So a local copy needs a real head with a real charset.

One source of truth, two outputs: the artifact publishes from index.html,
and this writes the standalone copy for opening locally.

Run with:  .venv\\Scripts\\python scripts\\build_local_site.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "site" / "index.html"
OUTPUT = ROOT / "site" / "standalone.html"

SKELETON = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{ color-scheme: light; }}
  body {{ margin: 0; }}
  img {{ max-width: 100%; }}
  [hidden] {{ display: none !important; }}
</style>
</head>
<body>
{content}
</body>
</html>
"""

if __name__ == "__main__":
    if not SOURCE.exists():
        sys.exit(f"Site source not found: {SOURCE}")

    OUTPUT.write_text(SKELETON.format(content=SOURCE.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print("Open it directly, or serve the folder with:")
    print("  .venv\\Scripts\\python -m http.server 8000 --directory site")
