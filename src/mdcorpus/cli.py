"""Command-line interface for md-research-corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mdcorpus.indexer import audit_index, build_inventory, write_index
from mdcorpus.ingest import ingest_file
from mdcorpus.search import search_corpus
from mdcorpus.validator import validate_corpus


def _cmd_ingest(args: argparse.Namespace) -> int:
    source = Path(args.source).resolve()
    dest = Path(args.dest).resolve()
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()] if args.tickers else []
    themes = [t.strip() for t in args.themes.split(",") if t.strip()] if args.themes else []
    out_path = ingest_file(
        source,
        dest,
        title=args.title,
        doc_type=args.doc_type,
        status=args.status,
        tickers=tickers,
        themes=themes,
        date=args.date,
    )
    print(f"Wrote {out_path}")
    return 0


def _cmd_index(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    index_path = Path(args.output).resolve() if args.output else root / "corpus_index.csv"
    if args.check:
        audit = audit_index(root, index_path)
        if audit.is_clean:
            print(f"Index OK: {index_path.name} matches corpus on disk.")
            return 0
        if audit.missing_from_index:
            print("Missing from index:", file=sys.stderr)
            for item in audit.missing_from_index:
                print(f"  + {item}", file=sys.stderr)
        if audit.missing_from_disk:
            print("Missing from disk:", file=sys.stderr)
            for item in audit.missing_from_disk:
                print(f"  - {item}", file=sys.stderr)
        return 1

    entries = build_inventory(root)
    write_index(entries, index_path)
    print(f"Indexed {len(entries)} documents -> {index_path}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    issues = validate_corpus(root)
    if not issues:
        entries = build_inventory(root)
        print(f"Validation passed ({len(entries)} documents checked).")
        return 0
    for issue in issues:
        print(f"{issue.path} [{issue.field}]: {issue.message}", file=sys.stderr)
    return 1


def _cmd_search(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    matches = search_corpus(
        root,
        args.pattern,
        ticker=args.ticker,
        theme=args.theme,
        doc_type=args.doc_type,
        limit=args.limit,
    )
    if args.json:
        payload = [
            {
                "path": m.path,
                "title": m.title,
                "line": m.line_number,
                "snippet": m.snippet,
                "tickers": m.tickers,
                "themes": m.themes,
            }
            for m in matches
        ]
        print(json.dumps(payload, indent=2))
        return 0

    if not matches:
        print("No matches found.")
        return 0

    for match in matches:
        tags = ", ".join(match.tickers + match.themes)
        tag_suffix = f" ({tags})" if tags else ""
        print(f"{match.path}:{match.line_number} — {match.title}{tag_suffix}")
        print(f"  {match.snippet}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mdcorpus",
        description="Manage, validate, index, and search a Markdown research corpus.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Convert a raw file into frontmatter Markdown.")
    p_ingest.add_argument(
        "source",
        help="Path to source file (.md, .txt, .csv, .pdf, .docx, .xlsx)",
    )
    p_ingest.add_argument("--dest", default="corpus/ingested", help="Output directory")
    p_ingest.add_argument("--title", help="Override document title")
    p_ingest.add_argument("--doc-type", default="note", help="Controlled doc_type value")
    p_ingest.add_argument("--status", default="active", help="Controlled status value")
    p_ingest.add_argument("--tickers", default="", help="Comma-separated ticker symbols")
    p_ingest.add_argument("--themes", default="", help="Comma-separated theme tags")
    p_ingest.add_argument("--date", help="ISO date YYYY-MM-DD (defaults to today)")
    p_ingest.set_defaults(func=_cmd_ingest)

    p_index = sub.add_parser("index", help="Build or audit corpus_index.csv.")
    p_index.add_argument("--root", default=".", help="Corpus repository root")
    p_index.add_argument("--output", help="Custom CSV path (default: <root>/corpus_index.csv)")
    p_index.add_argument("--check", action="store_true", help="Exit nonzero if index drifted")
    p_index.set_defaults(func=_cmd_index)

    p_val = sub.add_parser("validate", help="Validate frontmatter against metadata/vocab.json.")
    p_val.add_argument("--root", default=".", help="Corpus repository root")
    p_val.set_defaults(func=_cmd_validate)

    p_search = sub.add_parser("search", help="Search corpus with metadata filters and citations.")
    p_search.add_argument("pattern", help="Regex or keyword pattern (case-insensitive)")
    p_search.add_argument("--root", default=".", help="Corpus repository root")
    p_search.add_argument("--ticker", help="Filter by ticker symbol")
    p_search.add_argument("--theme", help="Filter by controlled theme")
    p_search.add_argument("--doc-type", help="Filter by document type")
    p_search.add_argument("--limit", type=int, default=25, help="Max matches to return")
    p_search.add_argument("--json", action="store_true", help="Emit JSON output")
    p_search.set_defaults(func=_cmd_search)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
