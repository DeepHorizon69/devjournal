from __future__ import annotations

import uuid

import pytest

from app.models.note import NoteFrontmatter
from app.services.frontmatter_svc import (
    compute_content_hash,
    compute_word_stats,
    extract_excerpt,
    extract_headings,
    normalize_domains,
    normalize_tags,
    parse_markdown_note,
    serialize_note,
)


def test_serialize_and_parse_roundtrip_all_fields() -> None:
    fm = NoteFrontmatter(
        id="550e8400-e29b-41d4-a716-446655440000",
        title="WireGuard MTU Debugging",
        type="troubleshooting",
        status="resolved",
        created_at="2026-11-04T09:30:00Z",
        updated_at="2026-11-04T14:22:10Z",
        domains=["Networking", "Linux"],
        tags=["wireguard", "mtu", "vpn"],
        pinned=True,
        trashed=False,
        original_rel_path=None,
    )
    body = "## Symptom\n\nPackets larger than 1380 bytes drop silently.\n"
    raw = serialize_note(fm, body)
    parsed = parse_markdown_note(
        raw, rel_path="40-Troubleshooting/wireguard-mtu-debugging.md", file_mtime=1730712600.0
    )

    assert not parsed.had_parse_warning
    assert parsed.metadata == fm
    assert parsed.raw_frontmatter_id == fm.id
    assert parsed.body == body
    assert parsed.folder == "40-Troubleshooting"
    assert parsed.slug == "wireguard-mtu-debugging"
    assert parsed.content_hash == compute_content_hash(raw)


@pytest.mark.parametrize(
    "body",
    [
        "\n\n## Section With Leading Blank Lines\nBody paragraph.\n",
        "Body with multiple trailing blank lines.\n\n\n",
        "\n\nBoth leading and trailing blank lines.\n\n",
        "",
    ],
)
def test_verbatim_body_preservation(body: str) -> None:
    fm = NoteFrontmatter(
        id="11111111-2222-3333-4444-555555555555",
        title="Verbatim Body Check",
        type="note",
        status="active",
        created_at="2026-11-04T09:30:00Z",
        updated_at="2026-11-04T09:30:00Z",
    )
    raw = serialize_note(fm, body)
    parsed = parse_markdown_note(raw, rel_path="10-Notes/verbatim.md", file_mtime=1730712600.0)
    assert parsed.body == body
    assert not parsed.had_parse_warning


def test_strict_timestamp_validation_and_normalization() -> None:
    mtime = 1730712600.0  # 2024-11-04T09:30:00Z

    # 1. Valid UTC timestamp
    md_utc = (
        "---\n"
        'id: "id-1"\n'
        'title: "UTC Note"\n'
        'created_at: "2026-11-04T09:30:00Z"\n'
        'updated_at: "2026-11-04T09:30:00Z"\n'
        "---\nBody\n"
    )
    p1 = parse_markdown_note(md_utc, "10-Notes/utc.md", mtime)
    assert not p1.had_parse_warning
    assert p1.metadata.created_at == "2026-11-04T09:30:00Z"

    # 2. Valid timezone offset (+02:00) normalized to UTC
    md_offset = (
        "---\n"
        'id: "id-2"\n'
        'title: "Offset Note"\n'
        'created_at: "2026-11-04T11:30:00+02:00"\n'
        'updated_at: "2026-11-04T04:30:00-05:00"\n'
        "---\nBody\n"
    )
    p2 = parse_markdown_note(md_offset, "10-Notes/offset.md", mtime)
    assert not p2.had_parse_warning
    assert p2.metadata.created_at == "2026-11-04T09:30:00Z"
    assert p2.metadata.updated_at == "2026-11-04T09:30:00Z"

    # 3. Missing timezone (naive timestamp or bare date) rejected -> fallback to mtime
    for bad_ts in ["2026-11-04T09:30:00", "2026-11-04"]:
        md_naive = (
            "---\n"
            'id: "id-3"\n'
            'title: "Naive Note"\n'
            f'created_at: "{bad_ts}"\n'
            'updated_at: "2026-11-04T09:30:00Z"\n'
            "---\nBody\n"
        )
        p_naive = parse_markdown_note(md_naive, "10-Notes/naive.md", mtime)
        assert p_naive.had_parse_warning
        assert p_naive.metadata.created_at == "2024-11-04T09:30:00Z"

    # 4. Invalid calendar date or arbitrary string rejected -> fallback to mtime
    for invalid_ts in ["2026-02-30T10:00:00Z", "not-a-timestamp"]:
        md_bad = (
            "---\n"
            'id: "id-4"\n'
            'title: "Bad Date Note"\n'
            f'created_at: "{invalid_ts}"\n'
            'updated_at: "2026-11-04T09:30:00Z"\n'
            "---\nBody\n"
        )
        p_bad = parse_markdown_note(md_bad, "10-Notes/bad-date.md", mtime)
        assert p_bad.had_parse_warning
        assert p_bad.metadata.created_at == "2024-11-04T09:30:00Z"


