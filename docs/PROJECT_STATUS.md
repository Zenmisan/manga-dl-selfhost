# manga-dl — Project Status

Last updated: 2026-09-12

A tri-platform manga reader and downloader.  
**Web:** PWA · **Desktop:** Tauri v2 · **Mobile:** Capacitor Android · **Backend:** FastAPI (infra-only — see Phase 10)

---

## Implementation Phases

### Phase 1–6 ✅ Core + Power + Polish + Tracker depth + Reader power + Web QoL
All foundational features shipped: library, reader, downloads, history, stats, tracking (AniList/MAL/Kitsu/MangaUpdates/Shikimori/Bangumi), backup, categories, bookmarks, Discord RPC, PWA, ComicInfo.xml, all 4 reading modes, dual-page spread, tap zones, themes (dark/light/system/AMOLED).

### Phase 7 ✅ Desktop Native (Tauri v2)
Background sync, OS notifications, auto-launch, update checker, custom download location, drag-drop CBZ import, folder picker.

### Phase 8 ✅ Android Native (Capacitor)
Volume keys (Kotlin plugin), back button handlers, KeepAwake, StatusBar ambilight, haptics, save to device storage, download completion notifications.

### Phase 9 ✅ Remaining Features (latest session)
- **Library**: batch select (checkbox overlay + action bar: download/delete/move-to-category), dynamic grid columns (2–6)
- **Settings**: grid column slider, webtoon padding slider, crop borders webtoon toggle, auto-backup (daily/weekly schedule)
- **Extensions**: uninstall, enable/disable toggle, update checking, installed/available split view
- **MangaDetail**: per-manga notification mute, metadata edit modal (title/cover/description), tracker sync modal (status/score/chapters/start+end dates)
- **History**: date filter (Today/Week/Month/All) + search
- **Stats**: reading time estimate, reading pace (ch/week), per-category breakdown
- **Reader**: webtoon side padding, webtoon crop borders
- **Downloads**: Android completion notification (@capacitor/local-notifications)
- **App**: web/Android auto-sync every 30min (Tauri uses Rust task)
- **Backend**: POST /manga/migrate endpoint
- **Settings**: Source Migration UI (2-step wizard)
- **Library**: EPUB support (.epub → JSZip + OPF spine → images displayed as pages)

### Phase 10 ✅ Extension-first architecture (2026-06-15)
- **Removed** all Python scraper providers (MangaDex, AsuraScans, OmegaScans, MangaKatana) — backend is now infra-only (proxy + DB + downloads), no scraping.
- Manga sources are JS extensions running in Web Workers (Tachiyomi-style), managed client-side via `ExtensionManager`.
- New backend proxy endpoints so sandboxed extensions can bypass CORS: `/manga/proxy/html`, `/manga/proxy/json`, `/manga/image-proxy`.
- Modernized Asura Scans extension for its Astro migration (scraping pages directly from static HTML images) and fixed MangaKatana extension to support trailing commas in JS image arrays.
- Search "All" tab fans out across every loaded extension and merges results (previously called a now-deleted backend endpoint and silently did nothing).
- `Subscribe` now requires the frontend to send manga metadata in the request body — backend has no provider to fetch it from anymore.
- Community (non-built-in) Tachiyomi extensions disabled for install on web — they're Android APKs, not JS, can't run in a browser.
- Fixed CORS-breaking trailing-slash redirect bug: `FastAPI(..., redirect_slashes=False)`.
- Fixed Android Gradle build (`kotlin-android` plugin wasn't applied to `:app`, Kotlin Gradle plugin too old for `@capacitor/filesystem`'s stdlib version — bumped to 2.1.0).
- Added in-app update checker (GitHub Releases API) surfaced in More page — Android opens APK URL for native install; Tauri in-place updater not yet wired (needs Rust recompile).

### Phase 11 ✅ Landing Page + Auth Routing (2026-06-16)
- **Full Landing Page**: Implemented at `/` with SEO meta tags, OG tags, and 100dvh hero section.
- **Auth Integration**: Supabase session state wired to Sidebar and Protected Routes.
- **Route Restructure**: Moved the main app to `/r` and implemented a high-impact landing page at root.

### Phase 12 ✅ Android UI Restructure (2026-06-16)
- **Bottom Navigation**: Implemented for mobile (Library, Updates, Search, Browse, More).
- **"More" Page**: Added with Incognito mode, History, Stats, and Settings links.
- **MangaDetail V2**: Implemented hero-style blurred cover art and floating "Smart Binge" FAB.

