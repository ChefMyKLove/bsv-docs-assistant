"""Text cleaning: strip formatting noise before chunking and embedding.

Markdown/TXT sources are cleaned conservatively: code fences are left
verbatim (whitespace in code can matter). PDFs additionally get repeated
headers/footers and page numbers removed, hyphenated line breaks rejoined,
and hard-wrapped lines reflowed into sentences.
"""
from __future__ import annotations

import html
import re
from collections import Counter
from dataclasses import replace

from .loader import Document, Section

FENCE_RE = re.compile(r"^```[^\n]*\n.*?^```[ \t]*$", re.MULTILINE | re.DOTALL)
FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\n(?=[\w-]+:)(?:.*\n)*?---[ \t]*(?:\n|\Z)"
)
GITBOOK_TAG_RE = re.compile(r"\{%.*?%\}", re.DOTALL)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
HTML_TAG_RE = re.compile(
    r"</?(?:img|br|hr|div|span|center|details|summary|picture|source|figure|figcaption|p|a)\b[^>]*>",
    re.IGNORECASE,
)
MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
EMPTY_LINK_RE = re.compile(r"\[\s*\]\([^)]*\)")
HR_RE = re.compile(r"^[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*$", re.MULTILINE)
# "Links: [API](#api), [Interfaces](#interfaces), ..." in-page navigation repeated on every
# generated API reference section: pure noise for retrieval.
NAV_LINKS_RE = re.compile(
    r"^Links:[ \t]*(?:\[[^\]]+\]\(#[^)]*\)(?:,[ \t]*)?)+[ \t]*$", re.MULTILINE
)
PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:page\s+)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?\s*$", re.IGNORECASE
)
BULLET_RE = re.compile(r"^(?:[-*•]|\d+[.)])\s")
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"))


def _clean_prose(segment: str) -> str:
    segment = html.unescape(segment)  # e.g. "&#x20;" and "&amp;" left over from GitBook exports
    segment = HTML_COMMENT_RE.sub("", segment)
    segment = GITBOOK_TAG_RE.sub("", segment)
    segment = NAV_LINKS_RE.sub("", segment)
    segment = HR_RE.sub("", segment)
    segment = MD_IMAGE_RE.sub("", segment)
    segment = EMPTY_LINK_RE.sub("", segment)
    segment = HTML_TAG_RE.sub("", segment)
    lines = []
    for line in segment.split("\n"):
        line = line.rstrip()
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        lines.append(" " * indent + re.sub(r" {2,}", " ", stripped))
    return "\n".join(lines)


def clean_text(text: str) -> str:
    """Clean one block of markdown/plain text; code fences are kept verbatim."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = text.translate(_INVISIBLE)
    text = FRONTMATTER_RE.sub("", text, count=1)
    parts: list[str] = []
    pos = 0
    for m in FENCE_RE.finditer(text):
        parts.append(_clean_prose(text[pos : m.start()]))
        parts.append(m.group(0).rstrip())
        pos = m.end()
    parts.append(_clean_prose(text[pos:]))
    text = "".join(parts)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _norm_edge(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def _strip_repeated_edges(
    pages: list[str], edge_lines: int = 2, min_ratio: float = 0.5, min_pages: int = 3
) -> list[str]:
    """Drop page numbers and headers/footers repeated across PDF pages."""
    split = [p.split("\n") for p in pages]
    repeated: set[str] = set()
    if len(pages) >= min_pages:
        counts: Counter[str] = Counter()
        for lines in split:
            nonempty = [l for l in lines if l.strip()]
            edges = {_norm_edge(l) for l in nonempty[:edge_lines] + nonempty[-edge_lines:]}
            counts.update(edges)
        threshold = max(min_pages, int(len(pages) * min_ratio))
        repeated = {k for k, c in counts.items() if k and c >= threshold and len(k) <= 100}
    out = []
    for lines in split:
        idx = [i for i, l in enumerate(lines) if l.strip()]
        edge_idx = set(idx[:edge_lines] + idx[-edge_lines:])
        kept = [
            l
            for i, l in enumerate(lines)
            if not (i in edge_idx and (PAGE_NUMBER_RE.match(l) or _norm_edge(l) in repeated))
        ]
        out.append("\n".join(kept))
    return out


def _reflow_pdf_page(text: str) -> str:
    """Rejoin hyphenated breaks and merge hard-wrapped lines into sentences."""
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    paragraphs = []
    for para in re.split(r"\n\s*\n", text):
        merged: list[str] = []
        for line in (l.strip() for l in para.split("\n")):
            if not line:
                continue
            if (
                merged
                and not BULLET_RE.match(line)
                and (not merged[-1].endswith((".", "!", "?", ":", ";")) or line[:1].islower())
            ):
                merged[-1] += " " + line
            else:
                merged.append(line)
        if merged:
            paragraphs.append("\n".join(merged))
    return "\n\n".join(paragraphs)


def clean_document(doc: Document) -> Document:
    """Return a cleaned copy of doc; sections that end up empty are dropped."""
    texts = [s.text for s in doc.sections]
    if doc.is_pdf:
        texts = [_reflow_pdf_page(t) for t in _strip_repeated_edges(texts)]
    sections = []
    for section, text in zip(doc.sections, texts):
        cleaned = clean_text(text)
        if cleaned:
            sections.append(Section(section.label, cleaned, section.page))
    return replace(doc, sections=sections)
