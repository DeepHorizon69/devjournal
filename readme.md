# DevJournal

> **Your Personal Engineering Knowledge Base**

DevJournal is a self-hosted, local-first, Markdown-centric engineering knowledge management web application. It is purpose-built for software and infrastructure engineers to document technical learning, benchmarks and experiments, troubleshooting investigations, homelab projects, daily journal entries, and reusable code snippets.

---

## Key Features

- **Markdown-First Canonical Storage**: Plain `.md` files on the server disk are the authoritative source of truth. Notes remain 100% portable, human-readable, and editable in any text editor.
- **Derived SQLite + FTS5 Index**: Fast full-text search and metadata queries stored in a rebuildable SQLite database (`devjournal.db`) with BM25 relevance ranking.
- **Documentation-Grade Reading & Editing**: Dark graphite/navy aesthetic (`#0B0F17`) with sky-blue accents (`#38BDF8`), clean typography, and a split-view Markdown editing experience powered by CodeMirror 6.
- **Orthogonal Classification**: Workspace sections (`All Notes`, `Experiments`, `Troubleshooting`, `Projects`, `Daily Journal`) categorize workflow types, while 7 Knowledge Domains (`Networking`, `Linux`, `Programming`, `IoT`, `Cybersecurity`, `Homelab`, `Mathematics`) organize subject matter without duplicating files.
- **Zero Cloud Lock-In**: Complete data sovereignty on user-controlled hardware (local PC, homelab server, or cloud-hosted VM with persistent disk).

---

## Documentation Suite

Detailed technical documentation is available in the [`docs/`](./docs) directory:

- [**System Architecture (`docs/ARCHITECTURE.md`)**](./docs/ARCHITECTURE.md): System topology, component responsibilities, Write-Then-Index synchronization contract, and crash recovery.
- [**Database & Storage Design (`docs/DATABASE.md`)**](./docs/DATABASE.md): SQLite schema DDL, ER diagram, indexing strategy, FTS5 BM25 ranking, and reindexing protocols.
- [**REST API Specification (`docs/API.md`)**](./docs/API.md): Complete `/api/v1` endpoint catalog, request/response models, error handling, and example payloads.
- [**UI/UX Design System (`docs/UI_UX.md`)**](./docs/UI_UX.md): Visual direction, 4px spacing system, 20-component inventory, screen specifications, and keyboard shortcuts.
- [**Development Guide (`docs/DEVELOPMENT.md`)**](./docs/DEVELOPMENT.md): Local environment setup, project structure, coding conventions, and testing procedures.
- [**Deployment & Operations (`docs/DEPLOYMENT.md`)**](./docs/DEPLOYMENT.md): Docker Compose instructions, persistent storage, backup/restore runbook, and security best practices.

---

## Quickstart & Local Launch

### Option 1: Unified Launch (FastAPI + Built SPA)
The FastAPI server serves both the REST API and the compiled React SPA on port `8000`:

```powershell
# Windows PowerShell:
.\backend\.venv\Scripts\uvicorn app.main:app --app-dir backend --port 8000
```

Open your browser to: **[http://localhost:8000](http://localhost:8000)**

---

### Option 2: Active Development Mode (Hot Reload)

#### Terminal 1 — Backend API
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

#### Terminal 2 — Frontend (Vite)
```powershell
cd frontend
npm run dev
```

Open your browser to: **[http://localhost:5173](http://localhost:5173)** *(Vite proxies `/api` calls to port 8000)*

---

### Running Automated Tests

```bash
# Backend pytest suite:
cd backend
.\.venv\Scripts\pytest -v

# Frontend Vitest suite:
cd frontend
npm run test

# Production build verification:
npm run build
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl + \` | Toggle sidebar (collapse to 60px icon rail / expand to 240px) |
| `Ctrl + K` | Open global Quick Search palette |
| `Alt + N` | Trigger New Note creation modal |
| `Ctrl + S` | Save active note immediately in editor |
| `Esc` | Dismiss modals, popovers, or mobile navigation drawer |

---

## License

Personal Engineering Knowledge Base — MIT License.
