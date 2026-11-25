"""mdcorpus: version-controlled Markdown research corpus toolkit."""

from mdcorpus.frontmatter import Document, dump_frontmatter, parse_document
from mdcorpus.indexer import IndexAudit, IndexEntry, audit_index, build_inventory, write_index
from mdcorpus.search import SearchMatch, search_corpus
from mdcorpus.validator import ValidationIssue, validate_corpus

__all__ = [
    "Document",
    "IndexAudit",
    "IndexEntry",
    "SearchMatch",
    "ValidationIssue",
    "audit_index",
    "build_inventory",
    "dump_frontmatter",
    "parse_document",
    "search_corpus",
    "validate_corpus",
    "write_index",
]
