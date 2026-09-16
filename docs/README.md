# Manga OS

A self-hostable, tri-platform manga reader. Web app, native desktop (Windows/macOS/Linux via Tauri), and Android (via Capacitor) — all from one React codebase.

> Built as a modern, open-source alternative to Tachiyomi with a glassmorphic UI and cloud sync.

---

## Features

- **500+ sources** — Tachiyomi-compatible extension engine; install/uninstall/enable/disable/update extensions from Keiyoushi index; built-in MangaDex, MangaKatana, Komga, Suwayomi providers
- **4 reading modes** — LTR pager, RTL pager, webtoon scroll, vertical pager; dual-page spread, tap zones, crop borders, webtoon padding, filters (brightness/contrast/grayscale/invert/sepia)
- **Download queue** — real-time WebSocket progress, CBZ with ComicInfo.xml, pause/resume/cancel/retry
- **Local library** — CBZ, ZIP, EPUB import; batch select with download/delete/move-to-category; dynamic grid columns; 8 filter modes; categories
- **Tracking** — AniList, MAL, Kitsu, MangaUpdates, Shikimori, Bangumi; sync status/score/chapters/dates
- **History** — full reading history with date filters (today/week/month); cloud-synced progress
- **Stats** — reading time, pace, per-category breakdown, 52-week heatmap, reading goals
- **Backup** — JSON export/import, Tachiyomi .tachibk + JSON import, cloud backup (Supabase), auto-backup schedule
- **Source migration** — move a manga from one source to another, preserving library entry
- **Cloud sync** — optional Supabase backend for reading progress, library, and backup across devices. Write actions, categories, and downloads are gated strictly to `zenmisan@gmail.com` to optimize backend resource load.
- **Onboarding** — triggers dynamically on first-time reader open, preserving API/backend setup state on the local device across different account logins.
- **Tri-platform**:
  - **Web** — PWA (offline-capable), auto-sync subscribed manga every 30 min.
  - **Desktop (Tauri v2)** — background chapter sync, OS notifications, auto-launch, update checker, drag-drop import, custom download path, Discord Rich Presence. Bypasses marketing page for logged-in sessions or native shells; builds served via Supabase Storage.
  - **Android (Capacitor)** — hardware volume keys, back button, screen keep-on, haptics, status bar ambilight, save to device, download notifications. Direct APK download from Supabase Storage.
- **Glassmorphic UI** — Tailwind + Framer Motion, dynamic ambilight colour theming from cover art

---

## Architecture

```
React 19 + Vite + TypeScript
        │
        ├── Web      → Firebase Hosting → FastAPI backend → Supabase
        ├── Desktop  → Tauri (Rust) shell → local FS + optional Supabase sync
        └── Android  → Capacitor shell → SQLite + optional Supabase sync
```

**Web users** rely on the FastAPI backend for scraping (browser CORS limits).  
**Native users** can scrape directly on-device; backend used only for sync.

---

## Stack

| Layer    | Tech                                                  |
|----------|-------------------------------------------------------|
| Frontend | React 19, Vite, TypeScript, Tailwind v4, Framer Motion, Zustand |
| Backend  | FastAPI, SQLAlchemy 2, aiosqlite, curl_cffi, Pillow   |
| Desktop  | Tauri v2 (Rust)                                       |
| Mobile   | Capacitor v8, Android                                 |
| Database | SQLite (local) or PostgreSQL via Supabase             |
| Storage  | Local filesystem or Supabase Storage                  |

---

## Local Development

### Prerequisites

