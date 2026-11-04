from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from app.models.api_models import AppSettingsResponse, UpdateSettingsRequest

CANONICAL_SETTINGS_KEY = "editor_preferences"
LEGACY_SETTINGS_KEYS: tuple[str, str] = ("app_preferences", "app_settings")


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SettingsRepository:
    """SQLite repository for editor preferences with legacy key migration."""

    def get_settings(self, conn: sqlite3.Connection) -> AppSettingsResponse:
        row = conn.execute(
            "SELECT value_json, updated_at FROM settings WHERE key = ?",
            (CANONICAL_SETTINGS_KEY,),
        ).fetchone()

        if row is None:
            row = conn.execute(
                """
                SELECT value_json, updated_at
                FROM settings
                WHERE key IN (?, ?)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                LEGACY_SETTINGS_KEYS,
            ).fetchone()

        if row is not None:
            try:
                parsed = json.loads(row["value_json"])
                if isinstance(parsed, dict):
                    validated = UpdateSettingsRequest(**parsed)
                    return AppSettingsResponse(
                        default_editor_mode=validated.default_editor_mode,
                        editor_font_size=validated.editor_font_size,
                        editor_word_wrap=validated.editor_word_wrap,
                        autosave_delay_ms=validated.autosave_delay_ms,
                        updated_at=row["updated_at"] or _now_utc_iso(),
                    )
            except Exception:
                pass

        return AppSettingsResponse(
            default_editor_mode="split",
            editor_font_size=14,
            editor_word_wrap=True,
            autosave_delay_ms=1000,
            updated_at=_now_utc_iso(),
        )

    def update_settings(
        self, conn: sqlite3.Connection, req: UpdateSettingsRequest
    ) -> AppSettingsResponse:
        now_iso = _now_utc_iso()
        payload_json = json.dumps(
            {
                "default_editor_mode": req.default_editor_mode,
                "editor_font_size": req.editor_font_size,
                "editor_word_wrap": req.editor_word_wrap,
                "autosave_delay_ms": req.autosave_delay_ms,
            }
        )
        conn.execute(
            """
            INSERT INTO settings (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (CANONICAL_SETTINGS_KEY, payload_json, now_iso),
        )
        conn.execute(
            "DELETE FROM settings WHERE key IN (?, ?)",
            LEGACY_SETTINGS_KEYS,
        )
        return AppSettingsResponse(
            default_editor_mode=req.default_editor_mode,
            editor_font_size=req.editor_font_size,
            editor_word_wrap=req.editor_word_wrap,
            autosave_delay_ms=req.autosave_delay_ms,
            updated_at=now_iso,
        )
