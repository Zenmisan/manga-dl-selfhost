# Manga OS Backend

FastAPI service handling cloud storage sync, legacy scraping proxy, and metadata enhancement.

## Tech Stack
- **Framework**: FastAPI (Python 3.14)
- **Database**: PostgreSQL (Supabase) via psycopg3
- **Network**: curl_cffi (Cloudflare bypass)
- **Processing**: Pillow (WebP compression, AI upscale foundation)

## Development Setup

Requires Python 3.14+

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run Local Server
```bash
uvicorn app.main:app --reload --port 8000
```

## Environment Variables
Create a `.env` file based on the config requirements:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `DATABASE_URL`
