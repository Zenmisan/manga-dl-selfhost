# Manga OS Development & Compilation Guide

This guide explains how to set up your local environment to compile the Manga OS ecosystem across Web, Desktop (Tauri), and Mobile (Capacitor/Android).

## 1. Prerequisites

Before starting, ensure you have the following core tools installed:
*   **Bun**: For fast JavaScript dependency management (`curl -fsSL https://bun.sh/install | bash`).
*   **Python 3.14+**: For the FastAPI backend sync server.

## 2. Web Compilation (Firebase)

The web version is the foundation for all other platforms.

```bash
# 1. Install dependencies
cd frontend
bun install

# 2. Run local development server
bun run dev

# 3. Build for production
bun run build
```

## 3. Desktop Compilation (Tauri: Windows, macOS, Linux)

Manga OS uses Tauri to wrap the React frontend into a lightweight, native desktop application with full file system access.

### Prerequisites for Desktop
*   **Rust**: You must install the Rust toolchain.
    ```bash
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
    ```
*   **Linux Dependencies**: If compiling on Linux, you need WebKit2GTK and build essentials:
    *   *Ubuntu/Debian*: `sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev`
    *   *Arch Linux*: `sudo pacman -S webkit2gtk-4.1 base-devel curl wget file xdotool openssl appmenu-gtk-module gtk3 libappindicator-gtk3 librsvg libvips`

### Running & Building
```bash
cd frontend

# Run the desktop app in development mode (hot-reloading)
bun run tauri dev

# Compile the final release binary (.exe, .dmg, or .AppImage/.deb)
bun run tauri build
```
The compiled binaries will be located in `frontend/src-tauri/target/release/bundle/`.

## 4. Android Compilation (Capacitor)

Manga OS uses Capacitor to wrap the React build into a native Android APK.

### Prerequisites for Android
*   **Java Development Kit (JDK) 17**: Android's build system (Gradle) is strictly tied to Java 17. Newer versions (like Java 21 or 26) will cause build failures.
    *   *Ubuntu/Debian*: `sudo apt install openjdk-17-jdk`
    *   *Arch Linux*: `sudo pacman -S jre17-openjdk jdk17-openjdk` (Set via `sudo archlinux-java set java-17-openjdk`)
*   **Android Studio**: Download and install [Android Studio](https://developer.android.com/studio). Ensure you install the Android SDK and Android SDK Command-line Tools via the SDK Manager inside Android Studio.

### Running & Building

Before opening Android Studio, you must build the web assets and sync them to the Android project folder:

```bash
cd frontend

# 1. Build the production React assets
bun run build

# 2. Sync the built assets into the Android native folder
bun run android:sync

# 3. Open the project in Android Studio
bun run android:open
```

Once Android Studio opens:
1. Wait for Gradle to finish syncing (watch the progress bar at the bottom right).
2. To run on an emulator or USB-connected phone, click the green **Play** button in the top toolbar.
3. To generate an APK for distribution, go to **Build > Build Bundle(s) / APK(s) > Build APK(s)** in the top menu. The APK will be generated in `frontend/android/app/build/outputs/apk/debug/`.
