# DevJournal

> **Your Personal Engineering Knowledge Base**

DevJournal is a self-hosted, local-first, Markdown-centric engineering knowledge management web application. It is purpose-built for engineers to document technical learning, benchmarks and experiments, troubleshooting investigations, software and homelab projects, daily journal entries, and reusable snippets.

---

## Architecture Highlights

- **Markdown-First Canonical Storage**: Plain `.md` files on the server disk are the authoritative source of truth. Notes remain 100% portable, human-readable, and editable in any text editor.
- **Derived SQLite + FTS5 Index**: Fast full-text search and metadata queries stored in a rebuildable SQLite database (`devjournal.db`).
- **Technical Documentation Reading Experience**: Dark graphite/navy aesthetic (`#0B0F17`) with sky-blue accents (`#38BDF8`), clean typography, and a split-view Markdown editing experience powered by CodeMirror 6.
- **Orthogonal Classification**: Workspace sections (`All Notes`, `Experiments`, `Troubleshooting`, `Projects`, `Daily Journal`) categorize workflow types, while 7 Knowledge Domains (`Networking`, `Linux`, `Programming`, `IoT`, `Cybersecurity`, `Homelab`, `Mathematics`) organize subject matter without duplicating files.

---

## Project Structure

```text
devjournal/
├── backend/                  # Python 3.12+ FastAPI API server
│   ├── app/
│   │   ├── api/v1/           # REST endpoints (/system/health, /notes, /search, etc.)
│   │   ├── config.py         # Pydantic BaseSettings
│   │   └── main.py           # FastAPI app & SPA static file server
│   ├── tests/                # Pytest test suite
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/                 # React 18 + TypeScript + Vite + Tailwind CSS
│   ├── src/
│   │   ├── components/       # Layout, Navigation, Editor, UI primitives
│   │   ├── pages/            # Overview, Notes, Daily, Editor, Search, Settings
│   │   ├── store/            # Zustand UI state
│   │   └── types/            # TypeScript domain interfaces
│   ├── package.json
│   └── vite.config.ts
├── devjournal-data/          # Persistent data directory (gitignored)
│   ├── vault/                # Markdown notes hierarchy (00-Inbox to 99-Trash)
│   └── devjournal.db         # Derived SQLite metadata & FTS5 search index
└── README.md
```

---

## Local Development Setup

### 1. Backend (FastAPI)

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000
```

Verify backend health at `http://127.0.0.1:8000/api/v1/system/health`.

### 2. Frontend (React + Vite)

```bash
cd frontend

# Install dependencies
npm install

# Run Vite dev server with proxy to backend
npm run dev
```

Open `http://localhost:5173` in your browser.

### 3. Running Tests

```bash
# Backend pytest suite:
cd backend
.venv\Scripts\pytest -v

# Frontend Vitest suite:
cd frontend
npm run test
```
