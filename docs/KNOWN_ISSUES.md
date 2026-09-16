# Known Issues & Limitations

Last updated: 2026-07-22

---

## 🔴 Critical / Requires Setup Before Shipping

### Supabase Production DB — missing columns/tables
Full migration script at `docs/supabase/migrations.sql`. Run in Supabase SQL Editor:
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
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (user_id, provider, manga_id, chapter_id)
);

-- Read tracking (chapter-level read state, synced by readTracking.ts)
CREATE TABLE IF NOT EXISTS read_tracking (
  user_id     VARCHAR NOT NULL,
  provider    VARCHAR NOT NULL,
  manga_id    VARCHAR NOT NULL,
  chapter_ids JSONB NOT NULL DEFAULT '[]',
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, provider, manga_id)
);

-- Category assignments (synced by categories.ts)
CREATE TABLE IF NOT EXISTS user_categories (
  user_id           VARCHAR NOT NULL PRIMARY KEY,
  custom_categories JSONB NOT NULL DEFAULT '[]',
  manga_assignments JSONB NOT NULL DEFAULT '{}',
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Manga notes + ratings (synced by mangaNotes.ts)
CREATE TABLE IF NOT EXISTS manga_notes (
  user_id    VARCHAR NOT NULL,
  provider   VARCHAR NOT NULL,
  manga_id   VARCHAR NOT NULL,
  note       TEXT NOT NULL DEFAULT '',
  rating     INTEGER NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, provider, manga_id)
);
```
Enable RLS on all three new tables — see `docs/supabase/migrations.sql` for policies.

---

## 🟠 Functional Bugs

~~### Android: every API call blocked (CORS)~~ **FIXED** — Added `https://localhost` and `capacitor://localhost` to `CORS_ORIGINS` in `backend/app/config.py`. Capacitor with `androidScheme: 'https'` sets WebView origin to `https://localhost`.

~~### Android: HTTP to LAN backend blocked~~ **FIXED** — `android/app/src/main/res/xml/network_security_config.xml` used invalid CIDR notation in `<domain>` elements (silently no-op). Replaced with `<base-config cleartextTrafficPermitted="true">`.

~~### Backend unreachable banner never dismisses~~ **FIXED** — Banner now auto-dismisses after 30s (via `setBannerDismissed(true)` on animation complete) and has a working close button. Resets when backend recovers.

~~### Blank page at `/r` on first visit~~ **FIXED** — Routing race condition resolved; session check completes before rendering the app shell.

~~### Onboarding skipped for fresh web users~~ **FIXED** — First-visit onboarding now triggers correctly for unauthenticated users entering reader mode.

~~### `manga-dl-bookmarks` key uses wrong compound key~~ **FIXED** — `MangaDetail.tsx:71`

~~### MAL sync sends chapter ID string, not chapter number~~ **FIXED** — `backend/app/api/auth.py` + `MangaDetail.tsx`

~~### `|` in manga title breaks `/read/online/` URL encoding~~ **FIXED** — param is now btoa-encoded; Reader uses `atob` decode

~~### Sources.tsx JSX nesting error (tab restructure)~~ **FIXED** — extensions tab `<div>` and conditional were unclosed; fixed closing structure

~~### MangaDex: chapter titles returning raw UUIDs~~ **FIXED** — Updated `mangadex.js` and `useMangaDetail.ts` fallback logic to format `Chapter X: Title` or `Chapter X` instead of raw UUIDs.

~~### MangaKatana: blank title and broken Popular/Latest lists~~ **FIXED** — Updated title selector matching and repaired `/manga` (popular) & `/latest` (latest) scrapers in `mangakatana.js`.

~~### Android: Biometric App Lock infinite re-prompt loop~~ **FIXED** — Added session unlock guard (`isUnlockedRef`) in `App.tsx` preventing re-triggering prompt on window focus/resume.

~~### Public Library: 403 Forbidden for non-admin users~~ **FIXED** — Opened `library.py` endpoints so all authenticated public users can manage and read their downloaded manga.

~~### Reader: Mobile navbar overlap & missing ESC exit shortcut~~ **FIXED** — Hidden app bottom navbar during `/read/` routes, added `ESC` shortcut in `useReaderKeybindings.ts`, and fixed "Mark All Read" button overlap on mobile viewports.

---

## 🟡 UX / Sync Gaps

