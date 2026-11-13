"""Split cleaned documents into overlapping, metadata-rich chunks.

Strategy (see README for the rationale):
  * ~1200 characters per chunk (about 300 tokens): small enough that one chunk
    is about one idea, large enough to keep a code sample with its explanation.
  * ~200 characters of overlap, carried as whole trailing blocks so a sentence
    or code fence is never cut in half by the overlap.
  * Split at markdown headings (levels 1-3) first, then paragraphs; code fences
    are atomic and only split by line when one alone exceeds the size.
  * Headings are never left orphaned at the end of a chunk.
  * Every chunk carries source, section, heading and a stable ID, so answers
    can cite their evidence and re-ingesting is idempotent.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .loader import Document

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
MIN_CHUNK = 300  # a heading only forces a split once the current chunk is this big
TINY_CHUNK = 150  # fragments smaller than this are folded into the previous chunk
HEADING_SPLIT_LEVEL = 3

FENCE_RE = re.compile(r"^```[^\n]*\n.*?^```[ \t]*$", re.MULTILINE | re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")


@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: dict

    @property
    def embedding_text(self) -> str:
        """Text sent to the embedding model: chunk text plus where it lives."""
        heading = self.metadata.get("heading", "")
        prefix = f"{self.metadata['source_file']} > {heading}" if heading else self.metadata["source_file"]
        return f"[{prefix}]\n{self.text}"


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()


def _paragraph_blocks(text: str) -> list[tuple[str, str, int]]:
    """Split prose into text and heading blocks; headings are detected on any line."""
    blocks: list[tuple[str, str, int]] = []
    for para in re.split(r"\n\s*\n", text):
        buf: list[str] = []
        for line in para.strip("\n").split("\n"):
            m = HEADING_RE.match(line.strip())
            if m:
                if "".join(buf).strip():
                    blocks.append(("text", "\n".join(buf).strip(), 0))
                buf = []
                blocks.append(("heading", line.strip(), len(m.group(1))))
            else:
                buf.append(line)
        if "".join(buf).strip():
            blocks.append(("text", "\n".join(buf).strip(), 0))
    return blocks


def _split_blocks(text: str) -> list[tuple[str, str, int]]:
    blocks: list[tuple[str, str, int]] = []
    pos = 0
    for m in FENCE_RE.finditer(text):
        blocks += _paragraph_blocks(text[pos : m.start()])
        blocks.append(("code", m.group(0).strip("\n"), 0))
        pos = m.end()
    blocks += _paragraph_blocks(text[pos:])
    return blocks


def _split_code(block: str, size: int) -> list[str]:
    """Split an oversized code fence by lines, re-wrapping each piece in fences."""
    lines = block.split("\n")
    opener = lines[0]
    closer = "```"
    inner = lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:]
    budget = size - len(opener) - len(closer) - 2
    units: list[str] = []
    for line in inner:
        if len(line) > budget:
            units += [line[i : i + budget] for i in range(0, len(line), budget)]
        else:
            units.append(line)
    pieces: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for unit in units:
        if cur and cur_len + len(unit) + 1 > budget:
            pieces.append("\n".join([opener, *cur, closer]))
            cur, cur_len = [], 0
        cur.append(unit)
        cur_len += len(unit) + 1
    if cur:
        pieces.append("\n".join([opener, *cur, closer]))
    return pieces


def _split_prose(text: str, size: int, overlap: int) -> list[str]:
    """Split oversized prose at newline/sentence/word boundaries with overlap."""
    pieces: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            window = text[start:end]
            cut = max(window.rfind("\n"), window.rfind(". "), window.rfind(" "))
            if cut > size * 0.5:
                end = start + cut + 1
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= n:
            break
        nxt = max(end - overlap, start + 1)
        m = re.search(r"\s", text[nxt:end])
        if m:
            nxt += m.end()
        start = max(nxt, start + 1)
    return pieces


def _fit(kind: str, block: str, size: int, overlap: int) -> list[str]:
    if len(block) <= size:
        return [block]
    if kind == "code":
        return _split_code(block, size)
    return _split_prose(block, size, overlap)


def _overlap_tail(items: list[tuple[str, str]], overlap: int) -> list[tuple[str, str]]:
    tail: list[tuple[str, str]] = []
    total = 0
    for kind, text in reversed(items):
        if kind == "heading" or total + len(text) + 2 > overlap:
            break
        tail.insert(0, (kind, text))
        total += len(text) + 2
    return tail


def _pop_trailing_headings(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Remove and return headings at the end of items (a heading must not end a chunk)."""
    popped: list[tuple[str, str]] = []
    while items and items[-1][0] == "heading":
        popped.insert(0, items.pop())
    return popped