def test_missing_frontmatter_deterministic_inference() -> None:
    raw = "# Quick Dropped Note\n\nSome content in the inbox.\n"
    rel_path = "00-Inbox/quick-dropped-note.md"
    parsed = parse_markdown_note(raw, rel_path=rel_path, file_mtime=1730712600.0)

    expected_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"devjournal:{rel_path}"))
    assert not parsed.had_parse_warning
    assert parsed.raw_frontmatter_id is None
    assert parsed.metadata.id == expected_uuid
    assert parsed.metadata.title == "Quick Dropped Note"
    assert parsed.metadata.type == "note"
    assert parsed.folder == "00-Inbox"

    # Experiment folder inference
    exp_parsed = parse_markdown_note(
        "No heading here.", rel_path="30-Experiments/esp32-power-test.md", file_mtime=1730712600.0
    )
    assert exp_parsed.metadata.type == "experiment"
    assert exp_parsed.metadata.title == "Esp32 Power Test"


@pytest.mark.parametrize(
    "raw_md,expected_warning_substr",
    [
        ("---\ntitle: [unclosed\n---\nBody text\n", "Malformed YAML frontmatter"),
        ("---\njust a scalar string\n---\nBody text\n", "YAML frontmatter must be a mapping, got str"),
        ("---\n- item1\n- item2\n---\nBody text\n", "YAML frontmatter must be a mapping, got list"),
        ("---\n---\nBody text\n", "Empty YAML frontmatter block"),
        ("---\n# only a comment\n---\nBody text\n", "Empty YAML frontmatter block"),
        ("---\ntitle: No closing fence\nBody text\n", "Unclosed YAML frontmatter fence"),
    ],
)
def test_malformed_and_non_mapping_yaml_frontmatter_graceful_fallback(
    raw_md: str, expected_warning_substr: str
) -> None:
    parsed = parse_markdown_note(
        raw_md, rel_path="10-Notes/faulty.md", file_mtime=1730712600.0
    )
    assert parsed.had_parse_warning
    assert parsed.parse_warning_message is not None
    assert expected_warning_substr in parsed.parse_warning_message
    assert parsed.metadata.id == str(
        uuid.uuid5(uuid.NAMESPACE_URL, "devjournal:10-Notes/faulty.md")
    )


def test_folder_authoritative_trash_semantics() -> None:
    # File in 99-Trash with trashed: false -> forced to trashed=True with warning
    md_in_trash = (
        "---\n"
        'id: "trash-1"\n'
        'title: "Interrupted Trash"\n'
        "trashed: false\n"
        "---\nBody\n"
    )
    p_trash = parse_markdown_note(md_in_trash, "99-Trash/interrupted.md", 1730712600.0)
    assert p_trash.metadata.trashed is True
    assert p_trash.had_parse_warning
    assert "folder state is authoritative" in (p_trash.parse_warning_message or "")

    # File in 10-Notes with trashed: true and original_rel_path -> forced to trashed=False, original_rel_path=None
    md_in_active = (
        "---\n"
        'id: "active-1"\n'
        'title: "Interrupted Restore"\n'
        "trashed: true\n"
        'original_rel_path: "10-Notes/interrupted.md"\n'
        "---\nBody\n"
    )
    p_active = parse_markdown_note(md_in_active, "10-Notes/interrupted.md", 1730712600.0)
    assert p_active.metadata.trashed is False
    assert p_active.metadata.original_rel_path is None
    assert p_active.had_parse_warning
    assert "folder state is authoritative" in (p_active.parse_warning_message or "")


def test_tag_and_domain_normalization_and_crlf_hashing() -> None:
    assert normalize_tags(["#WireGuard", "MTU Size", "wireguard", "linux_kernel!"]) == [
        "wireguard",
        "mtu-size",
        "linux-kernel",
    ]
    assert normalize_domains(["linux", "iot", "Unknown", "LINUX"]) == ["Linux", "IoT"]

    lf_text = "---\ntitle: Hash Test\n---\nLine 1\nLine 2\n"
    crlf_text = "---\r\ntitle: Hash Test\r\n---\r\nLine 1\r\nLine 2\r\n"
    assert len(compute_content_hash(lf_text)) == 64
    assert compute_content_hash(lf_text) == compute_content_hash(crlf_text)

    body = "# Heading 1\n\n```python\nprint('ignore code')\n```\n\nCheck [docs](https://example.com) for **details**.\n"
    assert extract_headings(body) == "Heading 1"
    assert extract_excerpt(body) == "Check docs for details."
    assert compute_word_stats("") == (0, 1)
    assert compute_word_stats(" ".join(["word"] * 250)) == (250, 2)
