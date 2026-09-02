"""Produces a sanitised sample audit for use as sales material.

Why this exists: the pilot audit analyses real companies who never asked to
be analysed. The observations are all factual and drawn from public pages, so
a published teardown would be defensible — but a *sample deliverable* implying
those companies were clients is a bad look and an avoidable risk. Standard
practice is to show the structure and depth of the work with the subjects
anonymised.

Why it is not fully automatic: swapping company names is the easy half. A
games report is full of product names — a title left in the text identifies
the studio just as surely as its name would. There is no reliable way to spot
every one of those automatically, so extra terms are declared explicitly and
the result is verified before it is trusted.

This tool will not tell you the output is safe. It tells you what it changed
and what it still found, and a human decides.

Run with:
  .venv\\Scripts\\python scripts\\anonymize_sample.py reports\\audit-2026-09-02.md clients\\pilot.json
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Stand-in identities. The .example TLD is reserved for documentation
# (RFC 2606), so these can never collide with a real site.
COVER_NAMES = [
    ("Northwind Games", "northwindgames.example"),
    ("Halcyon Interactive", "halcyoninteractive.example"),
    ("Two Rivers Studio", "tworiversstudio.example"),
    ("Fourth Wall Games", "fourthwallgames.example"),
]

# Product names and other giveaways that no name-swap would catch. Extend this
# per engagement — an unlisted product name defeats the whole exercise.
EXTRA_TERMS = {
    "Silksong": "Ridgewalker",
    "Hollow Knight": "Lantern Hollow",
    "Hades II": "Ember Court II",
    "Hades": "Ember Court",
    "Pyre": "Tidewalk",
    "Transistor": "Filament",
    "Bastion": "Redoubt",
    "Don't Starve": "Long Winter",
    "Dont Starve": "Long Winter",
    "Rotwood": "Thornwood",
    "Fretless": "Stringless",
    "Away Team": "Far Crew",
    "Darren Korb": "the studio composer",
    "Austin Wintory": "the guest conductor",
    "Royal Festival Hall": "a London concert hall",
}


# Words that appear in half the company names in existence. Replacing these
# would mangle ordinary sentences and identifies nobody.
_GENERIC_NAME_WORDS = {
    "games", "game", "entertainment", "studio", "studios", "interactive",
    "digital", "media", "group", "team", "the", "inc", "ltd", "llc", "co",
    "company", "software", "labs",
}


def _real_domains(conn, config: dict) -> set:
    """Every domain the report might contain, including redirect destinations.

    Taking domains from the config alone is not enough: a site can redirect
    somewhere else entirely, and it is the destination that ends up in the
    report. One of the pilot sites starts at kleientertainment.com and lands
    on klei.com — anonymising only the configured domain left the real one
    sitting in the output.
    """
    domains = set()

    for site in [config["client"]] + config["competitors"]:
        host = re.sub(r"^https?://", "", site["start_url"]).strip("/").split("/")[0]
        domains.add(host.removeprefix("www."))

    if conn is not None:
        for row in conn.execute("SELECT DISTINCT final_url FROM pages"):
            host = re.sub(r"^https?://", "", row["final_url"]).split("/")[0]
            domains.add(host.removeprefix("www."))

    return domains


def _slug(text: str) -> str:
    """'Don't Starve' -> 'dont-starve', the form that appears inside URLs."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower().replace("'", "")).strip("-")


def _short_form(cover_name: str) -> str:
    """'Two Rivers Studio' -> 'Two Rivers'. Bare 'Two' reads like a typo."""
    words = [w for w in cover_name.split() if w.lower() not in _GENERIC_NAME_WORDS]
    return " ".join(words) or cover_name.split()[0]


