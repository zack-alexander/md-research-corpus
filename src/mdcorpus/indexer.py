"""Build and audit CSV inventories for a Markdown research corpus."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from mdcorpus.frontmatter import parse_document

FIELDNAMES = [
    "id",
    "title",
    "doc_type",
    "status",
    "tickers",
    "themes",
    "date",
    "source_format",
    "path",
    "bytes",
    "lines",
]


@dataclass(slots=True)
class IndexEntry:
    """One indexed document row."""

    id: str
    title: str
    doc_type: str
    status: str
    tickers: str
    themes: str
    date: str
    source_format: str
    path: str
    bytes: int
    lines: int

    def as_dict(self) -> dict[str, str | int]:
        return {
            "id": self.id,
            "title": self.title,
            "doc_type": self.doc_type,
            "status": self.status,
            "tickers": self.tickers,
            "themes": self.themes,
            "date": self.date,
            "source_format": self.source_format,
            "path": self.path,
            "bytes": self.bytes,
            "lines": self.lines,
        }


@dataclass(slots=True)
class IndexAudit:
    """Diff between files on disk and rows recorded in ``corpus_index.csv``."""

    missing_from_index: list[str]
    missing_from_disk: list[str]
    stale_rows: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.missing_from_index and not self.missing_from_disk and not self.stale_rows


def slugify(value: str) -> str:
    cleaned = value.lower()
    cleaned = re.sub(r"\.(pdf|docx|xlsx|xls|csv|txt)\.md$", "", cleaned)
    cleaned = re.sub(r"\.md$", "", cleaned)
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned)
    return cleaned.strip("-")


def infer_source_format(path: Path) -> str:
    name = path.name.lower()
    for suffix in (".pdf.md", ".docx.md", ".xlsx.md", ".xls.md", ".csv.md", ".txt.md"):
        if name.endswith(suffix):
            return suffix.removeprefix(".").removesuffix(".md")
    return "md"


def _join_meta_list(value: str | list[str] | None) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "|".join(value)
    return value


def build_inventory(root: Path, corpus_subdir: str = "corpus") -> list[IndexEntry]:
    """Scan ``root / corpus_subdir`` for Markdown files and extract inventory entries."""
    corpus_dir = root / corpus_subdir
    if not corpus_dir.exists():
        return []

    entries: list[IndexEntry] = []
    for path in sorted(corpus_dir.rglob("*.md")):
        doc = parse_document(path)
        meta = doc.metadata
        rel_path = path.relative_to(root).as_posix()
        raw_text = path.read_text(encoding="utf-8", errors="replace")
        line_total = len(raw_text.splitlines())

        doc_id = str(meta.get("id") or slugify(path.name))
        default_title = re.sub(r"\.(pdf|docx|xlsx|xls|csv|txt)?\.?md$", "", path.name)
        title = str(meta.get("title") or default_title)
        doc_type = str(meta.get("doc_type") or "")
        status = str(meta.get("status") or "")
        date = str(meta.get("date") or "")
        source_fmt = str(meta.get("source_format") or infer_source_format(path))

        entries.append(
            IndexEntry(
                id=doc_id,
                title=title,
                doc_type=doc_type,
                status=status,
                tickers=_join_meta_list(meta.get("tickers")),
                themes=_join_meta_list(meta.get("themes")),
                date=date,
                source_format=source_fmt,
                path=rel_path,
                bytes=path.stat().st_size,
                lines=line_total,
            )
        )
    return entries


def write_index(entries: list[IndexEntry], output_path: Path) -> None:
    """Write inventory entries to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for entry in entries:
            writer.writerow(entry.as_dict())


def audit_index(root: Path, index_path: Path, corpus_subdir: str = "corpus") -> IndexAudit:
    """Compare on-disk corpus documents against ``corpus_index.csv``.

    Flags paths missing on either side as well as indexed rows whose recorded
    fields (title, metadata, size, line count) no longer match the file on disk.
    """
    disk_entries = {
        entry.path: entry for entry in build_inventory(root, corpus_subdir=corpus_subdir)
    }
    indexed_rows: dict[str, dict[str, str]] = {}
    if index_path.exists():
        with index_path.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("path"):
                    indexed_rows[row["path"]] = row

    stale_rows: list[str] = []
    for rel_path, entry in disk_entries.items():
        row = indexed_rows.get(rel_path)
        if row is None:
            continue
        expected = {key: str(value) for key, value in entry.as_dict().items()}
        if any((row.get(key) or "") != expected[key] for key in FIELDNAMES):
            stale_rows.append(rel_path)

    return IndexAudit(
        missing_from_index=sorted(disk_entries.keys() - indexed_rows.keys()),
        missing_from_disk=sorted(indexed_rows.keys() - disk_entries.keys()),
        stale_rows=sorted(stale_rows),
    )
