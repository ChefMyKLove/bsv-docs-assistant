"""Tests for the load -> clean -> chunk pipeline."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.chunker import CHUNK_SIZE, chunk_document, chunk_section
from src.cleaner import clean_document, clean_text
from src.ingest import DEFAULT_DOCS_DIR, build_chunks
from src.loader import load_documents


def _write(dirpath: Path, name: str, text: str) -> Path:
    path = dirpath / name
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------- loader


def test_loader_parses_header_and_sections(tmp_path):
    _write(
        tmp_path,
        "a.txt",
        "SOURCE: https://example.com/a\nRETRIEVED: 2026-10-16\nLICENSE: MIT\n\n"
        "===== PAGE: https://example.com/a/one.md =====\n# One\n\nfirst page\n\n"
        "===== FILE: docs/two.md =====\n# Two\n\nsecond page\n",
    )
    docs, errors = load_documents(tmp_path)
    assert not errors
    doc = docs[0]
    assert (doc.source_url, doc.retrieved, doc.license) == ("https://example.com/a", "2026-10-16", "MIT")
    assert [s.label for s in doc.sections] == ["https://example.com/a/one.md", "docs/two.md"]


def test_loader_isolates_bad_files(tmp_path):
    _write(tmp_path, "good.txt", "SOURCE: x\n\n# Title\n\nSome real content here.\n")
    _write(tmp_path, "empty.txt", "   \n")
    _write(tmp_path, "header_only.txt", "SOURCE: x\nRETRIEVED: y\n")
    (tmp_path / "corrupt.pdf").write_bytes(b"this is not a pdf")
    _write(tmp_path, "notes.md", "ignored: unsupported extension")
    docs, errors = load_documents(tmp_path)
    assert [d.filename for d in docs] == ["good.txt"]  # good file still loads
    assert {e.filename for e in errors} == {"empty.txt", "header_only.txt", "corrupt.pdf"}


def test_loader_missing_or_empty_folder(tmp_path):
    docs, errors = load_documents(tmp_path / "nope")
    assert not docs and "not found" in errors[0].reason
    docs, errors = load_documents(tmp_path)
    assert not docs and "no .txt or .pdf" in errors[0].reason


# ---------------------------------------------------------------- cleaner


def test_cleaner_strips_noise_but_keeps_code_verbatim():
    raw = (
        "---\ntitle: x\n---\n\n# Heading\n\n{% hint style=\"info\" %}\nUseful   text  here\n{% endhint %}\n\n"
        "![badge](http://img)\n\n---\n\nLinks: [API](#api), [Types](#types)\n\n"
        "Fish &amp; chips&#x20;ok\n\n\n\n```ts\nconst  a  =  1;   \n\n\nconst b = '<img src=\"x\" />';\n```\n"
    )
    out = clean_text(raw)
    assert "title: x" not in out and "{%" not in out and "![badge]" not in out
    assert "Links:" not in out and "\n---\n" not in out
    assert "Useful text here" in out and "Fish & chips ok" in out
    assert "const  a  =  1;" in out and '<img src="x" />' in out  # code untouched
    assert "\n\n\n\n" not in out


def _make_pdf(path: Path, pages: int = 6) -> None:
    reportlab = pytest.importorskip("reportlab")  # noqa: F841
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path))
    words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"]
    for n in range(1, pages + 1):
        w = words[n - 1]
        c.drawString(72, 800, "BSV Test Handbook")
        body = [
            f"Satoshi Vision {w} transactions are built from inputs and",
            f"outputs that are validated by script. Page {w} covers",
            f"its own unique fact number {n}. A trans-",
            f"action is final once mined in block {w}.",
        ]
        for i, line in enumerate(body):
            c.drawString(72, 700 - 16 * i, line)
        c.drawString(72, 40, f"Page {n}")
        c.showPage()
    c.save()


def test_pdf_pipeline_strips_headers_footers_and_reflows(tmp_path):
    _make_pdf(tmp_path / "handbook.pdf")
    docs, errors = load_documents(tmp_path)
    assert not errors and docs[0].is_pdf and len(docs[0].sections) == 6
    cleaned = clean_document(docs[0])
    text = "\n".join(s.text for s in cleaned.sections)
    assert "BSV Test Handbook" not in text
    assert not re.search(r"\bPage \d\b", text)
    assert "inputs and outputs that are validated" in text  # hard wraps rejoined
    assert "transactions are built" in text  # real body text survives edge stripping
    assert "A transaction is final" in text  # hyphenation rejoined
    chunks = chunk_document(cleaned)
    assert chunks[0].metadata["page"] == 1 and chunks[0].metadata["section"] == "p. 1"
    assert "handbook.pdf — p. 1" in chunks[0].metadata["citation"]


# ---------------------------------------------------------------- chunker


def test_chunks_respect_size_and_never_end_on_a_heading():
    section = "\n\n".join(
        f"## Topic {i}\n\n" + " ".join(f"Sentence {j} about topic {i}." for j in range(60))
        for i in range(6)
    ) + "\n\n## Empty trailing heading"
    pieces = chunk_section(section)
    assert pieces
    for text, heading in pieces:
        assert len(text) <= CHUNK_SIZE * 1.1
        assert not re.match(r"^#{1,6} ", text.strip().split("\n")[-1])
        assert heading.startswith("Topic")


def test_oversized_code_block_is_split_into_valid_fences():
    code = "```ts\n" + "\n".join(f"const value{i} = compute({i});" for i in range(200)) + "\n```"
    pieces = chunk_section("## API\n\nIntro text.\n\n" + code)
    for text, _ in pieces:
        assert text.count("```") % 2 == 0
        assert len(text) <= CHUNK_SIZE * 1.1


def test_overlap_is_carried_between_size_split_chunks():
    paragraphs = [f"Paragraph {i} " + "word " * 25 for i in range(40)]  # ~140 chars each
    pieces = chunk_section("\n\n".join(paragraphs))
    assert len(pieces) > 2
    shared = sum(
        pieces[i][0].split("\n\n")[-1] in pieces[i + 1][0] for i in range(len(pieces) - 1)
    )
    assert shared >= len(pieces) - 2


def test_chunk_ids_are_unique_stable_and_metadata_complete(tmp_path):
    _write(
        tmp_path,
        "My Doc.txt",
        "SOURCE: https://example.com\nRETRIEVED: 2026-10-16\nLICENSE: MIT\n\n"
        "===== PAGE: https://example.com/p1 =====\n## A\n\n" + ("alpha " * 400) + "\n\n"
        "===== PAGE: https://example.com/p2 =====\n## B\n\n" + ("beta " * 400),
    )
    first, _ = build_chunks(tmp_path)
    second, _ = build_chunks(tmp_path)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert len({c.chunk_id for c in first}) == len(first)
    assert first[0].chunk_id.startswith("my_doc_000_")
    required = {"source_file", "source_url", "section", "heading", "citation", "content_hash", "license"}
    assert all(required <= set(c.metadata) for c in first)
    assert all(isinstance(v, (str, int, float, bool)) for c in first for v in c.metadata.values())


# ---------------------------------------------------------------- real docs


@pytest.mark.skipif(not any(Path(DEFAULT_DOCS_DIR).glob("*.txt")), reason="no docs in docs/")
def test_real_docs_smoke():
    chunks, errors = build_chunks()
    assert not errors
    assert len(chunks) > 100
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert all(c.metadata["char_count"] <= CHUNK_SIZE * 1.1 for c in chunks)
    assert not any(c.text.count("```") % 2 for c in chunks)
    assert not any("{%" in c.text or "Links: [API]" in c.text for c in chunks)
