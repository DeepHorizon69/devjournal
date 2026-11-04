# DevJournal — Development Guide

This document describes the local development workflow, project architecture, coding standards, and testing procedures for contributing to **DevJournal**.

---

## 1. Prerequisites

- **Python**: 3.11+ (Python 3.12 recommended; Python 3.14 compatible).
- **Node.js**: v20.0+ (LTS).
- **npm**: v10.0+.
- **Git**: 2.30+.

---

## 2. Local Development Setup

### 2.1 Backend Setup (FastAPI)

1. Open a terminal and navigate to the `backend/` directory:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   ```bash
   # Windows PowerShell:
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS:
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install all production and development dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Launch the FastAPI development server with auto-reload:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

5. Confirm the server is healthy by visiting:
   `http://127.0.0.1:8000/api/v1/system/health`

---

### 2.2 Frontend Setup (React + Vite)

1. In a separate terminal, navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```

2. Install npm dependencies:
   ```bash
   npm install
   ```

3. Launch the Vite development server:
   ```bash
   npm run dev
   ```

4. Open your browser to:
   `http://localhost:5173`

> [!NOTE]
> In development mode, Vite automatically proxies all `/api/*` HTTP requests to `http://127.0.0.1:8000`, so no CORS configuration is needed.

---

## 3. Project Directory Map

```text
devjournal/
├── backend/
│   ├── app/
│   │   ├── api/v1/             # REST endpoint routers (notes, search, dashboard, etc.)
│   │   ├── config.py           # Pydantic BaseSettings environment configuration
│   │   ├── db/                 # SQLite connection and schema definitions
│   │   ├── models/             # Pydantic v2 schemas and request/response models
│   │   ├── services/           # Vault storage, frontmatter, indexing, templates
│   │   └── main.py             # FastAPI app factory, CORS, static SPA mount
│   ├── tests/                  # Pytest automated test suite
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/                # Typed fetch client and TanStack Query hooks
│   │   ├── components/
│   │   │   ├── layout/         # AppShell, SidebarNav, TopBar
│   │   │   ├── notes/          # NoteRow, FilterBar, NewNoteModal
│   │   │   ├── search/         # CommandPalette
│   │   │   └── ui/             # 20 reusable design system primitives
│   │   ├── pages/              # Overview, Notes, Daily, Editor, Search, Settings
│   │   ├── store/              # Zustand UI state (sidebar, modals, view modes)
│   │   ├── test/               # Vitest unit and component tests
│   │   ├── types/              # Domain TypeScript interfaces
│   │   ├── App.tsx             # React Router routing tree
│   │   └── main.tsx            # Application entry point
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── vite.config.ts
├── devjournal-data/            # Local data directory (gitignored)
│   ├── vault/                  # Canonical Markdown hierarchy (00-Inbox to 99-Trash)
│   └── devjournal.db           # SQLite metadata and FTS5 search index
├── docs/                       # Technical documentation suite
└── README.md
```

---

## 4. Coding Conventions

### 4.1 Backend (Python)
- **Formatting**: Adhere to PEP 8. Use standard 4-space indentation.
- **Type Annotations**: Enforce strict type annotations on all function signatures and router responses.
- **Data Validation**: Use Pydantic v2 schemas exclusively for request and response payloads.
- **Database Access**: Use parameterized SQL queries (`?` placeholders) inside repository functions. Never concatenate raw SQL strings.
- **Filesystem Security**: All file operations inside `vault/` must be validated using `resolve_safe_vault_path()` to prevent directory traversal.

### 4.2 Frontend (TypeScript + React)
- **TypeScript**: Strict mode is enabled (`noImplicitAny: true`, `noUnusedLocals: true`).
- **Styling**: Use Tailwind CSS utilities mapped to the design tokens defined in `tailwind.config.js` (`canvas-app`, `canvas-sidebar`, `canvas-surface`, `canvas-elevated`, `accent`, etc.).
- **Spacing Scale**: Base layout increments on the 4px scale (`p-1` = 4px, `p-2` = 8px, `p-3` = 12px, `p-4` = 16px). Use 6px (`p-1.5`) only for micro-spacing inside compact controls.
- **Accessibility**: All interactive elements must have accessible labels (`aria-label`) and visible keyboard focus indicators (`focus-visible:ring-2`).

---

## 5. Testing & Verification Procedures

### 5.1 Backend Tests (Pytest)
Run the backend pytest suite inside `backend/`:

```bash
cd backend
.\.venv\Scripts\pytest -v
```

Tests cover:
- Vault path sanitization and directory traversal prevention.
- YAML frontmatter parsing and normalization.
- Optimistic locking and `HTTP 409 Conflict` detection.
- Full-text search and BM25 ranking.
- System health and SPA static serving.

### 5.2 Frontend Tests (Vitest)
Run the frontend component and unit tests inside `frontend/`:

```bash
cd frontend
npm run test
```

Tests cover:
- SidebarNav rendering, branding, and active navigation states.
- 60px collapsed icon-rail rendering with portaled tooltips.
- Design system primitives (`Button`, `IconButton`, `Badge`, `StatusIndicator`, `NoteRow`, `FilterBar`, `Modal`).

### 5.3 Production Build Verification
Ensure the TypeScript compiler and Vite bundler produce a clean production build with zero warnings or errors:

```bash
cd frontend
npm run build
```

This compiles static assets into `frontend/dist/`, which the FastAPI backend serves in production.
