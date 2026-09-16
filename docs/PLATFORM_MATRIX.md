# Platform Feature Matrix

manga-dl runs on three platforms. All web features work on desktop and Android.
Native platform additions are listed per platform.

Legend: ✅ Done · 🔨 Partial · ⬜ Planned · ❌ Not possible · — Not applicable

Last updated: 2026-06-13

---

## 🌐 Web (PWA)

Web is the baseline. Everything that doesn't require native OS access is here.

| Feature | Status | Notes |
|---------|--------|-------|
| Full manga reader (LTR/RTL/webtoon/vertical pager) | ✅ | |
| Online streaming (no download required) | ✅ | |
| Library management (grid/list, sort, filter, batch select) | ✅ | |
| Dynamic grid columns (2–6) | ✅ | |
| Library categories + batch move | ✅ | |
| Search + browse sources (popular/latest/filters) | ✅ | |
| Download queue + pause/resume/cancel/retry | ✅ | |
| Reading history + date filter + search | ✅ | |
| Stats: time, pace, category, heatmap, goals | ✅ | |
| AniList / MAL / Kitsu / MangaUpdates / Shikimori / Bangumi | ✅ | |
| Tracker sync modal (status/score/dates) | ✅ | AniList + MAL |
| Reader brightness/contrast/filters | ✅ | CSS filter |
| Crop borders (pager + webtoon) | ✅ | |
| Webtoon side padding config | ✅ | |
| Dual-page spread | ✅ | |
| Tap zone layouts | ✅ | |
| Skip read chapters | ✅ | |
| Image prefetch | ✅ | |
| PWA offline mode | ✅ | vite-plugin-pwa + workbox |
| Web Share API (share chapter link) | ✅ | Clipboard fallback |
| Browser push notifications | ✅ | |
| Cloud backup / restore (Supabase) | ✅ | |
| Auto-backup (daily/weekly schedule) | ✅ | Browser download |
| Tachiyomi JSON + .tachibk import | ✅ | |
| Source migration UI | ✅ | |
| EPUB import + reading | ✅ | JSZip + OPF spine |
| Metadata edit (title/cover/description) | ✅ | |
| Per-manga notification mute | ✅ | |
| Extension install/uninstall/enable/disable/update | ✅ | |
| Incognito mode | ✅ | |
| Reading goals | ✅ | |
| Manga notes + rating | ✅ | |
| Library categories | ✅ | |
| Chapter bookmarks + scanlator filter | ✅ | |
| Unread badge + download badge | ✅ | |
| Public profile page | ✅ | |
| Dynamic source filters (MangaDex) | ✅ | |
| Auto-sync subscribed manga (30 min poll) | ✅ | Web/Android; Tauri uses Rust task |
| Background chapter sync | ❌ | No persistent background on web |
| Full filesystem access (custom path) | ❌ | Browser sandboxed |
| Discord Rich Presence | ❌ | No IPC to Discord client |
| Volume hardware keys | ❌ | Browser intercepts volume |
| Biometric lock | ❌ | WebAuthn possible future |
| System tray | ❌ | — |

---

## 🖥️ Desktop (Tauri v2)

All web features plus native OS capabilities.

| Feature | Status | Notes |
|---------|--------|-------|
| All web features | ✅ | |
| Full filesystem access | ✅ | tauri-plugin-fs |
| Custom download location | ✅ | Folder picker; shown in Settings → Desktop |
| Reveal in file manager | ✅ | Nautilus/Finder/Explorer |
| System tray (hide to tray on close) | ✅ | |
| Background chapter sync (Rust task) | ✅ | Configurable 15/30/60/120 min |
| OS notifications (new chapters) | ✅ | tauri-plugin-notification |
| Auto-launch on startup | ✅ | tauri-plugin-autostart |
| In-app update checker | ✅ | GitHub releases API |
| Drag-and-drop CBZ/EPUB import | ✅ | tauri://drag-drop event |
| Discord Rich Presence | ✅ | discord-rich-presence Rust crate |
| Volume key navigation | ✅ | Global keyboard events |
| Biometric (OS keychain lock) | ⬜ | Windows Hello / macOS Touch ID |
| Window remember size/position | ⬜ | |

---

## 📱 Android (Capacitor)

All web features plus native Android capabilities.

| Feature | Status | Notes |
|---------|--------|-------|
| All web features | ✅ | |
| Volume key page navigation | ✅ | Kotlin VolumeKeysPlugin + dispatchKeyEvent |
| Hardware back button | ✅ | App.addListener('backButton') in Reader/Detail/Dashboard |
| Keep screen on while reading | ✅ | @capacitor-community/keep-awake |
| Status bar colour sync (ambilight) | ✅ | @capacitor/status-bar setBackgroundColor |
| Haptic feedback on page turn | ✅ | @capacitor/haptics ImpactStyle.Light (configurable) |
| Save chapter to device storage | ✅ | @capacitor/filesystem → Documents/manga-dl/ |
| Download completion notification | ✅ | @capacitor/local-notifications |
| Auto-sync (frontend poll) | ✅ | Calls /manga/sync every 30 min |
| Biometric / PIN lock | ⬜ | @capacitor-community/biometric-auth |
| Secure screen (block screenshots) | ⬜ | FLAG_SECURE via native plugin |
| Push notifications (FCM) | ⬜ | @capacitor/push-notifications + Firebase |
| Background sync (WorkManager) | ⬜ | @capacitor/background-task |
| Badge count on app icon | ⬜ | @capacitor/badge (requires FCM) |
| Material You dynamic colours | ⬜ | Android 12+ DynamicColors |
| Discord Rich Presence | ❌ | Discord mobile doesn't expose RPC |

---

## Remaining Platform Work

### Desktop
- Biometric lock (Windows Hello / macOS Touch ID)
- Window state persistence

### Android
- Biometric / PIN lock
- Background sync (WorkManager — currently needs app open)
- FCM push notifications + badge count
- Secure screen (FLAG_SECURE)
- Material You theming

### Both
- WiFi-only / charging-only gates for sync + downloads
- WebView fallback for Cloudflare-protected sources
</content>
</invoke>