- [Bun](https://bun.sh) — JS package manager
- Python 3.14+
- Rust toolchain (desktop only)
- JDK 17 + Android Studio (Android only)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy and edit env
cp .env.example .env

uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`. Interactive docs at `/docs`.

**Environment variables:**

| Variable              | Default                          | Description                              |
|-----------------------|----------------------------------|------------------------------------------|
| `DATABASE_URL`        | `sqlite+aiosqlite:///./manga_dl.db` | SQLite or PostgreSQL URI              |
| `LIBRARY_PATH`        | `~/manga-library`                | Where downloaded CBZ files are stored    |
| `CACHE_PATH`          | `~/.manga-dl-cache`              | Temp image cache                         |
| `API_KEY`             | _(none)_                         | Optional — lock API behind a secret key  |
| `CORS_ORIGINS`        | `http://localhost:5173`          | Comma-separated or JSON array of origins |
| `SUPABASE_URL`        | _(none)_                         | Supabase project URL                     |
| `SUPABASE_SERVICE_KEY`| _(none)_                         | Supabase service role key                |
| `MAX_STORAGE_MB`      | `900`                            | Storage cap before smart eviction kicks in |

### Frontend (Web)

```bash
cd frontend
bun install
bun run dev   # http://localhost:5173
```

### Desktop (Tauri)

```bash
# Install Rust: https://rustup.rs

# Linux additional deps (Arch):
sudo pacman -S webkit2gtk-4.1 base-devel curl wget file xdotool openssl libappindicator-gtk3 librsvg

# Linux additional deps (Ubuntu/Debian):
sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev

cd frontend
bun run tauri dev          # dev mode with hot-reload
bun run tauri build        # release binary → src-tauri/target/release/bundle/
```

### Android (Capacitor)

Requires JDK 17 (not 17+) and Android Studio.

```bash
cd frontend
bun run build          # build React assets first
bun run android:sync   # sync assets into android/
bun run android:open   # open in Android Studio
```

Then use Android Studio to run on emulator/device or build APK via **Build > Build APK(s)**.

---

## Deployment (Free Tier)

### 1. Database — Supabase (free PostgreSQL)

1. Create project at [supabase.com](https://supabase.com)
2. Copy the **Transaction Pooler** connection string (Settings > Database)
3. Set prefix to `postgresql+psycopg://` and append `?sslmode=require`

### 2. Backend — Render (Docker)

1. Push repo to GitHub
2. Create a new **Web Service** on Render, select Docker runtime
3. Set environment variables (see table above), plus:
   - `DATABASE_URL` — your Supabase pooler URI
   - `CORS_ORIGINS` — your Firebase app URL

> Render free tier sleeps after 15 min of inactivity. First request after sleep may take ~60s.

### 3. Frontend — Firebase Hosting

```bash
npm install -g firebase-tools
firebase login
cd frontend
bun run build
firebase deploy --only hosting
```

Update `frontend/src/lib/api.ts` `baseURL` to point at your Render backend URL before building.

---

## API Overview

All `/api` routes require `X-API-Key` header if `API_KEY` is set in backend config.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/manga/providers` | List all sources and health status |
| `GET` | `/api/manga/search?q=&provider=&page=` | Search across sources |
| `GET` | `/api/manga/{provider}/{manga_id}` | Manga detail + chapter list |
| `POST` | `/api/downloads/queue` | Enqueue chapter download |
| `GET` | `/api/downloads/active` | Current download queue state |
| `GET` | `/api/downloads/history` | Last 100 completed/failed jobs |
| `WS` | `/api/downloads/ws` | Real-time download progress stream |
| `GET` | `/api/library` | Scan and return local CBZ library |

Full spec: [`docs/API_SPEC.md`](docs/API_SPEC.md)

---

## Project Structure

```
manga-dl/
├── backend/
│   ├── app/
│   │   ├── api/          # Route handlers (manga, downloads, library, auth, users)
│   │   ├── core/         # Queue, downloader, storage, security
│   │   ├── models/       # SQLAlchemy models
│   │   ├── providers/    # Source scrapers (MangaDex, AsuraScans, etc.)
│   │   └── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/              # React app
│   ├── src-tauri/        # Tauri Rust shell
│   ├── android/          # Capacitor Android project
│   └── package.json
└── docs/                 # All project documentation and research reports
    ├── API_SPEC.md
    ├── ARCHITECTURE.md
    ├── CONTRIBUTING.md
    ├── DEPLOYMENT.md
    ├── FEATURES.md
    ├── KNOWN_ISSUES.md
    ├── MASTER_PLAN.md
    ├── PLATFORM_MATRIX.md
    ├── PROJECT_CONTEXT.md
    ├── PROJECT_STATUS.md
    ├── implementation_plan.md
    ├── keiyoushi_source_analysis.md
    └── manga_dl_comprehensive_analysis.md
```

---

## Docs

All markdown documentation and analysis files are stored in the [docs/](docs/) folder:
- [Architecture](docs/ARCHITECTURE.md)
- [API Specification](docs/API_SPEC.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Contributing / Build Guide](docs/CONTRIBUTING.md)
- [Implementation Plan](docs/implementation_plan.md) (approved strategy and checklists)
- [Keiyoushi Source Analysis](docs/keiyoushi_source_analysis.md) (Tachiyomi-compatible extension engine details)
- [Comprehensive Analytical Report](docs/manga_dl_comprehensive_analysis.md) (SWOT, Gap, User/UX, Feature, Heuristic, Cost-Benefit, Risk, and SCAMPER)
- [Master Plan](docs/MASTER_PLAN.md) (overall roadmap)
- [Project Status](docs/PROJECT_STATUS.md) (current release checklist)
- [Features Specification](docs/FEATURES.md)
- [Known Issues & Limitations](docs/KNOWN_ISSUES.md)
- [Suwayomi Analysis](docs/suwayomi_analysis.md) (architecture comparison and desktop native opportunities)
