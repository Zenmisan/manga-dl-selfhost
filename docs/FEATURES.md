# manga-dl — Project Status

A tri-platform manga reader and downloader.  
**Web:** PWA (vite-plugin-pwa + workbox)  
**Desktop:** Tauri v2 — AppImage / .deb / .exe / .dmg  
**Mobile:** Capacitor Android APK  
**Backend:** FastAPI + SQLite (local) / Supabase PostgreSQL (prod) on Render

Last updated: 2026-09-12

---

## What Works ✅

### Core Reading & Library
- Search manga across 500+ sources (Tachiyomi-compatible extension engine)
- View manga detail + chapter list with cover images (proxied)
- Download chapters as CBZ → local library or Supabase cloud storage
- Download queue with real-time WebSocket progress, pause/resume/cancel/retry
- Library shows downloaded chapters AND subscribed series
- Subscribe / unsubscribe — auto-downloads new chapters via background sync
- Manual sync trigger from Settings
- CBZ reader — webtoon scroll, manga LTR, manga RTL, vertical pager
- Ambilight ambient colour effect in reader
- Export chapter as PDF or EPUB3
- Reading progress saved per chapter (local + cloud sync)
- MAL + AniList auto-track on chapter completion
- Browser push notifications for new chapter queues
- Reading stats page (chapters, pages, streaks, provider breakdown, reading time, pace, per-category)

### Library Management
- Grid/list toggle with cover images
- Sort: A-Z, Z-A, most downloaded, last read, most unread
- Filter: subscribed, downloading, failed, has unread, downloaded-only, started, completed (8 options)
- Batch select mode — checkbox overlay, floating action bar (download all / delete / move to category)
- Dynamic grid columns (2–6) configurable in Settings
- Categories with custom creation + per-manga assignment
- Unread badge, download badge on cards
- Continue reading button on library cards

### Reader
- 4 modes: LTR pager, RTL pager, webtoon scroll, vertical pager
- Webtoon dynamic scroll tracking: continuous viewport observer updating page indicators in real-time
- Brightness, contrast, grayscale, invert, sepia filters
- Crop borders (pager + webtoon independently)
- Webtoon side padding slider (0–80px)
- Dual-page spread: Auto / Always On / Off
- Tap zone layouts: Default / L-Nav / Edge / Disabled
- Volume key navigation (keyboard + Android hardware keys)
- Skip read chapters toggle
- Image prefetch (next 3 pages)
- Chapter transition screen with "Next Chapter →"
- Incognito mode (no history saved)
- Shareable chapter link (Web Share API + clipboard)
- Discord Rich Presence (desktop only)

### Manga Detail & Chapter Lists
- In-chapter read percentage bar: visual progress line showing 0–100% completion per chapter
- Contextual resume buttons: dynamic labels ("Start Reading", "Continue Ch. X", "Re-read Ch. X")
- Adaptive stats layout: automatic collapsing to 2-column layout when unrated
- Clean synopsis rendering: automatic Markdown tag stripping (`**bold**`, `[links]`, etc.)
- Genre badge pills: high-contrast top-3 genres and `+N more` overflow pill

### Online Reading & Discovery
- Discovery APIs: `/api/discovery/popular` and `/api/discovery/latest` with file-backed caching
- Interactive source toggles: `SourceToggleModal` component for toggling active search extensions
- Stream chapter pages without downloading
- Image proxy via curl_cffi with Chrome impersonation + correct Referer
- Cloud reading progress sync (saves page, resumes on next open) — requires login
- Smart URLs & Clean Paths (`/read/:title-slug-:extCode/:chapterSlug`)
- Public Library Access: Unlocked for all authenticated users (read, stream, convert PDF/EPUB)

### SEO & Social Previews
- Dynamic Page Titles: `usePageTitle` hook managing browser tab titles across all 15 routes and reader
- Enriched OpenGraph & Twitter Cards: Absolute canonical image tags and dimensions for Discord, Twitter/X, and Telegram unfurls
- XML Sitemap (`public/sitemap.xml`) covering all core application routes
- Crawler directives (`public/robots.txt`) allowing Google Search indexing

