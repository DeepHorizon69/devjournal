# DevJournal — Quick Deployment Guide

This guide provides step-by-step instructions to get **DevJournal** up and running in under two minutes, either locally on your workstation or on any remote server (VPS, Cloud VM, or Homelab).

---

## ⚡ Deployment Method Matrix

| Method | Best For | Prerequisites | Setup Time |
|---|---|---|---|
| **[Method 1: Docker Compose](#method-1--docker-compose-recommended)** *(Recommended)* | Servers, VPS, Homelab, or Local Docker | Docker & Docker Compose | **1 min** |
| **[Method 2: Native Python Run](#method-2--native-host-run-no-docker)** | Quick local inspection without Docker | Python 3.12+, Node 20+ | **2 mins** |

---

## Method 1 — Docker Compose (Recommended)

Works identically on **Linux servers (Ubuntu, Debian, Fedora)**, **macOS**, and **Windows**.

### Step 1: Clone the Repository
```bash
git clone https://github.com/DeepHorizon69/devjournal.git
cd devjournal
```

### Step 2: Launch the Container
```bash
docker compose up -d --build
```

### Step 3: Verify It's Running
Open your browser or run:
```bash
curl http://127.0.0.1:8000/api/v1/system/health
```

* **Web UI**: Open `http://localhost:8000` (or `http://your-server-ip:8000`)
* **API Documentation**: `http://localhost:8000/docs`

> [!TIP]
> **Data Persistence**: All your Markdown notes, SQLite database, and backups are permanently stored on the host machine in `./devjournal-data/`. Updating or stopping the container will **never** delete your notes.

---

## Method 2 — Native Host Run (No Docker)

If you don't have Docker installed and want to run DevJournal directly:

### 1. Build the Frontend Assets (One-Time)
```bash
cd frontend
npm ci
npm run build
cd ..
```

### 2. Set Up the Python Backend
* **On Linux / macOS:**
  ```bash
  cd backend
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  cd ..
  PYTHONPATH=backend python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
  ```

* **On Windows (PowerShell):**
  ```powershell
  cd backend
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  cd ..
  $env:PYTHONPATH="backend"
  .\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
  ```

---

## 🌐 Remote Access & Security (For Cloud / VPS)

Because DevJournal is a single-user knowledge base, never expose port `8000` unprotected to the open internet. Use one of these two free methods:

### Option A: Cloudflare Tunnel (Free Public Domain + HTTPS)
No open firewall ports required:
1. Install `cloudflared`:
   ```bash
   curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
   sudo dpkg -i cloudflared.deb
   ```
2. Start an instant quick tunnel:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
   *(Or bind to your custom domain via the Cloudflare Zero Trust dashboard with Google/GitHub login protection).*

### Option B: Tailscale VPN (Private & Encrypted)
1. Install [Tailscale](https://tailscale.com/) on your server and phone/laptop.
2. Bind DevJournal to your Tailscale IP:
   Open `docker-compose.yml` and replace `"127.0.0.1:8000:8000"` with:
   ```yaml
   ports:
     - "YOUR_TAILSCALE_IP:8000:8000"
   ```
3. Access your journal securely from anywhere via `http://YOUR_TAILSCALE_IP:8000`.

---

## 🛠️ Common Operations & Maintenance

### Update to Latest Version
```bash
git pull origin main
docker compose up -d --build
```

### Create a Instant Backup
* **Via Web UI**: Navigate to **Settings** $\rightarrow$ **Backup, Restore & Markdown Import** $\rightarrow$ **Create & Download Backup**.
* **Via Terminal**:
  ```bash
  curl -X POST http://127.0.0.1:8000/api/v1/system/backup
  ```
  *Backups are saved as verified `.zip` archives in `./devjournal-data/backups/`.*

### Stop or Restart
```bash
# Stop
docker compose down

# Restart
docker compose restart
```
