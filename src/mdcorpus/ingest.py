"""Convert raw research sources into normalized frontmatter Markdown."""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

from mdcorpus.frontmatter import dump_frontmatter, parse_frontmatter
from mdcorpus.indexer import slugify


def _csv_to_markdown_table(path: Path) -> str:
    with path.open("r", newline="", encoding="utf-8", errors="replace") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        return ""
    header = rows[0]
    separator = ["---"] * len(header)
    lines = [
        "| " + " | ".join(cell.strip() for cell in header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in rows[1:]:
        padded = row + [""] * max(0, len(header) - len(row))
        lines.append("| " + " | ".join(cell.strip() for cell in padded[: len(header)]) + " |")
    return "\n".join(lines) + "\n"


def _extract_body(source: Path) -> tuple[str, str]:
    """Return ``(body_markdown, source_format)`` for a supported raw file."""
    suffix = source.suffix.lower()

    if suffix in (".md", ".markdown"):
        _, body, _ = parse_frontmatter(source.read_text(encoding="utf-8", errors="replace"))
        return body, "md"

    if suffix == ".txt":
        return source.read_text(encoding="utf-8", errors="replace"), "txt"

    if suffix == ".csv":
        return _csv_to_markdown_table(source), "csv"

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - optional extra
            raise RuntimeError(
                "PDF ingestion requires optional parsers: pip install 'md-research-corpus[parsers]'"
            ) from exc
        reader = PdfReader(str(source))
        pages = [
            f"## Page {idx}\n\n{(page.extract_text() or '').strip()}"
            for idx, page in enumerate(reader.pages, start=1)
        ]
        return "\n\n".join(pages) + "\n", "pdf"

    if suffix == ".docx":
        try:
            import docx
        except ImportError as exc:  # pragma: no cover - optional extra
            raise RuntimeError(
                "DOCX ingestion requires optional parsers: "
                "pip install 'md-research-corpus[parsers]'"
            ) from exc
        document = docx.Document(str(source))
        paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs) + "\n", "docx"

    if suffix in (".xlsx", ".xls"):
        try:
            import openpyxl
        except ImportError as exc:  # pragma: no cover - optional extra
            raise RuntimeError(
                "XLSX ingestion requires optional parsers: "
                "pip install 'md-research-corpus[parsers]'"
            ) from exc
        wb = openpyxl.load_workbook(str(source), data_only=True)
        sections: list[str] = []
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            rows = [
                ["" if cell is None else str(cell).strip() for cell in row]
                for row in sheet.iter_rows(values_only=True)
            ]
            rows = [r for r in rows if any(r)]
            if not rows:
                continue
            header = rows[0]
            md_lines = [
                f"## {sheet_name}",
                "",
                "| " + " | ".join(header) + " |",
                "| " + " | ".join(["---"] * len(header)) + " |",
            ]
            for row in rows[1:]:
                md_lines.append("| " + " | ".join(row[: len(header)]) + " |")
            sections.append("\n".join(md_lines))
        return "\n\n".join(sections) + "\n", "xlsx"

    raise ValueError(f"Unsupported file type: {suffix or source.name}")


def ingest_file(
    source: Path,
    dest_dir: Path,
    *,
    title: str | None = None,
    doc_type: str = "note",
    status: str = "active",
    tickers: list[str] | None = None,
    themes: list[str] | None = None,
    date: str | None = None,
) -> Path:
    """Convert ``source`` into a normalized Markdown file inside ``dest_dir``."""
    body, source_fmt = _extract_body(source)
    doc_slug = slugify(source.stem)
    resolved_title = title or source.stem.replace("-", " ").replace("_", " ").strip().title()
    resolved_date = date or dt.date.today().isoformat()

    metadata: dict[str, str | list[str]] = {
        "id": doc_slug,
        "title": resolved_title,
        "doc_type": doc_type,
        "status": status,
        "date": resolved_date,
        "source_format": source_fmt,
        "tickers": [t.upper() for t in (tickers or [])],
        "themes": list(themes or []),
    }

    dest_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"{doc_slug}.md" if source_fmt == "md" else f"{doc_slug}.{source_fmt}.md"
    out_path = dest_dir / out_name
    out_path.write_text(dump_frontmatter(metadata, body), encoding="utf-8")
    return out_path
