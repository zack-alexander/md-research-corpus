from __future__ import annotations

import json
from pathlib import Path

from mdcorpus.cli import main
from mdcorpus.indexer import audit_index, build_inventory, write_index
from mdcorpus.ingest import ingest_file
from mdcorpus.search import search_corpus
from mdcorpus.validator import validate_corpus

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_sample_corpus_validates_cleanly() -> None:
    issues = validate_corpus(REPO_ROOT)
    assert issues == []


def test_inventory_and_index_audit(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus" / "notes"
    raw_txt = tmp_path / "draft.txt"
    raw_txt.write_text("Capital allocation drives compounding.\n", encoding="utf-8")

    out = ingest_file(
        raw_txt,
        corpus_dir,
        title="Compounding Memo",
        doc_type="memo",
        tickers=["acme"],
        themes=["capital-allocation"],
        date="2026-11-15",
    )
    assert out.exists()

    entries = build_inventory(tmp_path)
    assert len(entries) == 1
    assert entries[0].tickers == "ACME"
    assert entries[0].source_format == "txt"

    index_path = tmp_path / "corpus_index.csv"
    write_index(entries, index_path)
    assert audit_index(tmp_path, index_path).is_clean

    # Add an unindexed document and verify drift detection catches it
    extra = corpus_dir / "unindexed.md"
    extra.write_text("---\nid: extra\n---\nUnindexed body.\n", encoding="utf-8")
    audit = audit_index(tmp_path, index_path)
    assert not audit.is_clean
    assert "corpus/notes/unindexed.md" in audit.missing_from_index


def test_csv_ingestion_formats_markdown_table(tmp_path: Path) -> None:
    raw_csv = tmp_path / "metrics.csv"
    raw_csv.write_text("Ticker,ROIC\nACME,22%\nDEMO,15%\n", encoding="utf-8")

    out = ingest_file(raw_csv, tmp_path / "corpus", doc_type="screen", date="2026-11-15")
    text = out.read_text(encoding="utf-8")
    assert "| Ticker | ROIC |" in text
    assert "| ACME | 22% |" in text


def test_validator_catches_bad_vocab_and_duplicate_ids(tmp_path: Path) -> None:
    vocab_dir = tmp_path / "metadata"
    vocab_dir.mkdir()
    (vocab_dir / "vocab.json").write_text(
        json.dumps({"doc_types": ["memo"], "statuses": ["active"], "themes": ["macro"]}),
        encoding="utf-8",
    )
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.md").write_text(
        "---\nid: dup\ntitle: A\ndoc_type: invalid\nstatus: active\ndate: 2026-99\n"
        "themes: [unknown-theme]\n---\nBody\n",
        encoding="utf-8",
    )
    (corpus / "b.md").write_text(
        "---\nid: dup\ntitle: B\ndoc_type: memo\nstatus: active\ndate: 2026-11-01\n---\nBody\n",
        encoding="utf-8",
    )

    issues = validate_corpus(tmp_path)
    fields = {issue.field for issue in issues}
    assert {"doc_type", "date", "themes", "id"}.issubset(fields)


def test_search_with_filters_both_backends() -> None:
    for prefer_rg in (True, False):
        matches = search_corpus(
            REPO_ROOT,
            "ROIC",
            theme="capital-allocation",
            prefer_rg=prefer_rg,
        )
        assert len(matches) >= 1
        assert all(m.path.endswith("capital-allocation-framework.md") for m in matches)
        assert all(m.line_number >= 10 for m in matches)

    empty = search_corpus(REPO_ROOT, "ROIC", ticker="NONEXISTENT", prefer_rg=False)
    assert empty == []


def test_cli_search_json_and_validate(capsys) -> None:
    assert main(["validate", "--root", str(REPO_ROOT)]) == 0
    capsys.readouterr()

    assert main(["search", "margin of safety", "--root", str(REPO_ROOT), "--json"]) == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert len(parsed) == 1
    assert parsed[0]["tickers"] == ["ROYL"]
