"""Fast regex/keyword search with metadata filters and line-level citations."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mdcorpus.frontmatter import parse_document


@dataclass(slots=True)
class SearchMatch:
    """A single cited line match inside the corpus."""

    path: str
    title: str
    line_number: int
    snippet: str
    tickers: list[str]
    themes: list[str]


def _matches_filters(
    metadata: dict[str, str | list[str]],
    *,
    ticker: str | None = None,
    theme: str | None = None,
    doc_type: str | None = None,
) -> bool:
    if ticker:
        raw_tickers = metadata.get("tickers", [])
        ticker_list = raw_tickers if isinstance(raw_tickers, list) else [str(raw_tickers)]
        if ticker.upper() not in {t.upper() for t in ticker_list}:
            return False

    if theme:
        raw_themes = metadata.get("themes", [])
        theme_list = raw_themes if isinstance(raw_themes, list) else [str(raw_themes)]
        if theme.lower() not in {t.lower() for t in theme_list}:
            return False

    if doc_type:
        if str(metadata.get("doc_type", "")).lower() != doc_type.lower():
            return False

    return True


def _search_files_with_rg(pattern: str, files: list[Path]) -> list[tuple[Path, int, str]]:
    cmd = [
        "rg",
        "--no-heading",
        "--line-number",
        "--ignore-case",
        "--color",
        "never",
        pattern,
        *[str(f) for f in files],
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 1):
        raise RuntimeError(proc.stderr.strip() or "ripgrep search failed")

    results: list[tuple[Path, int, str]] = []
    single_file = len(files) == 1
    for line in proc.stdout.splitlines():
        if single_file:
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[0].isdigit():
                results.append((files[0], int(parts[0]), parts[1].strip()))
        else:
            parts = line.split(":", 2)
            if len(parts) == 3 and parts[1].isdigit():
                results.append((Path(parts[0]), int(parts[1]), parts[2].strip()))
    return results


def _search_files_python(pattern: str, files: list[Path]) -> list[tuple[Path, int, str]]:
    compiled = re.compile(pattern, re.IGNORECASE)
    results: list[tuple[Path, int, str]] = []
    for path in files:
        for line_no, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(),
            start=1,
        ):
            if compiled.search(line):
                results.append((path, line_no, line.strip()))
    return results


def search_corpus(
    root: Path,
    pattern: str,
    *,
    corpus_subdir: str = "corpus",
    ticker: str | None = None,
    theme: str | None = None,
    doc_type: str | None = None,
    limit: int = 25,
    prefer_rg: bool = True,
) -> list[SearchMatch]:
    """Search Markdown corpus documents and return line-cited matches."""
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid search pattern {pattern!r}: {exc}") from exc

    corpus_dir = root / corpus_subdir
    if not corpus_dir.exists():
        return []

    candidate_docs = {}
    for path in sorted(corpus_dir.rglob("*.md")):
        doc = parse_document(path)
        if _matches_filters(doc.metadata, ticker=ticker, theme=theme, doc_type=doc_type):
            candidate_docs[path] = doc

    if not candidate_docs:
        return []

    files = list(candidate_docs.keys())
    if prefer_rg and shutil.which("rg"):
        raw_hits = _search_files_with_rg(pattern, files)
    else:
        raw_hits = _search_files_python(pattern, files)

    matches: list[SearchMatch] = []
    for path, line_no, snippet in raw_hits:
        doc = candidate_docs.get(path)
        if doc is None or line_no < doc.body_start_line:
            continue
        raw_tickers = doc.metadata.get("tickers", [])
        raw_themes = doc.metadata.get("themes", [])
        matches.append(
            SearchMatch(
                path=path.relative_to(root).as_posix(),
                title=str(doc.metadata.get("title") or path.stem),
                line_number=line_no,
                snippet=snippet,
                tickers=raw_tickers if isinstance(raw_tickers, list) else [],
                themes=raw_themes if isinstance(raw_themes, list) else [],
            )
        )
        if len(matches) >= limit:
            break

    return matches
