CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    rel_path TEXT NOT NULL UNIQUE,
    folder TEXT NOT NULL,
    note_type TEXT NOT NULL DEFAULT 'note',
    status TEXT,
    excerpt TEXT NOT NULL DEFAULT '',
    word_count INTEGER NOT NULL DEFAULT 0,
    reading_time_mins INTEGER NOT NULL DEFAULT 1,
    content_hash TEXT NOT NULL,
    file_mtime REAL NOT NULL,
    is_pinned INTEGER NOT NULL DEFAULT 0,
    is_trashed INTEGER NOT NULL DEFAULT 0,
    original_rel_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_opened_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_notes_type_trashed ON notes(note_type, is_trashed, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_notes_folder_trashed ON notes(folder, is_trashed);
CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(is_trashed, is_pinned DESC, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_notes_last_opened ON notes(last_opened_at DESC) WHERE is_trashed = 0 AND last_opened_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS note_domains (
    note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    domain TEXT NOT NULL,
    PRIMARY KEY (note_id, domain)
);
CREATE INDEX IF NOT EXISTS idx_note_domains_domain ON note_domains(domain, note_id);

CREATE TABLE IF NOT EXISTS note_tags (
    note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (note_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_note_tags_tag ON note_tags(tag, note_id);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    note_id UNINDEXED,
    title,
    headings,
    body,
    tags_text,
    domains_text,
    tokenize = 'porter unicode61 remove_diacritics 2'
);