### Phase 13 ✅ Settings Restructure (2026-06-16)
- **Settings Split**: Refactored the monolithic 1000+ line `Settings.tsx` into categorized sub-pages (`General`, `Reader`, `Library`, `Trackers`, `System`).
- **Sidebar Layout**: Implemented a modern sidebar-based settings layout for desktop/tablet and a scrollable tab-strip for mobile.
- **Nested Routing**: Updated `App.tsx` with nested routes for each settings category.
- **Improved UX**: Categorized settings make it easier to find specific configurations across all platforms.

---
### Phase 14 ✅ Metadata Cloud Sync (2026-06-16)
- **Supabase Integration**: Created a `manga_overrides` table to store user-specific metadata overrides (Title, Cover URL, Description).
- **Backend API**: Added `PUT` and `GET` endpoints to `/users/manga-overrides` for synchronizing overrides.
- **Frontend Sync**: Implemented `syncMetaOverridesFromCloud` to pull overrides into `localStorage` on login/app start, ensuring cross-device consistency.
- **UI Application**: `MangaDetail` now automatically applies synced overrides when rendering manga data.

### Phase 15 ✅ Read-Based Heatmap (2026-06-16)
- **Backend Analytics**: Created a new `/users/me/stats` endpoint that aggregates historical data directly from the `ReadingProgress` table, ensuring only active, in-app reading sessions are counted.
- **Frontend Refactor**: Updated `Stats.tsx` to prioritize reading metrics (reads per day/year) while seamlessly falling back to download metrics for offline/unauthenticated users.
- **Improved Accuracy**: The heatmap and activity charts now accurately reflect true reading engagement rather than automated download queues.

### Phase 16 ✅ Security & Sync Gates (2026-06-17)
- **Biometric App Lock (Android)**: Integrated `@aparajita/capacitor-biometric-auth` in `App.tsx` and custom toggles in General settings.
- **WiFi & Charging Sync Gates**: Added sync guards using `@capacitor/network` and the Battery Status API, configurable in System settings.

### Phase 17 ✅ Multi-Device Native Access Control & Direct Delivery (2026-06-20)
- **Auth-Aware Landing Page & Redirection**: Configured the marketing landing page (`/`) to show only when the user is logged out on all devices (including Tauri/Capacitor). Logged-in users are automatically routed to the library dashboard (`/r`) with a smooth `loadingSession` state checking process to prevent flashes. Logging out cleans user session states and redirects the user back to the landing page.
- **Typography Upgrade**: Replaced display fonts on the landing page and globally with **Anton** (for hero titles, numbers, and headers) + **Inter** (for UI metadata, text, and descriptions) to create a premium, clean design.
- **Tablet Width Layout Fix**: Resolved card/tag overlapping on `Sources.tsx` for tablet viewports (843px - 1213px) using dynamic flexbox column wrapping.
- **Access Control Restriction**: Restricted backend `/library` write APIs, file uploads, categories, and download buttons strictly to `zenmisan@gmail.com`.
- **Direct Supabase Downloads**: Redirected app releases links on the landing page and download hub to serve directly from Supabase Storage instead of redirecting users to GitHub.
- **Onboarding Flow Refactor**: Shifted first-run onboarding to trigger dynamically upon entering reader mode for the first time, preserving the setup state on the local device across different account sign-ins.
- **Strategic Analyses Report**: Authored comprehensive analytical reports (SWOT, Gap, User/UX, Feature, Heuristic, Cost-Benefit, Risk, and SCAMPER).

### Phase 18 ✅ Desktop UI & Tauri Chrome (2026-07-05)
- **Sidebar Active Indicator**: Rendered a premium red vertical accent bar on the left edge of the active navigation links, enhancing visual cue clarity on desktop views.
- **Two-Column MangaDetail Layout**: Refactored the manga detail page layout on wide screens to present cover art and details on a sticky left panel, allowing user to scroll the chapters list on the right panel. Maintains single-column responsiveness on mobile and tablet screens.
- **Reader Keyboard Shortcuts Overlay**: Added a beautiful glassmorphic modal overlay detailing keyboard control mappings (left/right/down arrows, Space, Esc) that appears on the user's first visit to the reader view, with preference state stored in local storage.
- **Tauri Custom Titlebar**: Integrated custom window titlebar chrome for native desktop builds with a drag region and interactive minimize/maximize/close macOS-style traffic light buttons, powered by dynamic imports of Tauri's APIs.

### Phase 19 ✅ Platform Fixes, Performance & Code Quality (2026-07-20 - 2026-07-22)

