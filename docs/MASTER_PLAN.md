# manga-dl — Master Implementation Plan

Last updated: 2026-06-14

---

## PHASE A — Bug Fixes & Android Build (DONE ✅)

- [x] Fixed `MainActivity.java` — `registerPlugin` moved to `onCreate`, `getPlugin` by string name
- [x] Fixed `VolumeKeysPlugin.kt` — `JSObject()` instead of `null` in `notifyListeners`
- [x] Fixed bookmarks key `provider:provider` → `provider:mangaId`
- [x] Fixed MAL sync chapters read (was hardcoded 0)
- [x] Fixed ComicInfo.xml `xml.sax.saxutils.escape()` on all string fields
- [x] Fixed pipe-in-title URL encoding: btoa encode in MangaDetail, atob decode in Reader
- [x] Discord App ID confirmed real (`1515346416430485785`)
- [x] Supabase `manga-backups` bucket created by user

---

## PHASE B — Supabase Sync (DONE ✅)

- [x] `readTracking.ts` — syncs to `read_tracking` table on every write, pulls on app start
- [x] `categories.ts` — syncs to `user_categories` table on every write, pulls on app start
- [x] `mangaNotes.ts` — syncs to `manga_notes` table on every write, pulls on app start
- [x] `App.tsx` — calls all 3 sync functions on mount
- [x] `docs/supabase/migrations.sql` — all 3 tables + RLS policies documented
- [ ] **TODO**: Actually run `docs/supabase/migrations.sql` in Supabase SQL editor

---

## PHASE C — Landing Page + Auth Routing (DONE ✅)

- [x] C1. Route Restructure (LandingPage at `/`, Dashboard at `/r`)
- [x] C2. Auth State Wiring (Supabase session in `App.tsx`, user profile in Sidebar)
- [x] C3. Landing Page (`Landing.tsx` with Hero, Features, Platforms)
- [x] C4. SEO (`index.html` tags, `robots.txt`, `sitemap.xml`)

## PHASE D — Android UI Restructure (DONE ✅)

- [x] D1. Bottom Nav (Library, Updates, Search, Browse, More)
- [x] D2. More Page (`More.tsx` with Incognito, History, Stats, Settings)
- [x] D3. Library Improvements (Unread badges, 2-column, Categories, Batch select)
- [x] D4. MangaDetail Improvements (Hero cover, FAB, Read indicators)
- [x] D5. Browse Page Restructure (Sources/Extensions/Migrate tabs)
- [x] D6. Settings sub-pages (General, Reader, Library, Trackers, System)

- `frontend/public/sitemap.xml`

---

## PHASE D — Android UI Restructure (Mobile-first)

### D1. Bottom Navigation Restructure
Current (6 items, too crowded): Library · Search · Updates · Extensions · Downloads · Settings

New (5 items matching Tachiyomi pattern):
`Library · Updates · History · Browse · More`

- `More` opens a dedicated `MorePage` component (not a modal)
- Downloads, Settings, Stats, Categories accessible from More

### D2. More Page (`frontend/src/pages/More.tsx`)
New page at `/more`:
- Quick toggles section: Downloaded only, Incognito mode (with pill toggles)
- Links: Download queue (with count badge) · Categories · Statistics · Data & Storage · Settings · Help · About

### D3. Library Improvements (Dashboard.tsx)
- Unread chapter badge: top-left corner of cover card (red pill with count)
- 2-column default on mobile (already using gridColumns store value)
- Category tabs: horizontal scrollable pill tabs below header
- Empty state: `(˵•_•˵)` emoticon + "Your library is empty. Add manga from Browse."
- Long-press → batch select mode (already implemented)

### D4. MangaDetail Improvements
- Blurred cover as full-width hero background (~200px tall)
- Cover thumbnail overlaid bottom-left of hero
- Floating "Resume" / "Start" FAB pill button (red) bottom-right
- Chapter dot indicator: red dot = unread, grey dot = read

### D5. Browse Page Restructure (Sources.tsx)
- Tab bar: `Sources · Extensions · Migrate`
- Sources tab: grouped sections (Last Used, Pinned, by Language)
- Each source row: icon square + name + language + "Latest" link + pin toggle
- Extensions tab: "Update all" banner when updates pending, then Installed list

### D6. Settings — Sub-page Architecture
Replace current flat Settings page with categorized sub-pages:

**Settings index** (`/settings`):
- Appearance → theme, grid columns, AMOLED
- Reader → reading mode, tap zones, dual page, image scale, webtoon padding
- Library → categories, skip read chapters, auto-backup
- Downloads → download location, auto-download
- Tracking → AniList, MAL, Kitsu, MU, Shikimori, Bangumi links
- Sync → WiFi only, charging only gates
- Security & Privacy → biometric lock, incognito mode
- Data & Storage → backup/restore, cloud backup, clear cache
- Advanced → API key, custom backend URL
- About → version, GitHub, terms

Each sub-page is its own route: `/settings/appearance`, `/settings/reader`, etc.

### D7. Empty States
Add Tachiyomi-style empty states to:
- Updates page: `(˵•_•˵)` + "No recent updates"
- History page: `(˵•_•˵)` + "No reading history"
- Downloads page when empty
- Search before query entered

---

## PHASE E — Desktop UI (Tauri — our own design, not Tachiyomi)

### E1. Sidebar Enhancement
Current sidebar has all nav items. Add:
- [x] User avatar / Sign In section at very bottom (above Help)
- [x] Active indicator: left border accent (red) not just icon color
- [x] Collapsible sidebar (icon-only mode) for smaller windows

### E2. Desktop-specific Layout
- [x] Library: support 4-6 column grid (already have gridColumns)
- [x] MangaDetail: two-column layout on wide screens (cover+info left, chapters right)
- [x] Reader: keyboard shortcut overlay on first open
- [x] Settings: two-panel layout (category list left, content right) like macOS System Preferences

### E3. Window Chrome
- [x] Custom titlebar (Tauri) with drag region
- [x] Traffic light buttons (close/min/max) or standard Windows chrome
- [ ] Menu bar: File, Library, View, Help

---

## PHASE F — SEO & Marketing

### F1. Landing Page SEO (part of Phase C)
Already planned above.

### F2. Sitemap & robots.txt
```
/robots.txt → allow all, disallow /api
/sitemap.xml → /, /login, /register, /help, /download
```

### F3. OG Image
- Create `frontend/public/og-image.png` (1200×630)
- Dark background, red "M" logo, app name, tagline
- Used in og:image meta tag

---

## PHASE G — Known Remaining Code Issues

- [x] Manga metadata overrides (`manga-dl-meta-overrides`) still localStorage only (DONE — syncs to manga_overrides Supabase table)
- [ ] Source migration doesn't rename downloaded files on disk
- [x] Heatmap counts downloads not reads (DONE — endpoint aggregates from ReadingProgress table)
- [ ] Search shows source headers even with 0 results
- [ ] Search filter state resets on tab switch
- [ ] Public profile shows UUID (no display_name system)
- [ ] Tracker sync only for AniList + MAL (MU/Shiki/BGM no write API)
- [ ] Android WorkManager background sync (currently web-based 30min timer)
- [ ] RAR/CBR archive support not implemented
- [ ] WebView fallback for Cloudflare-protected sources

---

## PHASE H — Before Shipping Checklist

- [ ] Run `docs/supabase/migrations.sql` in Supabase SQL editor
- [ ] Create `manga-backups` Supabase storage bucket (DONE by user)
- [ ] Replace Discord App ID fake value (DONE — real ID confirmed)
- [ ] Generate OG image for landing page
- [ ] Test Android APK build end-to-end (after volume keys fix)
- [ ] Test desktop build (Tauri) on Windows + macOS
- [ ] Verify Supabase auth flows (email verify, login, register)
- [ ] Set VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY in GitHub secrets
- [ ] Add `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` to Firebase hosting env if applicable

---

## PHASE I — Multi-Device Native Access Control & Direct Delivery (DONE ✅)

- [x] Configure native wrappers and active sessions to bypass landing page on root path
- [x] Restrict download/library feature access strictly to `zenmisan@gmail.com`
- [x] Enable direct downloads from Supabase Storage instead of redirecting to GitHub
- [x] Correct tablet width grid layout card overlaps in Sources.tsx
- [x] Set display font to Anton and text font to Inter globally
- [x] Refactor first-time onboarding to trigger only upon reader open (persisted on local device across user accounts)
- [x] Redirect signed-out users back to the landing page instead of `/login`

---

## Implementation Order (recommended)

1. **Phase C** — Landing page + auth routing (highest user-facing impact)
2. **Phase D1–D3** — Android bottom nav + More page + Library improvements
3. **Phase D4–D6** — MangaDetail + Browse + Settings sub-pages
4. **Phase E** — Desktop layout improvements
5. **Phase F** — SEO/marketing meta
6. **Phase G** — Fix remaining code issues (low priority, mostly polish)
7. **Phase I** — Multi-Device Native Access Control & Direct Delivery (completed)
