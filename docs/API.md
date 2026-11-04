# DevJournal — REST API Specification

This document provides the complete API reference for **DevJournal** backend services (`/api/v1`).

---

## 1. General Conventions

- **Base URL**: All endpoints are prefixed with `/api/v1`.
- **Content Types**: Request bodies and responses are JSON (`application/json`) unless otherwise specified (e.g., file downloads use `text/markdown` or `application/zip`).
- **Date Format**: ISO-8601 UTC strings (`YYYY-MM-DDTHH:MM:SSZ`).
- **FastAPI Route Priority**: Static sub-routes (such as `POST /notes/daily/today`) are registered **before** parameterized routes (`GET /notes/{note_id}`) to prevent routing ambiguity.

---

## 2. Standard Error Format

DevJournal standardizes error responses using structured JSON envelopes:

```json
{
  "error": {
    "code": "CONFLICT_HASH_MISMATCH",
    "message": "Note has been modified on the server since it was loaded.",
    "details": {
      "current_hash": "a94f6c3...e1",
      "expected_hash": "71bc29a...0f"
    }
  }
}
```

### Common HTTP Status Codes
| Status Code | Code String | Description |
|---|---|---|
| `200 OK` | — | Request succeeded. |
| `201 Created` | — | Resource created successfully. |
| `400 Bad Request` | `INVALID_INPUT` / `PATH_TRAVERSAL` | Malformed parameter or unsafe file path. |
| `404 Not Found` | `NOTE_NOT_FOUND` | Requested note ID does not exist. |
| `409 Conflict` | `CONFLICT_HASH_MISMATCH` | Optimistic locking collision (`expected_hash` mismatch). |
| `422 Unprocessable Entity` | `VALIDATION_ERROR` | Pydantic model validation failure. |
| `500 Server Error` | `INTERNAL_ERROR` | Unhandled server exception. |

---

## 3. System & Settings Endpoints

### 3.1 Health Check
- **`GET /api/v1/system/health`**
- Returns backend operational status, directory writability, database connectivity, and active note count.

**Response (`200 OK`)**:
```json
{
  "status": "ok",
  "vault_writable": true,
  "db_ok": true,
  "indexed_notes": 42,
  "data_dir": "C:\\Users\\abbas\\Documents\\coding\\devjournal\\devjournal-data"
}
```

### 3.2 Rebuild Index
- **`POST /api/v1/system/reindex`**
- Rescans all `.md` files in the vault and reconstructs SQLite metadata and the FTS5 search index.

**Response (`200 OK`)**:
```json
{
  "status": "ok",
  "indexed": 42,
  "removed": 0,
  "duration_ms": 184
}
```

### 3.3 Create Backup
- **`POST /api/v1/system/backup`**
- Snapshots `devjournal.db` via SQLite hot backup and archives `vault/` into a timestamped `.zip` file.

**Response (`200 OK`)**:
```json
{
  "status": "ok",
  "filename": "devjournal-backup-20261104-120000.zip",
  "size_bytes": 1048576,
  "created_at": "2026-11-04T12:00:00Z"
}
```

### 3.4 Import Markdown File
- **`POST /api/v1/system/import-md`**
- Multipart form upload for a single `.md` file. Injects frontmatter if missing and indexes immediately.

**Form Parameters**:
- `file`: `UploadFile` (required, `.md` file)
- `folder`: `string` (optional, default: `00-Inbox`)

**Response (`201 Created`)**: Returns `NoteDetailResponse`.

### 3.5 Read Application Settings
- **`GET /api/v1/settings`**
- Returns stored editor preferences and UI settings from SQLite `settings`.

**Response (`200 OK`)**:
```json
{
  "default_editor_mode": "split",
  "editor_font_size": 14,
  "editor_word_wrap": true,
  "autosave_delay_ms": 1000,
  "updated_at": "2026-11-04T09:00:00Z"
}
```

### 3.6 Update Application Settings
- **`PUT /api/v1/settings`**
- Validates and persists editor preferences.

**Request Body**:
```json
{
  "default_editor_mode": "split",
  "editor_font_size": 15,
  "editor_word_wrap": true,
  "autosave_delay_ms": 1200
}
```

**Response (`200 OK`)**: Returns updated settings object.

---

## 4. Notes Endpoints

### 4.1 List Notes
- **`GET /api/v1/notes`**
- **Query Parameters**:
  - `type`: `string` (filter by `note`, `experiment`, `troubleshooting`, `project`, `daily`, `snippet`)
  - `domain`: `string` (filter by `Networking`, `Linux`, `Programming`, `IoT`, `Cybersecurity`, `Homelab`, `Mathematics`)
  - `tag`: `string` (filter by normalized tag slug)
  - `folder`: `string` (filter by folder path)
  - `status`: `string` (filter by `draft`, `active`, `investigating`, `resolved`, `completed`, `archived`)
  - `trashed`: `boolean` (default `false`)
  - `sort`: `updated_desc` | `created_desc` | `title_asc` (default `updated_desc`)
  - `limit`: `integer` (default `50`, max `200`)
  - `offset`: `integer` (default `0`)

