"""Minimal YAML-frontmatter parser and serializer with zero third-party dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Document:
    """A parsed Markdown document with optional frontmatter metadata."""

    path: Path
    metadata: dict[str, str | list[str]] = field(default_factory=dict)
    body: str = ""
    body_start_line: int = 1


def _parse_scalar(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _parse_inline_list(raw: str) -> list[str]:
    inner = raw.strip()[1:-1].strip()
    if not inner:
        return []
    return [_parse_scalar(item) for item in inner.split(",") if item.strip()]


def parse_frontmatter(text: str) -> tuple[dict[str, str | list[str]], str, int]:
    """Parse leading ``---`` frontmatter from Markdown text.

    Returns ``(metadata, body, body_start_line)`` where ``body_start_line`` is
    the 1-based line number of the first body line in the original file.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, 1

    end_idx: int | None = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break

    if end_idx is None:
        return {}, text, 1

    metadata: dict[str, str | list[str]] = {}
    current_list_key: str | None = None

    for line in lines[1:end_idx]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_list_key is not None:
            existing = metadata.get(current_list_key)
            if isinstance(existing, list):
                existing.append(_parse_scalar(stripped[2:]))
            continue

        if ":" not in line:
            current_list_key = None
            continue

        key, raw_val = line.split(":", 1)
        key = key.strip()
        raw_val = raw_val.strip()
        if not raw_val:
            metadata[key] = []
            current_list_key = key
        elif raw_val.startswith("[") and raw_val.endswith("]"):
            metadata[key] = _parse_inline_list(raw_val)
            current_list_key = None
        else:
            metadata[key] = _parse_scalar(raw_val)
            current_list_key = None

    body = "\n".join(lines[end_idx + 1 :])
    if text.endswith("\n"):
        body += "\n"
    return metadata, body, end_idx + 2


def parse_document(path: Path) -> Document:
    """Read and parse a Markdown file from disk."""
    text = path.read_text(encoding="utf-8", errors="replace")
    metadata, body, body_start_line = parse_frontmatter(text)
    return Document(
        path=path,
        metadata=metadata,
        body=body,
        body_start_line=body_start_line,
    )


def dump_frontmatter(metadata: dict[str, str | list[str]], body: str) -> str:
    """Serialize metadata and body into a normalized Markdown document."""
    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, list):
            formatted = ", ".join(value)
            lines.append(f"{key}: [{formatted}]")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    normalized_body = body.lstrip("\n")
    if normalized_body and not normalized_body.endswith("\n"):
        normalized_body += "\n"
    return "\n".join(lines) + normalized_body
