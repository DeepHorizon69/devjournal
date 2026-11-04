from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

NoteType = Literal[
    "note",
    "experiment",
    "troubleshooting",
    "project",
    "daily",
    "snippet",
]

VALID_NOTE_TYPES: frozenset[str] = frozenset(
    {
        "note",
        "experiment",
        "troubleshooting",
        "project",
        "daily",
        "snippet",
    }
)

KnowledgeDomain = Literal[
    "Networking",
    "Linux",
    "Programming",
    "IoT",
    "Cybersecurity",
    "Homelab",
    "Mathematics",
]

VALID_DOMAINS: dict[str, KnowledgeDomain] = {
    "networking": "Networking",
    "linux": "Linux",
    "programming": "Programming",
    "iot": "IoT",
    "cybersecurity": "Cybersecurity",
    "homelab": "Homelab",
    "mathematics": "Mathematics",
}

NoteStatus = Literal[
    "draft",
    "active",
    "investigating",
    "resolved",
    "completed",
    "archived",
]

VALID_STATUSES: frozenset[str] = frozenset(
    {
        "draft",
        "active",
        "investigating",
        "resolved",
        "completed",
        "archived",
    }
)

_ISO8601_TZ_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:?\d{2})$"
)


def validate_iso8601_utc_string(value: str) -> str:
    """Validate an ISO-8601 string with explicit timezone and normalize to UTC YYYY-MM-DDTHH:MM:SSZ."""
    if not isinstance(value, str):
        raise ValueError(f"Expected ISO-8601 timestamp string, got {type(value).__name__}")
    s = value.strip()
    if not _ISO8601_TZ_RE.match(s):
        raise ValueError(
            f"Invalid ISO-8601 timestamp (must include time and timezone): {value!r}"
        )
    iso_norm = s.replace(" ", "T")
    if iso_norm.endswith(("Z", "z")):
        iso_norm = iso_norm[:-1] + "+00:00"
    elif re.search(r"[+-]\d{4}$", iso_norm):
        iso_norm = iso_norm[:-2] + ":" + iso_norm[-2:]

    dt = datetime.fromisoformat(iso_norm)
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError(f"Timestamp missing timezone offset: {value!r}")

    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class NoteFrontmatter(BaseModel):
    """Canonical YAML frontmatter structure for a DevJournal Markdown note."""

    id: str
    title: str
    type: NoteType = "note"
    status: NoteStatus | None = None
    created_at: str
    updated_at: str
    domains: list[KnowledgeDomain] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    trashed: bool = False
    original_rel_path: str | None = None

    @field_validator("created_at", "updated_at")
    @classmethod
    def _validate_timestamps(cls, v: str) -> str:
        return validate_iso8601_utc_string(v)


class ParsedNote(BaseModel):
    """Complete parsed representation of a Markdown note and its derived index fields."""

    metadata: NoteFrontmatter
    raw_frontmatter_id: str | None = None
    has_id_collision: bool = False
    body: str
    slug: str
    rel_path: str
    folder: str
    excerpt: str
    headings: str
    word_count: int
    reading_time_mins: int
    content_hash: str
    file_mtime: float
    had_parse_warning: bool = False
    parse_warning_message: str | None = None


class NoteRecord(BaseModel):
    """SQLite note record hydrated with its domains and tags."""

    id: str
    title: str
    slug: str
    rel_path: str
    folder: str
    note_type: NoteType
    status: NoteStatus | None = None
    excerpt: str
    word_count: int
    reading_time_mins: int
    content_hash: str
    file_mtime: float
    is_pinned: bool
    is_trashed: bool
    original_rel_path: str | None = None
    domains: list[KnowledgeDomain] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    last_opened_at: str | None = None