**Response (`200 OK`)**:
```json
{
  "total": 1,
  "notes": [
    {
      "id": "018f4a7c-8d2b-7e10-9a3f-4b5c6d7e8f90",
      "title": "WireGuard MTU Troubleshooting",
      "slug": "wireguard-mtu-troubleshooting",
      "rel_path": "40-Troubleshooting/wireguard-mtu.md",
      "folder": "40-Troubleshooting",
      "note_type": "troubleshooting",
      "status": "resolved",
      "excerpt": "Diagnosing packet drops over site-to-site tunnel.",
      "word_count": 420,
      "reading_time_mins": 2,
      "content_hash": "a94f6c3b7829...",
      "is_pinned": true,
      "is_trashed": false,
      "domains": ["Networking", "Linux"],
      "tags": ["wireguard", "mtu"],
      "created_at": "2026-11-04T09:00:00Z",
      "updated_at": "2026-11-04T10:30:00Z",
      "last_opened_at": "2026-11-04T10:30:00Z"
    }
  ]
}
```

### 4.2 Create Note
- **`POST /api/v1/notes`**
- Creates a note from scratch or by instantiating a template. Atomically writes the `.md` file to disk and indexes in SQLite.

**Request Body**:
```json
{
  "title": "TCP BBR Congestion Control Benchmark",
  "note_type": "experiment",
  "status": "active",
  "domains": ["Networking", "Linux"],
  "tags": ["tcp", "bbr", "kernel"],
  "folder": "30-Experiments",
  "body": "## Objective\nMeasure throughput improvements with BBR v3...",
  "template_id": "experiment"
}
```

**Response (`201 Created`)**: Returns full `NoteDetailResponse`.

### 4.3 Get Note Detail
- **`GET /api/v1/notes/{note_id}`**
- Returns complete note metadata and Markdown body. Updates `last_opened_at` timestamp in SQLite unless `?record_open=false`.

**Response (`200 OK`)**:
```json
{
  "id": "018f4a7c-8d2b-7e10-9a3f-4b5c6d7e8f90",
  "title": "WireGuard MTU Troubleshooting",
  "slug": "wireguard-mtu-troubleshooting",
  "rel_path": "40-Troubleshooting/wireguard-mtu.md",
  "folder": "40-Troubleshooting",
  "note_type": "troubleshooting",
  "status": "resolved",
  "excerpt": "Diagnosing packet drops over site-to-site tunnel.",
  "word_count": 420,
  "reading_time_mins": 2,
  "content_hash": "a94f6c3b7829...",
  "is_pinned": true,
  "is_trashed": false,
  "domains": ["Networking", "Linux"],
  "tags": ["wireguard", "mtu"],
  "body": "## Problem\nSSH sessions stall during large transfers...",
  "created_at": "2026-11-04T09:00:00Z",
  "updated_at": "2026-11-04T10:30:00Z",
  "last_opened_at": "2026-11-04T10:30:00Z"
}
```

### 4.4 Save Full Note (Editor Save / Autosave)
- **`PUT /api/v1/notes/{note_id}`**
- Atomically replaces file content on disk and updates SQLite index. Supports optimistic concurrency via `expected_hash`.

**Request Body**:
```json
{
  "title": "WireGuard MTU Troubleshooting",
  "note_type": "troubleshooting",
  "status": "resolved",
  "domains": ["Networking", "Linux", "Homelab"],
  "tags": ["wireguard", "mtu", "proxmox"],
  "is_pinned": true,
  "body": "## Problem\nUpdated problem description...",
  "expected_hash": "a94f6c3b7829...",
  "force": false
}
```

**Response (`200 OK`)**: Returns updated `NoteDetailResponse` with fresh `content_hash`.  
*If `expected_hash` does not match the file on disk and `force=false`, returns `409 Conflict`.*

### 4.5 Partial Metadata Update (Pin / Status / Domains)
- **`PATCH /api/v1/notes/{note_id}`**
- Updates frontmatter metadata without re-transmitting the note body.

**Request Body**:
```json
{
  "is_pinned": true,
  "status": "completed"
}
```

**Response (`200 OK`)**: Returns updated `NoteDetailResponse`.