### User Onboarding & Profiles
- Automated username generation (`/api/users/generate-username`) suggesting unique handles
- Custom avatar selection and profile management
- Support ticket submission (`/api/users/support-ticket`)
- Transactional email service for welcome notifications and support ticket confirmations

### Mobile & Native Packaging
- Automated local Android SDK toolchain provisioning (`/home/zenmi/Android/Sdk`)
- Custom Gradle APK naming (`manga-dl-v1.0.apk` / `manga-dl-v1.0-debug.apk`)
- Linux desktop bundles (AppImage, `.deb`, `.rpm`) using Tauri v2
- Biometric App Lock session guard preventing infinite re-prompt loops
- Native volume key navigation (`VolumeKeys` plugin)
- Automatic bottom navbar hiding inside reader routes (`/read/...`)

### Performance / Lazy Loading
- TanStack Query v5 wraps all API calls with stale-while-revalidate caching
- Tab revisits show cached data instantly — no re-fetch until stale (library 30s, stats 2min, sources 5min, market 10min, updates 5min, history 60s)
- `refetchOnWindowFocus: false` — no spurious fetches on browser focus
- Local IndexedDB manga items merged into library cache alongside backend data
- Tab transitions: opacity-only, `mode="sync"`, 80ms — GPU-composited, no layout recalc

### History
- Full history page with manga title, chapter, page
- Clear all or per-manga
- Filter by date: Today / This Week / This Month / All
- Search by manga title
- Resume reading from history entry

### Statistics
- Total manga, chapters, pages, storage
- 30-day download activity chart
- Provider breakdown chart + download streak
- GitHub-style 52-week heatmap
- Reading goals (monthly chapters / yearly manga)
- Reading time estimate (pages × 45s)
- Reading pace (chapters/week from last 7 days)
- Per-category manga count bar chart

### Tracking
- AniList OAuth + reading sync
- MAL OAuth (PKCE) + reading sync
- Kitsu OAuth (password grant)
- MangaUpdates, Shikimori, Bangumi — link + display
- Tracker sync modal: set status / score / chapters read / start date / finish date (AniList + MAL)
- Per-manga notification mute toggle (when subscribed)

### Backup & Restore
- JSON backup v2 (library + history + all localStorage + categories + read tracking)
- Selective restore (per key, with confirmation)
- Tachiyomi JSON + .tachibk binary import
- Cloud backup to Supabase storage bucket
- Auto-backup: scheduled daily/weekly browser download

### Manga Management
- Manual metadata edit: title, cover URL, description (persisted, overrides source data)
- Source migration UI: pick library manga → find on new source → confirm (POST /manga/migrate)
- Chapter bookmarks, scanlator filter, bulk mark read
- Manga notes + 5-star personal rating

### Local Files
- Upload CBZ/ZIP/EPUB from disk → IndexedDB → read locally
- EPUB support: JSZip + OPF spine parsing, images extracted and displayed as pages
- Drag-and-drop CBZ/EPUB import (desktop only, Tauri)

### Extensions
- Install / uninstall from Keiyoushi index (500+ sources)
- Language filter + search in marketplace
- Enable/disable toggle per installed extension
- Update checking (compares installed version vs remote)
- Installed / available split view

### Desktop (Tauri v2)
- Background chapter sync (Rust tokio task, configurable 15/30/60/120 min)
- OS notification when new chapters found (tauri-plugin-notification)
- Auto-launch on startup (tauri-plugin-autostart)
- In-app update checker (GitHub releases API)
- Custom download location (folder picker)
- Drag-and-drop CBZ/EPUB import
- Discord Rich Presence
- System tray (hide to tray on close)
- Reveal file in system file manager

