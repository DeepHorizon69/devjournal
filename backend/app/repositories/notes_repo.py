from __future__ import annotations

import sqlite3
from typing import Any

from app.models.note import VALID_DOMAINS, NoteRecord, ParsedNote


class NotesRepository:
    """Explicit parameterized SQLite repository for notes, taxonomy junctions, and FTS5."""

    def upsert_parsed_note(
        self,
        conn: sqlite3.Connection,
        parsed: ParsedNote,
        preserved_last_opened_at: str | None = None,
    ) -> None:
        """Upsert a ParsedNote into notes, replace note_domains/note_tags, and refresh notes_fts."""
        note_id = parsed.metadata.id

        # If a different note ID currently occupies parsed.rel_path, remove that stale row first
        existing_at_path = conn.execute(
            "SELECT id, last_opened_at FROM notes WHERE rel_path = ?",
            (parsed.rel_path,),
        ).fetchone()
        path_last_opened: str | None = None
        if existing_at_path is not None and existing_at_path["id"] != note_id:
            stale_path_id = existing_at_path["id"]
            path_last_opened = existing_at_path["last_opened_at"]
            conn.execute("DELETE FROM notes_fts WHERE note_id = ?", (stale_path_id,))
            conn.execute("DELETE FROM notes WHERE id = ?", (stale_path_id,))

        if preserved_last_opened_at is None:
            existing_by_id = conn.execute(
                "SELECT last_opened_at FROM notes WHERE id = ?",
                (note_id,),
            ).fetchone()
            if existing_by_id is not None and existing_by_id["last_opened_at"] is not None:
                preserved_last_opened_at = existing_by_id["last_opened_at"]
            elif path_last_opened is not None:
                preserved_last_opened_at = path_last_opened

        conn.execute(
            """
            INSERT INTO notes (
                id, title, slug, rel_path, folder, note_type, status,
                excerpt, word_count, reading_time_mins, content_hash,
                file_mtime, is_pinned, is_trashed, original_rel_path,
                created_at, updated_at, last_opened_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                slug = excluded.slug,
                rel_path = excluded.rel_path,
                folder = excluded.folder,
                note_type = excluded.note_type,
                status = excluded.status,
                excerpt = excluded.excerpt,
                word_count = excluded.word_count,
                reading_time_mins = excluded.reading_time_mins,
                content_hash = excluded.content_hash,
                file_mtime = excluded.file_mtime,
                is_pinned = excluded.is_pinned,
                is_trashed = excluded.is_trashed,
                original_rel_path = excluded.original_rel_path,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                last_opened_at = COALESCE(excluded.last_opened_at, notes.last_opened_at)
            """,
            (
                note_id,
                parsed.metadata.title,
                parsed.slug,
                parsed.rel_path,
                parsed.folder,
                parsed.metadata.type,
                parsed.metadata.status,
                parsed.excerpt,
                parsed.word_count,
                parsed.reading_time_mins,
                parsed.content_hash,
                parsed.file_mtime,
                1 if parsed.metadata.pinned else 0,
                1 if parsed.metadata.trashed else 0,
                parsed.metadata.original_rel_path,
                parsed.metadata.created_at,
                parsed.metadata.updated_at,
                preserved_last_opened_at,
            ),
        )

        # Replace note_domains
        conn.execute("DELETE FROM note_domains WHERE note_id = ?", (note_id,))
        if parsed.metadata.domains:
            conn.executemany(
                "INSERT INTO note_domains (note_id, domain) VALUES (?, ?)",
                [(note_id, domain) for domain in parsed.metadata.domains],
            )

        # Replace note_tags
        conn.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
        if parsed.metadata.tags:
            conn.executemany(
                "INSERT INTO note_tags (note_id, tag) VALUES (?, ?)",
                [(note_id, tag) for tag in parsed.metadata.tags],
            )

        # Refresh FTS5 entry
        conn.execute("DELETE FROM notes_fts WHERE note_id = ?", (note_id,))
        conn.execute(
            """
            INSERT INTO notes_fts (note_id, title, headings, body, tags_text, domains_text)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                note_id,
                parsed.metadata.title,
                parsed.headings,
                parsed.body,
                " ".join(parsed.metadata.tags),
                " ".join(parsed.metadata.domains),
            ),
        )

    def update_file_mtime(
        self,
        conn: sqlite3.Connection,
        note_id: str,
        rel_path: str,
        file_mtime: float,
    ) -> None:
        """Update only file_mtime when SHA-256 content_hash is unchanged."""
        conn.execute(
            "UPDATE notes SET file_mtime = ? WHERE id = ? AND rel_path = ?",
            (file_mtime, note_id, rel_path),
        )

    def touch_last_opened(
        self,
        conn: sqlite3.Connection,
        note_id: str,
        opened_at: str,
    ) -> None:
        """Update last_opened_at timestamp for a note."""
        conn.execute(
            "UPDATE notes SET last_opened_at = ? WHERE id = ?",
            (opened_at, note_id),
        )

    def delete_stale_note(
        self,
        conn: sqlite3.Connection,
        note_id: str,
        expected_rel_path: str,
    ) -> bool:
        """Delete a stale note only if it still points to expected_rel_path (rename-safe)."""
        cursor = conn.execute(
            "DELETE FROM notes WHERE id = ? AND rel_path = ?",
            (note_id, expected_rel_path),
        )
        if cursor.rowcount > 0:
            conn.execute("DELETE FROM notes_fts WHERE note_id = ?", (note_id,))
            return True
        return False

    def delete_note_by_id(self, conn: sqlite3.Connection, note_id: str) -> bool:
        """Delete a note and its FTS5 row by note_id."""
        cursor = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        if cursor.rowcount > 0:
            conn.execute("DELETE FROM notes_fts WHERE note_id = ?", (note_id,))
            return True
        return False

    def get_index_manifest(
        self, conn: sqlite3.Connection
    ) -> dict[str, dict[str, Any]]:
        """Return a snapshot mapping rel_path -> {id, rel_path, file_mtime, content_hash, last_opened_at}."""
        rows = conn.execute(
            "SELECT id, rel_path, file_mtime, content_hash, last_opened_at FROM notes"
        ).fetchall()
        return {
            row["rel_path"]: {
                "id": row["id"],
                "rel_path": row["rel_path"],
                "file_mtime": float(row["file_mtime"]),
                "content_hash": row["content_hash"],
                "last_opened_at": row["last_opened_at"],
            }
            for row in rows
        }

    def _hydrate_rows(
        self, conn: sqlite3.Connection, rows: list[sqlite3.Row]
    ) -> list[NoteRecord]:
        """Batch-hydrate domains and tags for a list of SQLite note rows."""
        if not rows:
            return []

        note_ids = [row["id"] for row in rows]
        placeholders = ",".join("?" for _ in note_ids)

        domains_by_id: dict[str, list[str]] = {nid: [] for nid in note_ids}
        domain_rows = conn.execute(
            f"SELECT note_id, domain FROM note_domains WHERE note_id IN ({placeholders}) ORDER BY rowid ASC",
            note_ids,
        ).fetchall()
        for r in domain_rows:
            domains_by_id[r["note_id"]].append(r["domain"])

        tags_by_id: dict[str, list[str]] = {nid: [] for nid in note_ids}
        tag_rows = conn.execute(
            f"SELECT note_id, tag FROM note_tags WHERE note_id IN ({placeholders}) ORDER BY rowid ASC",
            note_ids,
        ).fetchall()
        for r in tag_rows:
            tags_by_id[r["note_id"]].append(r["tag"])

        return [
            NoteRecord(
                id=row["id"],
                title=row["title"],
                slug=row["slug"],
                rel_path=row["rel_path"],
                folder=row["folder"],
                note_type=row["note_type"],
                status=row["status"],
                excerpt=row["excerpt"],
                word_count=int(row["word_count"]),
                reading_time_mins=int(row["reading_time_mins"]),
                content_hash=row["content_hash"],
                file_mtime=float(row["file_mtime"]),
                is_pinned=bool(row["is_pinned"]),
                is_trashed=bool(row["is_trashed"]),
                original_rel_path=row["original_rel_path"],
                domains=domains_by_id.get(row["id"], []),
                tags=tags_by_id.get(row["id"], []),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                last_opened_at=row["last_opened_at"],
            )
            for row in rows
        ]

    def get_note_by_id(
        self, conn: sqlite3.Connection, note_id: str
    ) -> NoteRecord | None:
        """Fetch a full NoteRecord (including domains and tags) by note ID."""
        row = conn.execute(
            "SELECT * FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        if row is None:
            return None
        return self._hydrate_rows(conn, [row])[0]

    def get_note_by_rel_path(
        self, conn: sqlite3.Connection, rel_path: str
    ) -> NoteRecord | None:
        """Fetch a full NoteRecord by its vault-relative POSIX path."""
        row = conn.execute(
            "SELECT * FROM notes WHERE rel_path = ?", (rel_path,)
        ).fetchone()
        if row is None:
            return None
        return self._hydrate_rows(conn, [row])[0]

    def list_notes(
        self,
        conn: sqlite3.Connection,
        *,
        note_type: str | None = None,
        domain: str | None = None,
        tag: str | None = None,
        folder: str | None = None,
        status: str | None = None,
        trashed: bool = False,
        sort: str = "updated_desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[NoteRecord]]:
        """Query filtered, sorted, paginated notes with total match count."""
        clauses: list[str] = ["n.is_trashed = ?"]
        params: list[Any] = [1 if trashed else 0]

        if note_type:
            clauses.append("n.note_type = ?")
            params.append(note_type)
        if folder:
            clauses.append("n.folder = ?")
            params.append(folder)
        if status:
            clauses.append("n.status = ?")
            params.append(status)
        if domain:
            clauses.append(
                "EXISTS (SELECT 1 FROM note_domains nd WHERE nd.note_id = n.id AND nd.domain = ?)"
            )
            params.append(domain)
        if tag:
            clauses.append(
                "EXISTS (SELECT 1 FROM note_tags nt WHERE nt.note_id = n.id AND nt.tag = ?)"
            )
            params.append(tag)

        where_sql = " AND ".join(clauses)

        count_row = conn.execute(
            f"SELECT count(*) AS cnt FROM notes n WHERE {where_sql}",
            params,
        ).fetchone()
        total = int(count_row["cnt"]) if count_row is not None else 0

        if sort == "created_desc":
            order_sql = "n.is_pinned DESC, n.created_at DESC, n.id ASC"
        elif sort == "title_asc":
            order_sql = "n.is_pinned DESC, LOWER(n.title) ASC, n.id ASC"
        else:
            order_sql = "n.is_pinned DESC, n.updated_at DESC, n.id ASC"

        rows = conn.execute(
            f"""
            SELECT n.*
            FROM notes n
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

        return total, self._hydrate_rows(conn, rows)

    def list_all_trashed_notes(self, conn: sqlite3.Connection) -> list[NoteRecord]:
        """Return all trashed notes without pagination limit (for Empty Trash)."""
        rows = conn.execute(
            "SELECT * FROM notes WHERE is_trashed = 1 ORDER BY updated_at DESC"
        ).fetchall()
        return self._hydrate_rows(conn, rows)

    def count_active_notes(self, conn: sqlite3.Connection) -> int:
        """Return count of non-trashed notes in SQLite."""
        row = conn.execute(
            "SELECT count(*) AS cnt FROM notes WHERE is_trashed = 0"
        ).fetchone()
        return int(row["cnt"]) if row is not None else 0

    def get_taxonomy_counts(self, conn: sqlite3.Connection) -> dict[str, Any]:
        """Compute active note counts by type, domain, tag, folder, and total active/trashed."""
        types_map: dict[str, int] = {
            "note": 0,
            "experiment": 0,
            "troubleshooting": 0,
            "project": 0,
            "daily": 0,
            "snippet": 0,
        }
        for row in conn.execute(
            "SELECT note_type, count(*) AS cnt FROM notes WHERE is_trashed = 0 GROUP BY note_type"
        ).fetchall():
            types_map[row["note_type"]] = int(row["cnt"])

        domains_map: dict[str, int] = {d: 0 for d in VALID_DOMAINS.values()}
        for row in conn.execute(
            """
            SELECT nd.domain, count(*) AS cnt
            FROM note_domains nd
            JOIN notes n ON n.id = nd.note_id
            WHERE n.is_trashed = 0
            GROUP BY nd.domain
            """
        ).fetchall():
            domains_map[row["domain"]] = int(row["cnt"])

        tags_map: dict[str, int] = {}
        for row in conn.execute(
            """
            SELECT nt.tag, count(*) AS cnt
            FROM note_tags nt
            JOIN notes n ON n.id = nt.note_id
            WHERE n.is_trashed = 0
            GROUP BY nt.tag
            ORDER BY cnt DESC, nt.tag ASC
            """
        ).fetchall():
            tags_map[row["tag"]] = int(row["cnt"])

        folders_map: dict[str, int] = {
            "00-Inbox": 0,
            "10-Notes": 0,
            "20-Projects": 0,
            "30-Experiments": 0,
            "40-Troubleshooting": 0,
            "50-Snippets": 0,
            "90-Daily": 0,
        }
        for row in conn.execute(
            "SELECT folder, count(*) AS cnt FROM notes WHERE is_trashed = 0 GROUP BY folder"
        ).fetchall():
            folders_map[row["folder"]] = int(row["cnt"])

        total_active = self.count_active_notes(conn)
        trashed_row = conn.execute(
            "SELECT count(*) AS cnt FROM notes WHERE is_trashed = 1"
        ).fetchone()
        total_trashed = int(trashed_row["cnt"]) if trashed_row is not None else 0

        return {
            "types": types_map,
            "domains": domains_map,
            "tags": tags_map,
            "folders": folders_map,
            "total_active": total_active,
            "total_trashed": total_trashed,
        }

    def get_dashboard_data(self, conn: sqlite3.Connection) -> dict[str, Any]:
        """Aggregate Overview dashboard counts, domain counts, recently opened, and recently updated notes."""
        tax = self.get_taxonomy_counts(conn)
        types_map = tax["types"]

        counts = {
            "total_notes": tax["total_active"],
            "experiments": types_map.get("experiment", 0),
            "troubleshooting": types_map.get("troubleshooting", 0),
            "projects": types_map.get("project", 0),
            "daily": types_map.get("daily", 0),
            "snippets": types_map.get("snippet", 0),
        }

        opened_rows = conn.execute(
            """
            SELECT * FROM notes
            WHERE is_trashed = 0 AND last_opened_at IS NOT NULL
            ORDER BY last_opened_at DESC, updated_at DESC
            LIMIT 5
            """
        ).fetchall()

        updated_rows = conn.execute(
            """
            SELECT * FROM notes
            WHERE is_trashed = 0
            ORDER BY updated_at DESC, id ASC
            LIMIT 5
            """
        ).fetchall()

        return {
            "counts": counts,
            "domain_counts": tax["domains"],
            "recently_opened": self._hydrate_rows(conn, opened_rows),
            "recently_updated": self._hydrate_rows(conn, updated_rows),
        }
