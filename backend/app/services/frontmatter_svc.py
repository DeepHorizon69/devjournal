from __future__ import annotations

import hashlib
import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from app.models.note import (
    VALID_DOMAINS,
    VALID_NOTE_TYPES,
    VALID_STATUSES,
    KnowledgeDomain,
    NoteFrontmatter,
    NoteStatus,
    NoteType,
    ParsedNote,
    validate_iso8601_utc_string,
)
from app.services.vault_storage import TRASH_FOLDER, slugify_title

FOLDER_TO_DEFAULT_NOTE_TYPE: dict[str, NoteType] = {
    "00-Inbox": "note",
    "10-Notes": "note",
    "20-Projects": "project",
    "30-Experiments": "experiment",
    "40-Troubleshooting": "troubleshooting",
    "50-Snippets": "snippet",
    "90-Daily": "daily",
    "99-Trash": "note",
}

_HEADING_RE = re.compile(r"(?m)^#{1,4}\s+(.+?)\s*$")
_H1_RE = re.compile(r"(?m)^#\s+(.+?)\s*$")
_FENCED_CODE_RE = re.compile(r"```[\s\S]*?```|~~~[\s\S]*?~~~")
_ANY_HEADING_LINE_RE = re.compile(r"(?m)^#{1,6}\s+.*$")
_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_INLINE_FORMAT_RE = re.compile(r"[*_`~>]+")
_WHITESPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"\b\w+\b")
_TAG_SPACE_UNDERSCORE_RE = re.compile(r"[\s_]+")
_TAG_DISALLOWED_RE = re.compile(r"[^a-z0-9\-_./]")
_TAG_MULTI_DASH_RE = re.compile(r"-{2,}")


def normalize_lf(content: str) -> str:
    """Normalize CRLF and CR line endings to LF without altering blank lines."""
    return content.replace("\r\n", "\n").replace("\r", "\n")


def compute_content_hash(content: str) -> str:
    """Compute lowercase hex SHA-256 of LF-normalized UTF-8 Markdown content."""
    return hashlib.sha256(normalize_lf(content).encode("utf-8")).hexdigest()


def normalize_tags(raw_tags: Any) -> list[str]:
    """Normalize tags to lowercase kebab-case, strip invalid chars, and deduplicate."""
    if raw_tags is None:
        return []
    if isinstance(raw_tags, str):
        items: list[Any] = raw_tags.split(",")
    elif isinstance(raw_tags, (list, tuple, set)):
        items = list(raw_tags)
    else:
        return []

    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item is None or isinstance(item, (dict, list, bool)):
            continue
        s = str(item).strip().lstrip("#").strip().lower()
        if not s:
            continue
        s = _TAG_SPACE_UNDERSCORE_RE.sub("-", s)
        s = _TAG_DISALLOWED_RE.sub("", s)
        s = _TAG_MULTI_DASH_RE.sub("-", s).strip("-")
        if s and s not in seen:
            seen.add(s)
            result.append(s)
    return result


def normalize_domains(raw_domains: Any) -> list[KnowledgeDomain]:
    """Match domains case-insensitively against VALID_DOMAINS and deduplicate."""
    if raw_domains is None:
        return []
    if isinstance(raw_domains, str):
        items: list[Any] = [part.strip() for part in raw_domains.split(",")]
    elif isinstance(raw_domains, (list, tuple, set)):
        items = list(raw_domains)
    else:
        return []

    seen: set[KnowledgeDomain] = set()
    result: list[KnowledgeDomain] = []
    for item in items:
        if not isinstance(item, str):
            continue
        key = item.strip().lower()
        canonical = VALID_DOMAINS.get(key)
        if canonical is not None and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


def extract_headings(body: str) -> str:
    """Extract H1-H4 headings from Markdown body for FTS5 indexing."""
    matches = _HEADING_RE.findall(body)
    cleaned: list[str] = []
    for m in matches:
        text = _MD_LINK_RE.sub(r"\1", m)
        text = _INLINE_FORMAT_RE.sub("", text).strip()
        if text:
            cleaned.append(text)
    return " \n ".join(cleaned)


def extract_excerpt(body: str, max_len: int = 200) -> str:
    """Extract a plain-text excerpt from the Markdown body (excluding code blocks and headings)."""
    text = _FENCED_CODE_RE.sub(" ", body)
    text = _ANY_HEADING_LINE_RE.sub(" ", text)
    text = _MD_IMAGE_RE.sub(r"\1", text)
    text = _MD_LINK_RE.sub(r"\1", text)
    text = _INLINE_FORMAT_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "..."