#### Bug Fixes
- **Android CORS**: Added `https://localhost` and `capacitor://localhost` to backend `CORS_ORIGINS`. Capacitor with `androidScheme: 'https'` makes the WebView origin `https://localhost`; without it every API call was blocked.
- **Android HTTP to LAN backend**: `network_security_config.xml` used invalid CIDR notation (`10.0.0.0/8`) in `<domain>` elements — silently ignored by Android. Replaced with `<base-config cleartextTrafficPermitted="true">` so self-hosted LAN backends work.
- **Backend unreachable banner**: Banner now auto-dismisses after 30s and has a working close button. Reappears if backend goes down again after recovering.
- **Blank page at `/r`**: Fixed fresh-visit routing bug where the app shell rendered before the session check completed.
- **Onboarding for web users**: First-visit onboarding now triggers correctly for unauthenticated web users entering the reader for the first time.

#### Reader Refactor (Reader.tsx: 1130 lines → 169)
Extracted into purpose-built hooks and components:
- `useReaderData.ts` (233 lines) — page/chapter state, manifest fetch (3 code paths: online/local/remote), MAL+AniList auto-sync, debounced cloud save, next-chapter prefetch, in-browser page prefetch, cloud upload.
- `useAndroidFeatures.ts` (34 lines) — back button, KeepAwake, StatusBar ambilight sync.
- `useReaderNavigation.ts` (112 lines) — nextPage/prevPage, tap zones, spread logic, keyboard/volume key handler, chapter navigation.
- `ReaderHeader.tsx` (185 lines) — header with reading mode + scale dropdowns typed on union literals (no `string`).
- `ReaderViewport.tsx` (168 lines) — webtoon/vertical-pager/pager renderers, chapter-end overlay, nav buttons.
- `ShortcutOverlay.tsx` (68 lines) — first-time keyboard controls tutorial.
- `Reader.tsx` is now 169 lines of glue: hook calls, ambilight state, loading/error screens, render tree.

#### Tab Animation Performance
- Changed `AnimatePresence` from `mode="wait"` (sequential, ~500ms perceived) to `mode="sync"` (overlapping) with `duration: 0.08` opacity-only transition. Removed `y`/`scale` transforms — opacity is GPU-composited and eliminates layout recalcs.

#### Lazy Loading — TanStack Query v5
- Installed `@tanstack/react-query`. `QueryClient` wraps the entire app in `main.tsx` with `staleTime: 60s`, `gcTime: 5min`, `refetchOnWindowFocus: false`.
- Central query hooks in `src/lib/queries.ts` with per-endpoint stale times: library (30s), stats (2min), sources (5min), market (10min), updates (5min), history (60s).
- Migrated: Dashboard, Stats, Updates, History, Sources — all use cached data on tab revisit; no re-fetch until stale.
- Dashboard: local IndexedDB items kept in separate `localItems` state, merged into the `items` useMemo alongside backend data. Banner dismiss state decoupled from `isError` via `bannerDismissed` local state.

### Phase 20 ✅ Architecture Modularization & Platform Audit Fixes (2026-07-21 - 2026-07-22)

#### Conductor Tracks & Ralph's Method Workflow
- Integrated Ralph's Method track lifecycle (`.agents/tracks/`) for feature developments, bug fixes, and architectural refactors.

#### Backend Services Layer (`backend/app/services/`)
- **`archive_converter.py`**: Extracted CBZ page listing, image extraction with upscaling, and stream conversion to PDF/EPUB.
- **`library_service.py`**: Extracted database library queries, stats, and disk caching.
- **`js_extensions.py`**: Extracted extension script loader and metadata definitions.
- **`proxy_service.py`**: Extracted CORS-bypassing proxy routines (`proxy_html`, `proxy_json`, `proxy_image`).
- **`manga_service.py`**: Extracted subscribed manga update streams, subscription toggles, and source migrations.
- **`device_service.py`**: Extracted device fingerprinting, registration limits (3 devices max), and 30-day forfeiture locking.
- **`user_service.py`**: Extracted user reading progress, history, stats, and public profile data.
- **FastAPI Routers**: Refactored `library.py`, `sources.py`, `manga.py`, and `users.py` down to concise, readable routers.

#### Standalone JS Extension Templates (`backend/app/services/extensions/`)
- Extracted raw JavaScript code strings into standalone `.js` template files:
  - `mangadex.js`: Fixed chapter title fallback formatting (`Chapter X: Title` instead of raw UUIDs like `995aba31...`).
  - `mangakatana.js`: Fixed title selector matching and repaired Popular (`/manga`) & Latest (`/latest`) scrapers.
  - `asurascans.js`: Modernized AST and scraper fallbacks for popular and latest lists.
  - `omegascans.js`: Fixed API query ordering parameters for popular and latest series.
  - `madara.template.js` & `mangathemesia.template.js`: Dynamic template generators for community scanlator sites.

