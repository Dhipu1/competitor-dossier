"""Splits a page's text into retrievable chunks.

Why not embed the whole page as one unit? An embedding compresses text into
a single vector — a whole page's worth of topics averages into something
that matches nothing precisely. Chunks let a search land on the specific
section that answers a question.

Strategy: split on markdown headings first, since those are the author's own
statement of where topics begin and end. Sections longer than max_chars get
split again at paragraph boundaries, never mid-sentence.
"""

import re
from dataclasses import dataclass
from typing import List, Optional

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


@dataclass
class Chunk:
    ordinal: int             # position within the page, 0-based
    heading: Optional[str]   # section this chunk came from
    text: str

    def embedding_text(self) -> str:
        """What we actually embed: heading + body.

        The heading is included so a chunk carries its own topic context —
        a paragraph saying "it launched in March" is far more findable when
        the embedded text also says which game the section was about.
        """
        return f"{self.heading}\n\n{self.text}" if self.heading else self.text


def _split_long(body: str, max_chars: int) -> List[str]:
    """Breaks an over-long section at paragraph boundaries."""
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    pieces, current = [], ""

    for para in paragraphs:
        if current and len(current) + len(para) + 2 > max_chars:
            pieces.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para

    if current:
        pieces.append(current)
    return pieces


def chunk_page(text: Optional[str], *, max_chars: int = 1200, min_chars: int = 50) -> List[Chunk]:
    """Splits page text into chunks, each tagged with the heading it sits under."""
    if not text or not text.strip():
        return []

    # find where each heading starts so we can slice the text into sections
    matches = list(_HEADING.finditer(text))
    sections = []

    if not matches or matches[0].start() > 0:
        # text before the first heading (or a page with no headings at all)
        end = matches[0].start() if matches else len(text)
        sections.append((None, text[:end]))

    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((heading, text[start:end]))

    chunks = []
    for heading, body in sections:
        body = body.strip()
        if not body:
            continue
        for piece in _split_long(body, max_chars):
            if len(piece) < min_chars:
                continue
            chunks.append(Chunk(ordinal=len(chunks), heading=heading, text=piece))

    return chunks