def compute_word_stats(body: str) -> tuple[int, int]:
    """Return (word_count, reading_time_mins) where reading_time_mins is at least 1."""
    word_count = len(_WORD_RE.findall(body))
    reading_time_mins = max(1, math.ceil(word_count / 200))
    return word_count, reading_time_mins


def normalize_iso8601_utc(
    raw_val: Any, fallback_mtime: float
) -> tuple[str, bool, str | None]:
    """Validate and normalize a timestamp to UTC ISO-8601 or fall back to file_mtime."""
    fallback_iso = datetime.fromtimestamp(fallback_mtime, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    if raw_val is None:
        return fallback_iso, False, None

    if type(raw_val) is datetime:
        if raw_val.tzinfo is None or raw_val.tzinfo.utcoffset(raw_val) is None:
            return (
                fallback_iso,
                True,
                f"Timestamp missing timezone: {raw_val!r}; using file_mtime fallback",
            )
        utc_str = raw_val.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return utc_str, False, None

    if isinstance(raw_val, str):
        try:
            utc_str = validate_iso8601_utc_string(raw_val)
            return utc_str, False, None
        except ValueError:
            return (
                fallback_iso,
                True,
                f"Invalid ISO-8601 timestamp {raw_val!r}; using file_mtime fallback",
            )

    return (
        fallback_iso,
        True,
        f"Invalid timestamp value {raw_val!r}; using file_mtime fallback",
    )


def serialize_note(metadata: NoteFrontmatter, body: str) -> str:
    """Serialize NoteFrontmatter and Markdown body into canonical LF-normalized Markdown.

    Preserves the Markdown body verbatim (after LF normalization) without stripping
    leading or trailing blank lines.
    """
    frontmatter_dict: dict[str, Any] = {
        "id": metadata.id,
        "title": metadata.title,
        "type": metadata.type,
        "status": metadata.status,
        "created_at": metadata.created_at,
        "updated_at": metadata.updated_at,
        "domains": list(metadata.domains),
        "tags": list(metadata.tags),
        "pinned": bool(metadata.pinned),
        "trashed": bool(metadata.trashed),
        "original_rel_path": metadata.original_rel_path,
    }
    yaml_block = yaml.safe_dump(
        frontmatter_dict,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    body_lf = normalize_lf(body)
    return f"---\n{yaml_block}\n---\n{body_lf}"


def _infer_title(raw_title: Any, body: str, rel_path: str) -> str:
    if isinstance(raw_title, str) and raw_title.strip():
        return raw_title.strip()
    h1_match = _H1_RE.search(body)
    if h1_match and h1_match.group(1).strip():
        return h1_match.group(1).strip()
    stem = Path(rel_path).stem
    inferred = re.sub(r"[-_]+", " ", stem).strip()
    return inferred.title() if inferred else "Untitled"


def parse_markdown_note(
    raw_content: str,
    rel_path: str,
    file_mtime: float,
) -> ParsedNote:
    """Parse a raw Markdown string into a ParsedNote with fault tolerance and folder-authoritative trash state."""
    text_lf = normalize_lf(raw_content)
    content_hash = compute_content_hash(text_lf)
    norm_rel_path = PurePosixPath(rel_path.replace("\\", "/")).as_posix()
    parts = PurePosixPath(norm_rel_path).parts
    folder = parts[0] if parts else "10-Notes"

    warnings: list[str] = []
    raw_meta: dict[str, Any] = {}
    body = text_lf

    # 1. Frontmatter Fence Splitting
    if text_lf.startswith("---\n") or text_lf == "---":
        if text_lf == "---":
            warnings.append(
                "Unclosed YAML frontmatter fence; treating entire file as Markdown body"
            )
            body = text_lf
        else:
            close_idx = text_lf.find("\n---\n", 3)
            if close_idx != -1:
                yaml_str = text_lf[4:close_idx]
                body = text_lf[close_idx + 5 :]
                _parse_yaml_block(yaml_str, raw_meta, warnings)
            elif text_lf.endswith("\n---") and len(text_lf) >= 7:
                yaml_str = text_lf[4:-4]
                body = ""
                _parse_yaml_block(yaml_str, raw_meta, warnings)
            else:
                warnings.append(
                    "Unclosed YAML frontmatter fence; treating entire file as Markdown body"
                )
                body = text_lf

    # 2. Identity Inference
    raw_id_val = raw_meta.get("id")
    raw_frontmatter_id = (
        raw_id_val.strip()
        if isinstance(raw_id_val, str) and raw_id_val.strip()
        else None
    )
    effective_id = (
        raw_frontmatter_id
        if raw_frontmatter_id is not None
        else str(uuid.uuid5(uuid.NAMESPACE_URL, f"devjournal:{norm_rel_path}"))
    )

    # 3. Title, Type, Status
    title = _infer_title(raw_meta.get("title"), body, norm_rel_path)

    raw_type = raw_meta.get("type")
    if isinstance(raw_type, str) and raw_type in VALID_NOTE_TYPES:
        note_type: NoteType = raw_type  # type: ignore[assignment]
    else:
        note_type = FOLDER_TO_DEFAULT_NOTE_TYPE.get(folder, "note")

    raw_status = raw_meta.get("status")
    status: NoteStatus | None = (
        raw_status  # type: ignore[assignment]
        if isinstance(raw_status, str) and raw_status in VALID_STATUSES
        else None
    )

    # 4. Strict Timestamp Validation
    created_at, created_warn, created_msg = normalize_iso8601_utc(
        raw_meta.get("created_at"), file_mtime
    )
    if created_warn and created_msg:
        warnings.append(f"created_at: {created_msg}")

    updated_at, updated_warn, updated_msg = normalize_iso8601_utc(
        raw_meta.get("updated_at"), file_mtime
    )
    if updated_warn and updated_msg:
        warnings.append(f"updated_at: {updated_msg}")

    # 5. Domains, Tags, Pinned
    domains = normalize_domains(raw_meta.get("domains"))
    tags = normalize_tags(raw_meta.get("tags"))
    raw_pinned = raw_meta.get("pinned", False)
    pinned = raw_pinned if isinstance(raw_pinned, bool) else False

    # 6. Folder-Authoritative Trash & original_rel_path Semantics
    raw_trashed = raw_meta.get("trashed")
    raw_orig_rel = raw_meta.get("original_rel_path")
    clean_orig_rel = (
        raw_orig_rel.strip()
        if isinstance(raw_orig_rel, str) and raw_orig_rel.strip()
        else None
    )

    if folder == TRASH_FOLDER:
        trashed = True
        original_rel_path = clean_orig_rel
        if raw_trashed is False:
            warnings.append(
                "Note is in 99-Trash with trashed=false in frontmatter; folder state is authoritative"
            )
    else:
        trashed = False
        original_rel_path = None
        if raw_trashed is True or clean_orig_rel is not None:
            warnings.append(
                "Note is in active folder with stale trash metadata; folder state is authoritative"
            )

    metadata = NoteFrontmatter(
        id=effective_id,
        title=title,
        type=note_type,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
        domains=domains,
        tags=tags,
        pinned=pinned,
        trashed=trashed,
        original_rel_path=original_rel_path,
    )

    slug = Path(norm_rel_path).stem or slugify_title(title, fallback_id=effective_id)
    headings = extract_headings(body)
    excerpt = extract_excerpt(body)
    word_count, reading_time_mins = compute_word_stats(body)

    had_parse_warning = len(warnings) > 0
    parse_warning_message = "; ".join(warnings) if warnings else None

    return ParsedNote(
        metadata=metadata,
        raw_frontmatter_id=raw_frontmatter_id,
        has_id_collision=False,
        body=body,
        slug=slug,
        rel_path=norm_rel_path,
        folder=folder,
        excerpt=excerpt,
        headings=headings,
        word_count=word_count,
        reading_time_mins=reading_time_mins,
        content_hash=content_hash,
        file_mtime=file_mtime,
        had_parse_warning=had_parse_warning,
        parse_warning_message=parse_warning_message,
    )


def _parse_yaml_block(
    yaml_str: str,
    raw_meta_out: dict[str, Any],
    warnings_out: list[str],
) -> None:
    """Safely deserialize YAML frontmatter block and validate it is a mapping."""
    if yaml_str.strip() == "":
        warnings_out.append("Empty YAML frontmatter block; using inferred defaults")
        return

    try:
        loaded = yaml.safe_load(yaml_str)
    except yaml.YAMLError as exc:
        warnings_out.append(f"Malformed YAML frontmatter: {exc}")
        return

    if loaded is None:
        warnings_out.append("Empty YAML frontmatter block; using inferred defaults")
        return

    if not isinstance(loaded, dict):
        warnings_out.append(
            f"YAML frontmatter must be a mapping, got {type(loaded).__name__}"
        )
        return

    raw_meta_out.update(loaded)