#### Frontend Hooks Composition
- **`useMangaDetail.ts`**: Refactored from 456 lines down to ~220 lines by extracting sub-hooks:
  - `useMangaTracker.ts`: AniList / MAL search and progress/score synchronization.
  - `useMangaChaptersFilter.ts`: Chapter search, sort modes, read filters, and scanlator filters.
- **`useReaderNavigation.ts`**: Refactored from 149 lines down to ~100 lines by extracting:
  - `useReaderKeybindings.ts`: Volume keys (Capacitor) and physical keyboard shortcuts (`Arrow`, `Escape`).

#### Platform Audit & UX Fixes
- **Public Library Access**: Removed hardcoded admin restriction in `library.py` so all authenticated public users can manage and read their downloaded manga library.
- **Android Biometric Lock Fix**: Added session unlock guard (`isUnlockedRef`) in `App.tsx` preventing infinite re-prompt loops on app focus/resume.
- **SEO & Google Search Indexing**: Added `public/sitemap.xml` and `public/robots.txt` for search engine indexing and route inventory capture.
- **Reader Mobile Layout**: Hidden main app bottom navbar during reader routes (`/read/...`), fixed "Mark All Read" button overlap on mobile viewports, and updated online streaming loading indicators.

### Phase 21 ✅ User Onboarding, Profile Ecosystem & Auth Hardening (2026-07-31 - 2026-08-07)
- **Google Sign-In**: Fully integrated Firebase Authentication for Google Sign-In with robust error handling and fallbacks.
- **Username Generation & Setup**: Added onboarding username generator (`/api/users/generate-username`) suggesting available handles.
- **Support & Transactional Emails**: Implemented user support ticket submissions (`/api/users/support-ticket`) and automated transactional notifications (welcome email + support receipt) via backend email service.
- **Strict JWT Protection**: Replaced legacy `get_current_user` with `require_jwt_user` for per-user library isolation on `/api/library` and `/api/manga`.
- **Profile Polish**: Custom avatar selection, immutable username editing constraints, and seamless tracker configuration in Settings.

### Phase 22 ✅ Discovery Engine, Source Management & UI Overhaul (2026-08-07 - 2026-08-30)
- **Discovery API & Caching**: Server-side endpoints (`/api/discovery/popular`, `/api/discovery/latest`) with file-backed caching for rapid catalog browsing without hitting third-party source rate limits.
- **Source Toggle Modal**: Added dynamic `SourceToggleModal` component in search to filter and toggle active providers directly from the search bar.
- **Extension Reliability**: Purged deprecated/broken providers, upgraded User-Agent impersonation, and tuned scraping selectors.
- **UI Modernization**: Upgraded loading indicators across all views using `ThemedSpinner` and `ThemedLoadingScreen`, added high-contrast rounded pill filters, glassmorphic dropdowns, and interactive file import guides.

### Phase 23 ✅ Local Android SDK Toolchain & Packaging Automation (2026-08-31 - 2026-09-01)
- **Local Android SDK Provisioning**: Automated download and setup of official Google `cmdline-tools`, `platforms/android-34`, `build-tools/34.0.0`, and `platform-tools` in `/home/zenmi/Android/Sdk` with license automation.
- **App ID & Path Synchronizations**: Configured `CAPACITOR_ANDROID_STUDIO_PATH` for Arch Linux and synchronized `appId` (`com.zenmisan.mangadl`) in `capacitor.config.ts` with Gradle `applicationId`.
- **Custom APK Naming**: Configured Gradle variants to output cleanly versioned release (`manga-dl-v1.0.apk`) and debug (`manga-dl-v1.0-debug.apk`) artifacts.
- **Secrets Decoupling & Git Hygiene**: Removed hardcoded fallback keys from `firebase.ts` and `supabase.ts`, routed backend resolution to `VITE_BACKEND_URL`, and untracked SQLite `.db` and hosting cache files.
- **Deploy Boundary Protection**: Added executable ignore rules to `firebase.json` to comply with Spark plan limits while preserving Supabase release pipelines.

