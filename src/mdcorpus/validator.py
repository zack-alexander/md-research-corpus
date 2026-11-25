"""Validate corpus Markdown frontmatter against controlled vocabularies."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from mdcorpus.frontmatter import parse_document

REQUIRED_FIELDS = ("id", "title", "doc_type", "status", "date")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(slots=True)
class ValidationIssue:
    """A schema or vocabulary validation failure on one corpus document."""

    path: str
    field: str
    message: str


def load_vocab(vocab_path: Path) -> dict[str, set[str]]:
    raw = json.loads(vocab_path.read_text(encoding="utf-8"))
    return {key: set(values) for key, values in raw.items() if isinstance(values, list)}


def validate_corpus(
    root: Path,
    *,
    corpus_subdir: str = "corpus",
    vocab_path: Path | None = None,
) -> list[ValidationIssue]:
    """Validate all Markdown documents under ``root / corpus_subdir``."""
    resolved_vocab_path = vocab_path or (root / "metadata" / "vocab.json")
    vocab = load_vocab(resolved_vocab_path) if resolved_vocab_path.exists() else {}

    corpus_dir = root / corpus_subdir
    if not corpus_dir.exists():
        return []

    issues: list[ValidationIssue] = []
    seen_ids: dict[str, str] = {}

    for path in sorted(corpus_dir.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        doc = parse_document(path)
        meta = doc.metadata

        for req in REQUIRED_FIELDS:
            val = meta.get(req)
            if not val or (isinstance(val, list) and not val):
                issues.append(ValidationIssue(rel, req, f"missing required field '{req}'"))

        doc_id = meta.get("id")
        if isinstance(doc_id, str) and doc_id:
            if doc_id in seen_ids:
                issues.append(
                    ValidationIssue(
                        rel,
                        "id",
                        f"duplicate id '{doc_id}' (already used by {seen_ids[doc_id]})",
                    )
                )
            else:
                seen_ids[doc_id] = rel

        date_val = meta.get("date")
        if isinstance(date_val, str) and date_val and not DATE_RE.match(date_val):
            issues.append(ValidationIssue(rel, "date", f"invalid ISO date '{date_val}'"))

        doc_type = meta.get("doc_type")
        if (
            isinstance(doc_type, str)
            and doc_type
            and "doc_types" in vocab
            and doc_type not in vocab["doc_types"]
        ):
            issues.append(
                ValidationIssue(
                    rel,
                    "doc_type",
                    f"unknown doc_type '{doc_type}' (allowed: {sorted(vocab['doc_types'])})",
                )
            )

        status = meta.get("status")
        if (
            isinstance(status, str)
            and status
            and "statuses" in vocab
            and status not in vocab["statuses"]
        ):
            issues.append(
                ValidationIssue(
                    rel,
                    "status",
                    f"unknown status '{status}' (allowed: {sorted(vocab['statuses'])})",
                )
            )

        themes = meta.get("themes")
        if isinstance(themes, list) and "themes" in vocab:
            for theme in themes:
                if theme not in vocab["themes"]:
                    issues.append(
                        ValidationIssue(
                            rel,
                            "themes",
                            f"unknown theme '{theme}' (allowed: {sorted(vocab['themes'])})",
                        )
                    )

    return issues
