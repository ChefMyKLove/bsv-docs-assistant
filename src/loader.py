"""Load source documents (.txt, .pdf) from a folder.

Failures are isolated per file: a bad file is reported in the returned error
list instead of crashing the pipeline.

Text files may start with header lines (SOURCE / RETRIEVED / LICENSE / NOTE)
and may contain section markers of the form ``===== PAGE|FILE|SECTION: x =====``.
Each marker starts a new Section whose label (a URL or file path) is kept so
that answers can cite where the text came from.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".pdf"}
SECTION_MARKER_RE = re.compile(
    r"^===== (?:PAGE|FILE|SECTION): (.+?) =====[ \t]*$", re.MULTILINE
)
HEADER_RE = re.compile(r"^(SOURCE|RETRIEVED|LICENSE|NOTE):[ \t]*(.*)$")
MAX_HEADER_LINES = 8


@dataclass
class Section:
    label: str  # URL, file path inside the source, or "p. N" for PDFs
    text: str
    page: int | None = None


@dataclass
class Document:
    filename: str
    source_url: str
    retrieved: str
    license: str
    note: str
    is_pdf: bool
    sections: list[Section] = field(default_factory=list)


@dataclass
class LoadError:
    filename: str
    reason: str


def _split_sections(body: str, default_label: str) -> list[Section]:
    matches = list(SECTION_MARKER_RE.finditer(body))
    if not matches:
        return [Section(default_label, body)] if body.strip() else []
    sections: list[Section] = []
    preamble = body[: matches[0].start()]
    if preamble.strip():
        sections.append(Section(default_label, preamble))
    for idx, m in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        text = body[m.end() : end]
        if text.strip():
            sections.append(Section(m.group(1).strip(), text))
    return sections


def _load_txt(path: Path) -> Document:
    raw = path.read_bytes().decode("utf-8", errors="replace")
    if not raw.strip():
        raise ValueError("file is empty")
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿").split("\n")
    meta: dict[str, str] = {}
    i = 0
    while i < len(lines) and i < MAX_HEADER_LINES:
        m = HEADER_RE.match(lines[i])
        if not m:
            break
        meta[m.group(1)] = m.group(2).strip()
        i += 1
    sections = _split_sections("\n".join(lines[i:]), default_label=path.name)
    if not sections:
        raise ValueError("file has a header but no content")
    return Document(
        filename=path.name,
        source_url=meta.get("SOURCE", ""),
        retrieved=meta.get("RETRIEVED", ""),
        license=meta.get("LICENSE", ""),
        note=meta.get("NOTE", ""),
        is_pdf=False,
        sections=sections,
    )


def _load_pdf(path: Path) -> Document:
    from pypdf import PdfReader  # imported lazily so TXT-only use needs no pypdf

    reader = PdfReader(str(path))
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("PDF is password-protected")
    sections: list[Section] = []
    for n, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # one bad page should not sink the document
            log.warning("%s: page %d failed to extract (%s)", path.name, n, exc)
            continue
        if text.strip():
            sections.append(Section(f"p. {n}", text, page=n))
    if not sections:
        raise ValueError("no extractable text (scanned PDF? it would need OCR)")
    return Document(
        filename=path.name,
        source_url="",
        retrieved="",
        license="",
        note="",
        is_pdf=True,
        sections=sections,
    )


def load_file(path: Path) -> Document:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return _load_txt(path)
    if suffix == ".pdf":
        return _load_pdf(path)
    raise ValueError(f"unsupported file type: {suffix}")


def load_documents(docs_dir: str | Path) -> tuple[list[Document], list[LoadError]]:
    """Load every supported file in docs_dir. Never raises for bad input."""
    docs: list[Document] = []
    errors: list[LoadError] = []
    root = Path(docs_dir)
    if not root.is_dir():
        return docs, [LoadError(str(root), "documents folder not found")]
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        try:
            docs.append(load_file(path))
        except Exception as exc:
            log.warning("could not load %s: %s", path.name, exc)
            errors.append(LoadError(path.name, f"{type(exc).__name__}: {exc}"))
    if not docs and not errors:
        errors.append(LoadError(str(root), "no .txt or .pdf documents found"))
    return docs, errors
