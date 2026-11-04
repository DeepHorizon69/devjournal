from __future__ import annotations

import html
import re
import uuid
from pathlib import Path
from typing import Any

from app.config import settings
from app.db.connection import get_db_connection
from app.models.api_models import SearchResponse, SearchResultItem, SnippetSegment
from app.models.note import VALID_DOMAINS
from app.repositories.notes_repo import NotesRepository
from app.services.frontmatter_svc import normalize_tags
from app.services.vault_storage import VaultStorageService

_SEARCH_TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)


def build_safe_fts5_query(raw_query: str) -> str:
    """Sanitize user search input into a safe FTS5 MATCH expression immune to syntax errors."""
    tokens = _SEARCH_TOKEN_RE.findall(raw_query or "")
    if not tokens:
        return ""
    # Quote each token and enable prefix matching so FTS5 operators (AND/OR/NOT/NEAR) or punctuation never error
    return " ".join(f'"{tok}"*' for tok in tokens[:24])


def parse_nonce_snippet(
    raw_snippet: str, open_marker: str, close_marker: str
) -> tuple[str, list[SnippetSegment]]:
    """Split an FTS5 snippet marked with per-query collision-resistant nonce markers into safe segments."""
    if not raw_snippet:
        return "", []

    pattern = re.compile(
        f"({re.escape(open_marker)}.*?{re.escape(close_marker)})",
        flags=re.DOTALL,
    )
    parts = pattern.split(raw_snippet)
    segments: list[SnippetSegment] = []
    rendered_parts: list[str] = []

    open_len = len(open_marker)
    close_len = len(close_marker)

    for part in parts:
        if not part:
            continue
        if part.startswith(open_marker) and part.endswith(close_marker):
            inner = part[open_len : len(part) - close_len]
            if inner:
                segments.append(SnippetSegment(text=inner, highlight=True))
                rendered_parts.append(f"<mark>{html.escape(inner, quote=False)}</mark>")
        else:
            segments.append(SnippetSegment(text=part, highlight=False))
            rendered_parts.append(html.escape(part, quote=False))

    return "".join(rendered_parts), segments


class SearchService:
    """Executes BM25-ranked FTS5 full-text search with collision-resistant per-query nonce markers."""

    def __init__(
        self,
        vault_storage: VaultStorageService | None = None,
        repo: NotesRepository | None = None,
        db_path: Path | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path is not None else settings.db_path
        self.vault_storage = vault_storage or VaultStorageService(
            settings.vault_dir, db_path=self.db_path
        )
        self.repo = repo or NotesRepository()

    def search(
        self,
        query: str,
        *,
        note_type: str | None = None,
        domain: str | None = None,
        tag: str | None = None,
        folder: str | None = None,
        status: str | None = None,
        trashed: bool = False,
        limit: int = 25,
    ) -> SearchResponse:
        if self.vault_storage.has_pending_move_journal():
            self.vault_storage.recover_interrupted_moves(db_path=self.db_path)

        clean_query = (query or "").strip()
        fts_expr = build_safe_fts5_query(clean_query)
        if not fts_expr:
            return SearchResponse(query=clean_query, total_matches=0, results=[])

        nonce = uuid.uuid4().hex
        open_marker = f"\x01DJ_OPEN_{nonce}\x01"
        close_marker = f"\x01DJ_CLOSE_{nonce}\x01"

        clauses: list[str] = ["notes_fts MATCH ?", "n.is_trashed = ?"]
        filter_params: list[Any] = [fts_expr, 1 if trashed else 0]

        if note_type:
            clauses.append("n.note_type = ?")
            filter_params.append(note_type)
        if folder:
            clauses.append("n.folder = ?")
            filter_params.append(folder)
        if status:
            clauses.append("n.status = ?")
            filter_params.append(status)
        if domain:
            canonical_domain = VALID_DOMAINS.get(domain.strip().lower(), domain.strip())
            clauses.append(
                "EXISTS (SELECT 1 FROM note_domains nd WHERE nd.note_id = n.id AND nd.domain = ?)"
            )
            filter_params.append(canonical_domain)
        if tag:
            norm_tags = normalize_tags([tag])
            normalized_tag = norm_tags[0] if norm_tags else tag.strip().lower()
            clauses.append(
                "EXISTS (SELECT 1 FROM note_tags nt WHERE nt.note_id = n.id AND nt.tag = ?)"
            )
            filter_params.append(normalized_tag)

        where_sql = " AND ".join(clauses)

        with get_db_connection(self.db_path) as conn:
            count_row = conn.execute(
                f"""
                SELECT count(*) AS cnt
                FROM notes_fts
                JOIN notes n ON n.id = notes_fts.note_id
                WHERE {where_sql}
                """,
                filter_params,
            ).fetchall()
            total_matches = int(count_row[0]["cnt"]) if count_row else 0

            rows = conn.execute(
                f"""
                SELECT
                    n.*,
                    snippet(notes_fts, -1, ?, ?, '...', 32) AS raw_snippet,
                    bm25(notes_fts, 10.0, 5.0, 1.0, 4.0, 2.0) AS score
                FROM notes_fts
                JOIN notes n ON n.id = notes_fts.note_id
                WHERE {where_sql}
                ORDER BY score ASC, n.updated_at DESC
                LIMIT ?
                """,
                [open_marker, close_marker, *filter_params, limit],
            ).fetchall()

            hydrated = self.repo._hydrate_rows(conn, rows)

        results: list[SearchResultItem] = []
        for row, rec in zip(rows, hydrated):
            raw_snip = row["raw_snippet"] or rec.excerpt or ""
            safe_snippet, segments = parse_nonce_snippet(
                raw_snip, open_marker, close_marker
            )
            results.append(
                SearchResultItem(
                    id=rec.id,
                    title=rec.title,
                    slug=rec.slug,
                    rel_path=rec.rel_path,
                    folder=rec.folder,
                    note_type=rec.note_type,
                    status=rec.status,
                    domains=list(rec.domains),
                    tags=list(rec.tags),
                    updated_at=rec.updated_at,
                    snippet=safe_snippet,
                    snippet_segments=segments,
                    score=round(float(row["score"]), 4),
                )
            )

        return SearchResponse(
            query=clean_query,
            total_matches=total_matches,
            results=results,
        )