### Phase 24 ✅ Real-Time Webtoon Scroll, Reading Milestones & Social Metadata (2026-09-12)
- **Dynamic Webtoon Scroll Tracking**: Real-time viewport intersection tracker in `Reader.tsx` synchronizing the active page counter and bottom scrubber during smooth vertical reading.
- **In-Chapter Progress Bar**: Visual blue indicator on chapter cards in `MangaChaptersSection.tsx` displaying exact reading percentage (0–100%).
- **Smart Resume Labels**: Intelligent contextual button text (`Start Reading`, `Continue Ch. X`, `Re-read Ch. X`).
- **Dynamic Page Titles & Rich Previews**: Dynamic `usePageTitle` hook applied across all app routes and Reader; enriched `index.html` with canonical absolute OpenGraph/Twitter image tags and metadata for social link unfurls.
- **Stale State Remediation**: Used `currentPageRef` in `useReaderData` to prevent stale closure bugs during unmount progress syncing.
- **Reader Back Navigation**: Simplified back button to `navigate(-1)` to honor original entry history stack; eliminates ping-pong between reader and manga detail.
- **MangaDetail Hallmark Design Pass**: Removed red left-border wall on unread chapters, switched READ buttons to outline style, adaptive 2/3-column stats grid, tiered genre badges, synopsis Markdown stripping, pencil edit button removal.
- **CI Workflow Removal**: Deleted Firebase GitHub Actions auto-deploy workflows; hosting is now manual-only.

### Phase 25 ✅ Full Project Documentation (2026-09-12)
- **CHANGELOG.md**: Complete chronological changelog from `[0.1.0] - 2026-05-30` through `[Unreleased]` covering all 10 versions with detailed Added/Changed/Fixed/Removed/Security entries per version.
- **docs/PROJECT_STATUS.md**: Updated with Phase 24 full detail and Phase 25 documentation phase.
- **docs/FEATURES.md**: Removed stale "Not Yet Implemented" rows for Biometric Lock and WiFi/Charging gates (shipped in Phase 16).

---

## What Remains 🔲

| Feature | Priority |
|---------|----------|
| WebView fallback for Cloudflare sources | Medium |
| RAR/CBR archive support | Low |
| Local folder scan (bulk import from directory) | Low |
| Tablet multi-column reading layout | Low |
| Custom date format | Low |
| DNS-over-HTTPS, custom user agent | Low |
| Material You dynamic colours | Low |
| Auto-delete after read, split page spreads | Low |
| Background sync Android WorkManager | Low |
| Badge count on app icon (requires FCM) | Low |
| Tracker filter in library | Low |


---

## Known Setup Requirements ⚠️

### Must do before shipping
1. **Supabase SQL migrations** — run the `reading_progress` table creation (see FEATURES.md)

### Known code issues
- ~~Settings page is a monolithic 1000+ line file (`Settings.tsx`)~~ — FIXED (Phase 13, refactored into sub-pages).
- ~~Heatmap tracks downloads instead of reads~~ — FIXED (Phase 15, `/users/me/stats` aggregates `ReadingProgress`).
- ~~Reader.tsx was 1130 lines~~ — FIXED (Phase 19, refactored to 169 lines with extracted hooks).
- ~~backend routers were 1000+ lines~~ — FIXED (Phase 20, extracted business logic into `app/services/`).

---

## Architecture Summary

```
frontend/
  public/           Static assets, sitemap.xml, robots.txt
  src/
    pages/          React page components
    hooks/          Custom hooks (useDashboardData, useMangaDetail, useMangaTracker, useReaderNavigation, etc.)
    lib/            Zustand store, API client, local utilities
    components/     Shared & domain-specific UI components
  src-tauri/        Rust Tauri shell (desktop)
  android/          Capacitor Android project

backend/
  app/
    api/            FastAPI lightweight route handlers
    services/       Business logic services (library_service, manga_service, device_service, etc.)
    services/extensions/ Standalone .js extension scripts (mangadex, mangakatana, asurascans, etc.)
    models/         SQLAlchemy ORM models
```

## Tech Stack
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS, Framer Motion, Zustand (persist), TanStack Query v5
- **Backend**: FastAPI, SQLAlchemy async, SQLite/PostgreSQL, curl_cffi (Cloudflare bypass)
- **Desktop**: Tauri v2, Rust tokio, tauri-plugin-notification/autostart/dialog/fs
- **Android**: Capacitor 6, @capacitor/haptics, @capacitor/filesystem, @capacitor/local-notifications, custom Kotlin VolumeKeys plugin
- **Auth**: Supabase Auth (JWT) + API key header
- **Storage**: Supabase Storage (CBZ cloud) + IndexedDB (local CBZ/EPUB)
</content>
</invoke>