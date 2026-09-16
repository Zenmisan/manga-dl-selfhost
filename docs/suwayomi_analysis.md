# Suwayomi-Server Architecture & Feature Analysis

This report analyzes the extracted [Suwayomi-Server](file:///C:/Users/Zenmi/Documents/Coding%20Projrct/manga-dl/Suwayomi-Server-master) repository, comparing its features and architectural patterns with **manga-dl** to guide future native desktop improvements.

---

## 1. Architectural Differences

| Dimension | Suwayomi-Server | manga-dl |
| :--- | :--- | :--- |
| **Language & Runtime** | Kotlin / JVM (Java 21+) | React (Frontend) + FastAPI / Python (Backend) |
| **Desktop Wrapper** | Bundled JRE + ElectronJS launcher | Tauri v2 (Rust shell wrapper) |
| **Memory Footprint** | Large (JVM + Electron: ~300MB - 1GB+) | Extremely light (Tauri + FastAPI: ~50MB - 120MB) |
| **Extension Engine** | Runs native Android Tachiyomi APKs via an emulator layer (`AndroidCompat`) | Runs lightweight JS scrapers inside client-side Web Workers |
| **External Client Support** | Exposes REST APIs + OPDS v1.2 Feed | Exposes REST APIs + WebSocket progress stream |

---

## 2. Key Findings & Opportunities for manga-dl

### A. OPDS Feed Support (High Opportunity)
- **What it is:** Suwayomi exposes a standard **OPDS (Open Publication Distribution System) v1.2** feed at `/api/opds/v1.2`. This allows external reader applications (e.g., Panels on iOS, KOReader on e-ink devices) to browse and stream from the server.
- **Action Item:** We can easily implement an OPDS feed endpoint in our FastAPI backend (`backend/app/api/`) by generating compliant XML/Atom feeds from our local SQLite library database.

### B. Cloudflare Bypass via FlareSolverr (Medium Opportunity)
- **What it is:** Suwayomi integrates with **FlareSolverr** (a proxy server to bypass Cloudflare challenges) via config properties.
- **Action Item:** If `curl_cffi` fails on Cloudflare blocks, we can implement an optional configuration key `FLARESOLVERR_URL` in our backend settings, letting users route scraping requests through a FlareSolverr docker container.

### C. Native System Tray Menu
- **What it is:** Suwayomi's system tray (built using Java `SystemTray.kt` / `dorkbox`) only exposes `Open` and `Quit`.
- **Action Item:** Our Tauri system tray menu can be enhanced to expose quick controls:
  - Trigger Library Sync
  - Check Active Download Progress
  - Toggle Incognito Mode

### D. Android Compatibility Sandbox (`AndroidCompat`)
- **What it is:** Suwayomi includes a Gradle module `AndroidCompat` to mock Android SDK contexts, letting compiled Tachiyomi Kotlin extensions run on desktop platforms.
- **Action Item:** None. Our lightweight JS-in-Web-Workers engine (`ExtensionManager`) is far cleaner, uses fewer resources, and runs natively in PWAs without emulating Android.
