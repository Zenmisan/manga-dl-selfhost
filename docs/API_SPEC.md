# manga-dl API Specification
**Version 1.0.0** · 2026-05-30 · HADS 1.0.0

---

## AI READING INSTRUCTION
Read `[SPEC]` and `[BUG]` blocks for authoritative facts.
Read `[NOTE]` only if additional context is needed.

---

## 1. Authentication
**[SPEC]**
- **Mechanism**: Header-based stateless authentication.
- **Header Key**: `X-API-Key`
- **Enforcement**:
  - Applied globally to all `/api` routes via FastAPI dependencies.
  - Required only if `API_KEY` is defined in the backend environment/config.
- **Error Response**: `403 Forbidden` if header is missing or incorrect while `API_KEY` is set.
- **Fallthrough**: If `API_KEY` is `null` (default), all requests are permitted without authentication.

**[NOTE]**
The frontend client persists the API Key in Browser LocalStorage. The key is injected into outgoing requests via an Axios interceptor. This model allows for easy deployment behind a reverse proxy or as a standalone private instance.

## 2. Manga & Search API
**[SPEC]**
- **List Providers**: `GET /api/manga/providers`
  - Returns metadata and current `health` status for all registered sources.
- **Unified Search**: `GET /api/manga/search?q={query}&provider={id}&page={n}`
  - `q`: Search string (required, min 1 char).
  - `provider`: Optional ID (e.g., `mangadex`) to restrict search.
  - `page`: Pagination index (default: 1).
- **Manga Detail**: `GET /api/manga/{provider_id}/{manga_id}`
  - `{manga_id}`: Can be a UUID (MangaDex) or a URL slug (Asura).
  - Returns full metadata and an array of `chapters`.
- **Chapter Object**:
  ```json
  {
    "id": "string",
    "title": "string",
    "number": 0.0,
    "url": "string",
    "published_at": "string|null"
  }
  ```

**[NOTE]**
The `{manga_id}` path parameter is defined as a greedy path in FastAPI (`path` type) to accommodate providers that use hierarchical IDs like `series/name`. When searching all providers, the backend runs queries concurrently to minimize latency.

## 3. Download Management
**[SPEC]**
- **Enqueue Job**: `POST /api/downloads/queue`
  - **Payload**:
    ```json
    {
      "provider_id": "string",
      "manga_id": "string",
      "chapter_id": "string"
    }
    ```
  - **Behavior**: Blocking operation. Backend fetches manga metadata and page URLs *before* returning `download_id`.
- **Active Tasks**: `GET /api/downloads/active`
  - Returns current state of the memory-resident `DownloadQueue`.
- **History**: `GET /api/downloads/history`
  - Returns the last 100 persistent records from the database.
- **Job Statuses**: `queued`, `downloading`, `done`, `failed`.

**[NOTE]**
The `queue` endpoint is synchronous in its URL resolution but asynchronous in its execution. It will wait for the provider to return the list of image URLs before acknowledging the request with a `200 OK` and a `download_id`. If a chapter is paywalled or pages cannot be resolved, it returns `422 Unprocessable Entity`.

## 4. WebSocket Events
**[SPEC]**
- **Endpoint**: `/api/downloads/ws`
- **Direction**: Read-only (Server-to-Client).
- **Initialization**: Upon connection, server pushes a `state` event containing the current `active` list.
- **Event Types**:
  | Type | Trigger |
  |------|---------|
  | `state` | Immediate upon handshake |
  | `queued` | New job added to memory queue |
  | `started` | Worker begins downloading first page |
  | `progress`| Every page download success |
  | `completed`| Archive created or job failed |
- **Payload Structure**:
  ```json
  {
    "type": "string",
    "download": { "id": "uuid", "progress": 85, ... }
  }
  ```

**[NOTE]**
The WebSocket is designed for ephemeral progress tracking. It does not support persistence (if the browser refreshes, it re-syncs state via the initial message). Clients should not send commands over this socket; control actions like `cancel` or `pause` must use REST endpoints.

## 5. Library API
**[SPEC]**
- **Endpoint**: `GET /api/library`
- **Mechanism**: Real-time synchronous scan of `LIBRARY_PATH`.
- **Discovery Logic**:
  - Each first-level subdirectory is treated as a unique Manga Title.
  - Scans exclusively for `.cbz` files within these directories.
- **Response Format**: Array of `LibraryItem` objects.
  ```json
  {
    "title": "string",
    "files": ["string"]
  }
  ```
- **Sorting**: Results are sorted alphabetically by `title`.

**[NOTE]**
This endpoint is the "Ground Truth" for the frontend. It bypasses the database to ensure that if a user manually adds or deletes files from their storage, the change is reflected immediately without a sync task. Large libraries on mechanical drives may experience slight latency due to the synchronous nature of the disk I/O.