~~### Read tracking is localStorage-only~~ **FIXED** — `readTracking.ts` syncs to `read_tracking` Supabase table

~~### Manga categories are localStorage-only~~ **FIXED** — `categories.ts` syncs to `user_categories` Supabase table

~~### Manga notes / rating are localStorage-only~~ **FIXED** — `mangaNotes.ts` syncs to `manga_notes` Supabase table

~~### Manga metadata overrides are localStorage-only~~ **FIXED** — `metaOverrides.ts` syncs to `manga_overrides` Supabase table

### Auto-backup (web) triggers browser download prompt
- **File:** `frontend/src/pages/Settings.tsx` → auto-backup useEffect
- **Issue:** Fires `a.click()` to download JSON, which pops a save dialog. Silent background backup not possible on web.
- **Acceptable:** Document behaviour in Settings UI. Cloud backup (Supabase) is the silent alternative.

---

## 🟡 Extension Limitations

### Keiyoushi index is Android APK metadata — no JS sources
- **Issue:** Extension install succeeds (metadata stored) but sources can't execute JS. Built-in providers (MangaDex, MangaKatana, etc.) delegate to the backend and work correctly.
- **Workaround:** Extensions act as "preferences" for which sources to show. Actual data flows through backend providers.

### Source migration doesn't migrate downloaded files
- **File:** `backend/app/api/manga.py` → `migrate_manga_source`
- **Issue:** Migrating a manga updates the DB record but existing CBZ files remain under the old path/title. Re-downloading is required.
- **Fix:** Rename the download directory for the manga on the filesystem as part of migration.

---

## 🟢 Minor / Low Priority

### Category tabs in Dashboard don't persist across reload
- **Issue:** `activeCategory` resets to `null` on reload.
- **Fix:** Persist in URL param (`?category=Reading`) or `sessionStorage`.

~~### Heatmap uses download date, not read date~~ **FIXED** — `/users/me/stats` endpoint now aggregates `ReadingProgress` data to show actual reading activity.

~~### Public profile shows UUID as display name~~ **MITIGATED** — own profile shows email username prefix; others show `Reader #XXXXXXXX`. Full fix requires `display_name` column in backend.

### Search grouped results show header for zero-result providers
- **File:** `frontend/src/pages/Search.tsx`
- **Issue:** Headers render even when provider returns 0 results. Mostly invisible but wastes space.
- **Fix:** Add `results.length > 0` guard before rendering provider group.

### Dynamic filter state resets on tab switch
- **File:** `frontend/src/pages/Search.tsx`
- **Issue:** `activeFilters` local state resets when switching Popular → Latest → Popular.
- **Fix:** Move to Zustand store or `useRef`.

### `vite-plugin-pwa` dev mode disabled
- **Issue:** Service worker not registered in dev. PWA features only work in production build.
- **Expected.** Run `bun run build && bun run preview` to test PWA.

### `tauri-plugin-autostart` may not compile on all Linux distros
- **Issue:** Requires platform autostart APIs. May fail on minimal setups.
- **Fix:** Gate behind `[target.'cfg(target_os = "linux")'.dependencies]` if needed.

### Tracker sync only works for AniList + MAL
- **File:** `frontend/src/pages/MangaDetail.tsx` → `showSyncModal`
- **Issue:** Kitsu/MangaUpdates/Shikimori/Bangumi have no backend write-API integration.
- **Mitigated:** Settings UI now shows "Read-only / No write API" and "Token storage only · No auto-sync" badges on these sections so users aren't confused.
- **Fix:** Add sync handlers for MU/Shiki/BGM when their APIs support status+score writes.

---

## 📋 Platform Gaps (see PLATFORM_MATRIX.md)

| Feature | Web | Desktop | Android |
|---------|-----|---------|---------|
| Background sync (persistent) | ❌ | ✅ Rust task | ⬜ WorkManager |
| Biometric lock | ❌ | ⬜ | ⬜ |
| Discord Rich Presence | ❌ | ✅ | ❌ |
| Volume keys | ❌ (browser) | ✅ keyboard | ✅ Kotlin plugin |
| Filesystem (custom path) | ❌ | ✅ | ✅ Documents/ |
| Push notifications | ✅ Web Push | ✅ OS notif | ⬜ FCM needed |
| Download notification | ❌ | ❌ | ✅ local-notifications |
</content>
</invoke>