def build_mapping(config: dict, conn) -> dict:
    """Real name/domain -> stand-in, longest first so substrings can't win."""
    sites = [config["client"]] + config["competitors"]
    mapping = {}
    covers = dict(zip((s["name"] for s in sites), COVER_NAMES))

    for real_name, (cover_name, _) in covers.items():
        mapping[real_name] = cover_name

        # "Klei Entertainment" also appears as plain "Klei". Map the
        # distinctive words on their own, or the short form survives.
        for word in real_name.split():
            if word.lower() not in _GENERIC_NAME_WORDS and len(word) > 3:
                mapping.setdefault(word, _short_form(cover_name))

    # domains, matched to whichever site's name shares the most letters with
    # them, so klei.com is covered even though the config said something else
    for domain in _real_domains(conn, config):
        stem = re.split(r"[.\-]", domain)[0].lower()
        best = max(
            covers.items(),
            key=lambda kv: len(set(stem) & set(kv[0].lower().replace(" ", ""))) if stem else 0,
        )
        cover_domain = best[1][1]
        mapping[f"www.{domain}"] = f"www.{cover_domain}"
        mapping[domain] = cover_domain

    mapping.update(EXTRA_TERMS)

    # Product names also live inside URL paths as slugs: a page about
    # "Don't Starve" sits at /games/dont-starve-elsewhere, which no
    # replacement of the prose form will ever touch.
    for real, cover in list(mapping.items()):
        real_slug, cover_slug = _slug(real), _slug(cover)
        if real_slug and real_slug != real.lower() and real_slug not in mapping:
            mapping[real_slug] = cover_slug

    return dict(sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True))


def anonymize(text: str, mapping: dict) -> tuple:
    replaced = {}
    for real, cover in mapping.items():
        pattern = re.compile(re.escape(real), re.IGNORECASE)
        text, count = pattern.subn(cover, text)
        if count:
            replaced[real] = count
    return text, replaced


def find_leftovers(text: str, mapping: dict, config: dict, conn) -> list:
    """Independent check for identifying material still in the output.

    Deliberately not just "did my replacements apply". Checking only the terms
    we chose to replace verifies the tool against its own assumptions, which
    is how the first version of this reported a clean pass while a real
    competitor's live domain was still sitting in the text. This re-derives
    what to look for from the crawl and the config instead.
    """
    suspects = set(mapping)

    for domain in _real_domains(conn, config):
        suspects.add(domain)
        suspects.add(re.split(r"[.\-]", domain)[0])  # the bare brand, e.g. "klei"

    for site in [config["client"]] + config["competitors"]:
        for word in site["name"].split():
            if word.lower() not in _GENERIC_NAME_WORDS and len(word) > 3:
                suspects.add(word)

    # and the URL-slug form of everything above — the miss that got through
    # the first time was a product name inside a link path, not in prose
    for term in list(suspects):
        slug = _slug(term)
        if slug and slug != term.lower():
            suspects.add(slug)

    return sorted(s for s in suspects if re.search(re.escape(s), text, re.IGNORECASE))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        reports = sorted(ROOT.joinpath("reports").glob("audit-*.md"))
        if not reports:
            sys.exit("No audit reports found.")
        report = reports[-1]
    else:
        report = Path(sys.argv[1])

    config_path = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "clients" / "pilot.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    from storage.db import get_connection

    conn = get_connection()
    mapping = build_mapping(config, conn)
    original = report.read_text(encoding="utf-8")
    sanitised, replaced = anonymize(original, mapping)

    header = (
        "> **Sample report.** Subjects anonymised. This shows the structure and\n"
        "> depth of a Competitor Gap Audit using real pipeline output; company\n"
        "> and product names have been replaced with stand-ins.\n\n"
    )

    out = ROOT / "docs" / "sample-audit.md"
    out.write_text(header + sanitised, encoding="utf-8")

    print(f"Wrote {out}\n")
    print("Replacements made:")
    for real, count in sorted(replaced.items(), key=lambda kv: -kv[1]):
        print(f"  {count:>3}x  {real!r} -> {mapping[real]!r}")

    leftovers = find_leftovers(sanitised, mapping, config, conn)
    print()
    if leftovers:
        print("STILL PRESENT after replacement — fix before using this:")
        for term in leftovers:
            print(f"  - {term}")
        sys.exit(1)

    print("Nothing identifying found by an independent re-scan of the output.")
    print(
        "\nThat is not the same as 'safe to publish'. Read it yourself: an\n"
        "identifying detail that was never added to EXTRA_TERMS will not have\n"
        "been caught, and this tool cannot know what it was not told."
    )
