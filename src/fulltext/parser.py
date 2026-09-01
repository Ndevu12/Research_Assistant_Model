# -*- coding: utf-8 -*-
"""PDF text extraction with lightweight section detection.

Uses PyMuPDF for dependable local-first extraction. Section headings are
detected heuristically (numbered headings and common scholarly section
names) and recorded per text block so chunking can stay section-aware.
The references section is truncated — bibliography lines add noise to
retrieval without adding evidence.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import FullTextDocument

_HEADING_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*\.?\s+)?"
    r"(abstract|introduction|background|related work|methods?|methodology|"
    r"materials and methods|approach|experiments?|results?|evaluation|"
    r"discussion|limitations|conclusions?|future work|acknowledg\w+|references)"
    r"\s*$",
    re.IGNORECASE,
)

_STOP_SECTIONS = {"references", "acknowledgment", "acknowledgments", "acknowledgements"}


def _detect_heading(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
        return None
    match = _HEADING_RE.match(stripped)
    if match:
        return match.group(1).lower()
    return None


def extract_document(paper_id: str, path: Path) -> FullTextDocument:
    """Extract text from a PDF, annotated with per-page section markers.

    The returned document's ``text`` holds the body up to the references
    section; ``metadata['sections']`` maps section names to their first page.
    """
    import pymupdf

    sections: dict[str, int] = {}
    pages: list[str] = []
    current_section = "body"
    stopped = False

    with pymupdf.open(path) as pdf:
        page_count = pdf.page_count
        for page_number, page in enumerate(pdf, start=1):
            if stopped:
                break
            lines = page.get_text("text").splitlines()
            kept: list[str] = []
            for line in lines:
                heading = _detect_heading(line)
                if heading:
                    if heading in _STOP_SECTIONS:
                        stopped = True
                        break
                    current_section = heading
                    sections.setdefault(heading, page_number)
                    kept.append(f"\n## {heading.title()}\n")
                    continue
                kept.append(line)
            if kept:
                pages.append("\n".join(kept))

    text = "\n".join(pages)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return FullTextDocument(
        paper_id=paper_id,
        local_path=path,
        text=text or None,
        page_count=page_count,
        metadata={"sections": sections, "current_section": current_section},
    )