### Android (Capacitor)
- Hardware back button handlers (Reader, MangaDetail, Dashboard exit)
- Volume key page navigation (Kotlin plugin)
- Keep screen on while reading (KeepAwake)
- Status bar colour sync with ambilight
- Haptic feedback on page turn (configurable)
- Save chapter to device storage (Capacitor Filesystem → Documents/manga-dl/)
- Download completion notification (@capacitor/local-notifications)

### Account & Security
- Register / login with Supabase Auth
- 3-device limit enforced in backend
- API key auth for backend
- Incognito mode (no history)

---

## Not Yet Implemented 🔲

| Feature | Priority | Notes |
|---------|----------|-------|
| WebView fallback for Cloudflare sources | Medium | Some sources need JS challenge solving |
| RAR/CBR archive support | Low | Need native decompressor |
| Folder import (bulk scan local directory) | Low | Desktop: Tauri readDir + filter |
| Tablet multi-column reading view | Low | |
| Custom date format | Low | |
| DNS-over-HTTPS | Low | |
| Custom user agent | Low | |
| Material You dynamic colours | Low | Android 12+ only |
| Auto-delete chapter after read | Low | |
| Split dual-page spreads | Low | |
| Background sync (Android WorkManager) | Low | Currently depends on app being open |
| Tracker filter in library | Low | |
| Badge count on app icon | Low | Requires FCM setup |

---

## Known Broken / Needs Setup ⚠️

### Discord Rich Presence — placeholder App ID
- `frontend/src-tauri/src/lib.rs` → `DISCORD_APP_ID = "1234567890123456789"`
- Replace with real Discord Developer App ID

### Cloud Backup — Supabase bucket must be created manually
- Supabase dashboard → Storage → New bucket → `manga-backups` → private

### Supabase Production DB — run these SQL migrations
```sql
ALTER TABLE downloads ADD COLUMN IF NOT EXISTS file_size_bytes INTEGER DEFAULT 0;
ALTER TABLE downloads ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE;
ALTER TABLE downloads ADD COLUMN IF NOT EXISTS last_page_read INTEGER DEFAULT 0;

CREATE TABLE IF NOT EXISTS reading_progress (
  user_id    VARCHAR NOT NULL,
  provider   VARCHAR NOT NULL,
  manga_id   VARCHAR NOT NULL,
  chapter_id VARCHAR NOT NULL,
  last_page  INTEGER DEFAULT 1,
  updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  PRIMARY KEY (user_id, provider, manga_id, chapter_id)
);
```

### Extensions — Keiyoushi index is Android APK metadata
- No JS source files exist in the index
- Built-in providers (MangaDex, MangaKatana, etc.) work; installed extensions are JS shims

---

## Architecture

```
Frontend (React 19 + TypeScript + Vite + Tailwind + Zustand)
  ├── Web        → PWA (vite-plugin-pwa + workbox)
  ├── Desktop    → Tauri v2 shell (auto-starts Python backend)
  └── Android    → Capacitor shell (calls Render backend by default)

Backend (FastAPI + SQLAlchemy + aiosqlite)
  ├── Local dev  → SQLite (manga_dl.db)
  ├── Production → Supabase PostgreSQL (via DATABASE_URL env var)
  └── Storage    → Supabase Storage bucket "manga-library"

Auth
  ├── API key    → X-API-Key header (all endpoints except /api/users/*)
  └── Supabase   → JWT Bearer token (/api/users/* — reading progress, devices)
```

## Environment Variables

### Backend (Render)
| Var | Value |
|-----|-------|
| `API_KEY` | `mgdl-creator` — change in prod |
| `SUPABASE_URL` | `https://gyivwfweldwvzccbpgoz.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Service role key |
| `SUPABASE_JWT_SECRET` | JWT secret |
| `CORS_ORIGINS` | Comma-separated allowed origins |

### Frontend (build-time env vars)
| Var | Value |
|-----|-------|
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Anon/public key |
</content>
</invoke>