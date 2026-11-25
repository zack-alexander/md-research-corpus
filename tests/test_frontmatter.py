from __future__ import annotations

from pathlib import Path

from mdcorpus.frontmatter import dump_frontmatter, parse_document, parse_frontmatter


def test_parse_and_dump_roundtrip(tmp_path: Path) -> None:
    meta = {
        "id": "test-note",
        "title": "Test Note",
        "doc_type": "memo",
        "status": "active",
        "date": "2026-11-10",
        "tickers": ["ACME", "DEMO"],
        "themes": ["capital-allocation"],
    }
    body = "# Heading\n\nBody paragraph about ROIC.\n"
    raw = dump_frontmatter(meta, body)

    target = tmp_path / "test-note.md"
    target.write_text(raw, encoding="utf-8")

    doc = parse_document(target)
    assert doc.metadata["id"] == "test-note"
    assert doc.metadata["tickers"] == ["ACME", "DEMO"]
    assert doc.metadata["themes"] == ["capital-allocation"]
    assert "# Heading" in doc.body
    assert doc.body_start_line == 10


def test_parse_multiline_yaml_list() -> None:
    raw = """---
id: multi
themes:
  - energy
  - royalties
---
Line one.
"""
    meta, body, start = parse_frontmatter(raw)
    assert meta["themes"] == ["energy", "royalties"]
    assert body.strip() == "Line one."
    assert start == 7


def test_no_frontmatter_returns_full_body() -> None:
    raw = "# Plain doc\n\nNo frontmatter here.\n"
    meta, body, start = parse_frontmatter(raw)
    assert meta == {}
    assert body == raw
    assert start == 1
