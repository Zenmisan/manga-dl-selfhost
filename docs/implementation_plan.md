# Implementation Plan: Multi-Sourcing & Image Descrambling

This plan outlines the specific files to be created/modified to implement Multi-Source templates (Madara, MangaThemesia), Astro hydration prop unwrapping, and automatic page image descrambling (both in the browser reader and backend downloader).

---

## Phase 1: Shared Javascript Utilities (Frontend)
We need to introduce helper methods in the frontend workspace for unwrapping Astro props and rendering scrambled canvas tiles.

* **Target File:** `frontend/src/lib/descramble.ts` (new file)
* **Tasks:**
  1. Implement `unwrapAstro(el: any): any` helper.
  2. Implement a client-side drawing utility `descrambleImage(img: HTMLImageElement, tiles: number[], cols: number, rows: number): HTMLCanvasElement` that splits the source image and re-assembles the tiles onto a 2D canvas.

---

## Phase 2: React Reader Component Integration (Frontend)
The reader page must automatically detect if a page image URL contains descrambling metadata inside its hash fragment (e.g. `#{"tiles":[...],"tileCols":4,"tileRows":5}`) and render a `<canvas>` (or convert the canvas to a blob/data URL) instead of a plain `<img>`.

* **Target File:** `frontend/src/pages/Reader.tsx`
* **Tasks:**
  1. Add a custom image loader component/hook that checks for `#{"tiles":...}` fragments in page URLs.
  2. If detected, load the image asynchronously, descramble it using `descrambleImage`, and render the canvas output.

---

## Phase 3: Generic JS Source Templates (Backend + Frontend)
We will declare the multi-source template scrapers and register them as built-in extensions so they are instantly accessible.

* **Target File:** `backend/app/api/sources.py`
* **Tasks:**
  1. Implement the standard scraper code blocks for `_MADARA_JS` and `_MANGATHEMESIA_JS` based on Keiyoushi template structures.
  2. Add new configurations to the `BUILT_IN_EXTENSIONS` mapping in the backend so users can choose them.
  3. Support loading these generic templates dynamically with target `baseUrl` parameters.

---

## Phase 4: Downloader Image Descrambler (Backend)
When downloading chapters for offline reading, the backend must save pages fully descrambled into the final `.cbz` file.

* **Target File:** `backend/app/core/downloader.py`
* **Tasks:**
  1. In `download_image()`, parse and strip any `#` hash fragment from the URL before requesting or extracting the extension.
  2. If the hash fragment contains descrambling parameters (`tiles`, `tileCols`, `tileRows`), decode the download payload as a Pillow `Image` object.
  3. Divide and reassemble the image tiles into their correct slots, saving the resulting clean image directly to the destination path.