def _heading_text(block: str) -> str:
    m = HEADING_RE.match(block)
    return m.group(2).strip() if m else block.strip()


def chunk_section(
    text: str,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    min_chunk: int = MIN_CHUNK,
    tiny: int = TINY_CHUNK,
) -> list[tuple[str, str]]:
    """Chunk one cleaned section. Returns (chunk_text, heading) pairs."""
    out: list[list] = []  # [text, heading, started_with_overlap]
    cur: list[tuple[str, str]] = []
    cur_len = 0
    n_carry = 0  # leading items of cur that are overlap copied from the previous chunk
    heading = ""
    start_heading = ""

    def length(items: list[tuple[str, str]]) -> int:
        return sum(len(t) + 2 for _, t in items)

    def emit(items: list[tuple[str, str]], h: str, carried: bool) -> None:
        body = "\n\n".join(t for _, t in items).strip()
        if body:
            out.append([body, h, carried])

    for kind, block, level in _split_blocks(text):
        if kind == "heading":
            heading = _heading_text(block)
            if level <= HEADING_SPLIT_LEVEL and cur and cur_len >= min_chunk:
                orphans = _pop_trailing_headings(cur)
                emit(cur, start_heading, n_carry > 0)
                cur, n_carry = orphans, 0
                cur_len = length(cur)
                start_heading = _heading_text(orphans[0][1]) if orphans else heading
            if not cur:
                start_heading = heading
            cur.append((kind, block))
            cur_len += len(block) + 2
            continue

        for piece in _fit(kind, block, size, overlap):
            if cur and cur_len + len(piece) + 2 > size:
                orphans = _pop_trailing_headings(cur)
                emit(cur, start_heading, n_carry > 0)
                carry = [] if orphans else _overlap_tail(cur, overlap)
                cur = carry + orphans
                n_carry = len(carry)
                cur_len = length(cur)
                if carry and cur_len + len(piece) + 2 > size:
                    cur, cur_len, n_carry = [], 0, 0  # overlap would overflow: drop it
                start_heading = _heading_text(orphans[0][1]) if orphans else heading
            if not cur:
                start_heading = heading
            cur.append((kind, piece))
            cur_len += len(piece) + 2

    _pop_trailing_headings(cur)  # a section must not end on a bare heading
    if len(cur) > n_carry:  # skip a chunk that would only repeat overlap
        emit(cur, start_heading, n_carry > 0)

    # Fold tiny fragments (no overlap text) into the previous chunk when they fit.
    merged: list[list] = []
    for body, h, carried in out:
        if merged and not carried and len(body) < tiny and len(merged[-1][0]) + len(body) + 2 <= size:
            merged[-1][0] += "\n\n" + body
        else:
            merged.append([body, h, carried])
    return [(body, h) for body, h, _ in merged]


def chunk_document(
    doc: Document, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[Chunk]:
    stem = _slug(Path(doc.filename).stem)
    chunks: list[Chunk] = []
    for sec_idx, section in enumerate(doc.sections):
        for i, (text, heading) in enumerate(chunk_section(section.text, size, overlap)):
            citation = f"{doc.filename} — {section.label}"
            if heading:
                citation += f" › {heading}"
            meta: dict = {
                "source_file": doc.filename,
                "source_url": doc.source_url,
                "section": section.label,
                "heading": heading,
                "section_index": sec_idx,
                "chunk_index": i,
                "license": doc.license,
                "retrieved": doc.retrieved,
                "citation": citation,
                "char_count": len(text),
                "content_hash": hashlib.sha1(text.encode("utf-8")).hexdigest()[:16],
            }
            if section.page is not None:
                meta["page"] = section.page
            chunks.append(Chunk(f"{stem}_{sec_idx:03d}_{i:03d}", text, meta))
    return chunks