### 4.6 Soft Delete to Trash
- **`DELETE /api/v1/notes/{note_id}`**
- Moves file to `vault/99-Trash/` and sets `is_trashed = 1`. To permanently unlink file, pass `?permanent=true`.

**Response (`200 OK`)**:
```json
{
  "status": "ok",
  "deleted_id": "018f4a7c-8d2b-7e10-9a3f-4b5c6d7e8f90",
  "permanent": false
}
```

### 4.7 Restore Note from Trash
- **`POST /api/v1/notes/{note_id}/restore`**
- Moves file from `99-Trash/` back to its original path and sets `is_trashed = 0`.

**Response (`200 OK`)**: Returns restored `NoteDetailResponse`.

### 4.8 Open or Create Today's Daily Journal
- **`POST /api/v1/notes/daily/today`**
- Idempotently retrieves or creates `vault/90-Daily/YYYY-MM-DD.md` using the Daily template.

**Response (`200 OK` or `201 Created`)**: Returns `NoteDetailResponse`.

### 4.9 Raw Markdown Export
- **`GET /api/v1/notes/{note_id}/export`**
- Downloads the raw `.md` file with header: `Content-Disposition: attachment; filename="<slug>.md"`.

---

## 5. Discovery & Aggregation Endpoints

### 5.1 Dashboard Data
- **`GET /api/v1/dashboard`**
- Returns real SQLite-backed statistics for the Overview page.

**Response (`200 OK`)**:
```json
{
  "counts": {
    "total_notes": 42,
    "experiments": 8,
    "troubleshooting": 12,
    "projects": 5,
    "daily": 14,
    "snippets": 3
  },
  "domain_counts": {
    "Networking": 15,
    "Linux": 22,
    "Programming": 18,
    "IoT": 4,
    "Cybersecurity": 9,
    "Homelab": 14,
    "Mathematics": 3
  },
  "recently_opened": [ /* 5 NoteSummary objects */ ],
  "recently_updated": [ /* 5 NoteSummary objects */ ]
}
```

### 5.2 Taxonomy Counts
- **`GET /api/v1/taxonomy`**
- Returns note counts for sidebar badges and filter dropdowns.

**Response (`200 OK`)**:
```json
{
  "types": { "note": 10, "experiment": 8, "troubleshooting": 12, "project": 5, "daily": 14, "snippet": 3 },
  "domains": { "Networking": 15, "Linux": 22, "Programming": 18, "IoT": 4, "Cybersecurity": 9, "Homelab": 14, "Mathematics": 3 },
  "tags": { "wireguard": 4, "kernel": 6, "docker": 11 },
  "folders": { "10-Notes": 10, "20-Projects": 5, "30-Experiments": 8, "40-Troubleshooting": 12, "90-Daily": 14 },
  "total_active": 42,
  "total_trashed": 2
}
```

### 5.3 Full-Text Search
- **`GET /api/v1/search?q=<query>&type=<type>&domain=<domain>&tag=<tag>&limit=25`**
- Queries SQLite FTS5 with BM25 ranking and `<mark>` highlights.

**Response (`200 OK`)**:
```json
{
  "query": "mtu wireguard",
  "total_matches": 1,
  "results": [
    {
      "id": "018f4a7c-8d2b-7e10-9a3f-4b5c6d7e8f90",
      "title": "WireGuard MTU Troubleshooting",
      "slug": "wireguard-mtu-troubleshooting",
      "rel_path": "40-Troubleshooting/wireguard-mtu.md",
      "note_type": "troubleshooting",
      "status": "resolved",
      "domains": ["Networking", "Linux"],
      "tags": ["wireguard", "mtu"],
      "updated_at": "2026-11-04T10:30:00Z",
      "snippet": "...diagnosing packet drops over <mark>wireguard</mark> tunnel due to mismatch in <mark>mtu</mark> size...",
      "score": -14.28
    }
  ]
}
```

### 5.4 Templates Catalog
- **`GET /api/v1/templates`**
- Returns the 5 built-in note creation templates.

**Response (`200 OK`)**:
```json
{
  "templates": [
    { "id": "general", "name": "General Note", "note_type": "note", "folder": "10-Notes", "body": "## Overview\n..." },
    { "id": "experiment", "name": "Experiment", "note_type": "experiment", "folder": "30-Experiments", "body": "## Objective\n..." },
    { "id": "troubleshooting", "name": "Troubleshooting", "note_type": "troubleshooting", "folder": "40-Troubleshooting", "body": "## Problem\n..." },
    { "id": "project", "name": "Project", "note_type": "project", "folder": "20-Projects", "body": "## Project Overview\n..." },
    { "id": "daily", "name": "Daily Journal", "note_type": "daily", "folder": "90-Daily", "body": "## Daily Learning\n..." }
  ]
}
```
