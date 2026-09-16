# manga-dl (self-hosted)

A self-hosted manga reader with download management, tracker sync, and browser extension support.

This is the self-hosted backend. Auth is a simple API key (or open mode for trusted networks). Supabase and Firebase are optional — leave those env vars unset and the backend runs with API-key-only auth.

---

## Quick Start (Docker)

```bash
cp .env.example .env
# Edit .env — set API_KEY at minimum
docker compose up -d
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

---

## Configuration

Copy `.env.example` to `.env` and fill in values:

| Variable | Required | Default | Description |
|---|---|---|---|
| `API_KEY` | No | *(open mode)* | Secret key for all API requests. Leave blank to disable auth. |
| `LIBRARY_PATH` | No | `/data/manga-library` | Where downloaded manga is stored on the server. |
| `DATABASE_URL` | No | SQLite in `/data` | SQLite (default) or PostgreSQL connection string. |
| `MAX_CONCURRENT_DOWNLOADS` | No | `3` | Parallel chapter downloads. |
| `REQUEST_DELAY` | No | `1.0` | Seconds between requests to the same source. |
| `CORS_ORIGINS` | No | localhost ports | Comma-separated list of allowed frontend origins. |
| `ANILIST_CLIENT_ID` | No | — | AniList OAuth app ID (for tracker sync). |
| `ANILIST_CLIENT_SECRET` | No | — | AniList OAuth secret. |
| `MAL_CLIENT_ID` | No | — | MyAnimeList OAuth app ID. |
| `MAL_CLIENT_SECRET` | No | — | MyAnimeList OAuth secret. |

### API Key auth

When `API_KEY` is set, every request must include it as either:

- Header: `X-API-Key: your-key`
- Query param: `?api_key=your-key`

The frontend reads `VITE_API_URL` at build time and prompts for the key on first visit, storing it in `localStorage`.

---

## Running without Docker

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env  # edit as needed
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
bun install
VITE_API_URL=http://localhost:8000/api bun run build
# serve dist/ with any static server
```

---

## Tracker Sync (AniList / MAL)

1. Create an OAuth app on [AniList](https://anilist.co/settings/developer) or [MyAnimeList](https://myanimelist.net/apiconfig).
2. Set the redirect URI to `http://your-host/api/auth/anilist/callback` (or `/api/auth/mal/callback`).
3. Add the client ID/secret to `.env` and restart.

---

## Manga Sources

Sources are browser extensions installed via the Sources page in the app. Built-in sources include MangaDex, AsuraScans, FlameScans, and 30+ manga sources. Web novel sources (Royal Road, Scribble Hub, LightNovelWorld, WuxiaWorld) are also built-in. Community sources can be added via custom repository URLs.

---

## Data

Volumes defined in `docker-compose.yml`:

- `manga_library` — downloaded chapter files
- `manga_db` — SQLite database

To back up: `docker compose stop && tar -czf backup.tar.gz $(docker volume inspect --format '{{.Mountpoint}}' manga-dl-selfhost_manga_library) $(docker volume inspect --format '{{.Mountpoint}}' manga-dl-selfhost_manga_db)`

---

## FAQ

**Q: How do I reset the API key?**
Update `API_KEY` in `.env` and restart (`docker compose restart backend`). Update the key in the app's Settings page.

**Q: Can I use PostgreSQL instead of SQLite?**
Yes — set `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname` in `.env`.

**Q: The frontend can't reach the backend.**
Make sure `VITE_API_URL` points to your backend's public address, not `localhost`, when building for remote access. Rebuild the frontend container after changing it: `docker compose build frontend && docker compose up -d frontend`.

**Q: Where are my manga files?**
On the host at the Docker volume mountpoint: `docker volume inspect manga-dl-selfhost_manga_library`.
