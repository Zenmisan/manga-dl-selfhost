# Tauri In-App Updater

## How It Works

1. User clicks "Check for updates" in the More page
2. App calls GitHub Releases API (`https://api.github.com/repos/zenmisan/manga-dl/releases/latest`)
3. If a newer version exists, an update banner appears
4. User clicks "Download & Install":
   - **Desktop (Tauri):** `@tauri-apps/plugin-updater` downloads + installs silently, then relaunches
   - **Android:** Opens the `.apk` asset URL from GitHub Releases for manual install
   - **Web:** Opens the GitHub Releases page in a new tab

## Code Locations

| File | Role |
|---|---|
| `frontend/src/lib/updates.ts` | Version check logic, platform detection, install dispatch |
| `frontend/src/pages/More.tsx` | UI — "Check for updates" button + update banner |
| `frontend/src-tauri/tauri.conf.json` | Updater plugin config (pubkey + endpoint) |
| `frontend/src-tauri/Cargo.toml` | `tauri-plugin-updater` + `tauri-plugin-process` crates |
| `frontend/src-tauri/src/lib.rs` | Plugin registration |

## Version Comparison

`CURRENT_VERSION` is injected at build time from `package.json` via Vite:

```ts
// vite.config.ts
define: { __APP_VERSION__: JSON.stringify(pkg.version) }

// updates.ts
const CURRENT_VERSION = __APP_VERSION__
```

To release a new version: bump `version` in `frontend/package.json` before building.

## GitHub Releases Endpoint

The Tauri updater fetches:
```
https://github.com/zenmisan/manga-dl/releases/latest/download/latest.json
```

This file must exist as a release asset. CI generates and uploads it automatically when using `tauri action` in GitHub Actions (see `SIGNING.md`).

The `latest.json` format:
```json
{
  "version": "1.0.1",
  "notes": "Bug fixes and improvements",
  "pub_date": "2026-07-05T00:00:00Z",
  "platforms": {
    "windows-x86_64": {
      "url": "https://github.com/.../manga-dl_1.0.1_x64-setup.exe",
      "signature": "..."
    },
    "darwin-aarch64": {
      "url": "https://github.com/.../manga-dl_1.0.1_aarch64.dmg",
      "signature": "..."
    },
    "linux-x86_64": {
      "url": "https://github.com/.../manga-dl_1.0.1_amd64.AppImage",
      "signature": "..."
    }
  }
}
```

## Blocker Before Shipping

`pubkey` in `tauri.conf.json` is currently empty. The updater **will not work** until you generate a signing key pair — see `SIGNING.md`.
