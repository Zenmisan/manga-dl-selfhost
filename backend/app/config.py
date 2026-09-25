from pydantic_settings import BaseSettings
from pathlib import Path
from functools import lru_cache


from pydantic import field_validator
import json
from typing import Any


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./manga_dl.db"
    LIBRARY_PATH: str = str(Path.home() / "manga-library")
    CACHE_PATH: str = str(Path.home() / ".manga-dl-cache")
    MAX_CONCURRENT_DOWNLOADS: int = 3
    REQUEST_DELAY: float = 1.0  # seconds between requests to same host
    CORS_ORIGINS: Any = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://manga-dl.web.app",
        "https://manga-dl.firebaseapp.com",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://localhost",
        "capacitor://localhost",
    ]
    API_KEY: str | None = None
    RESEND_API_KEY: str | None = None
    RESEND_FROM_EMAIL: str = "manga-dl <onboarding@resend.dev>"
    SUPPORT_EMAIL: str = "zenmisan@gmail.com"  # where support ticket notifications go
    # Gmail SMTP (alternative to Resend — no custom domain needed)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None   # your Gmail address
    SMTP_PASS: str | None = None   # Google App Password (16 chars)
    
    # AniList OAuth (Authorization Code flow — backend exchanges code for token)
    ANILIST_CLIENT_ID: str | None = None
    ANILIST_CLIENT_SECRET: str | None = None
    # MAL OAuth — client secret required even for PKCE flows
    MAL_CLIENT_ID: str | None = None
    MAL_CLIENT_SECRET: str | None = None

    # Per-source auth cookies (injected by proxy when URL matches)
    COMIXTO_COOKIE: str | None = None
    COMIXTO_API_TOKEN: str | None = None  # _= query param required for chapter API endpoints

    # Supabase Storage Configuration
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None  # Required for backend bucket operations
    SUPABASE_JWT_SECRET: str | None = None
    SUPABASE_BUCKET: str = "manga-library"
    MAX_STORAGE_MB: int = 900          # Global hard cap (Supabase free = 1 GB)
    MAX_STORAGE_PER_USER_MB: int = 200  # Per-user eviction threshold

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def ensure_async_pg(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+psycopg://", 1)
        elif v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+psycopg://", 1)
        
        # psycopg3 uses 'sslmode' instead of 'ssl'
        if "ssl=require" in v:
            v = v.replace("ssl=require", "sslmode=require")
            
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        mandatory = [
            "https://localhost",
            "capacitor://localhost",
            "http://localhost",
            "http://localhost:5173",
            "http://localhost:3000",
            "tauri://localhost",
            "http://tauri.localhost",
        ]
        origins: list[str] = []
        if isinstance(v, str):
            v = v.strip()
            if v:
                if v.startswith("[") and v.endswith("]"):
                    try:
                        origins = json.loads(v)
                    except json.JSONDecodeError:
                        origins = [i.strip() for i in v.split(",") if i.strip()]
                else:
                    origins = [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, tuple, set)):
            origins = list(v)

        for m in mandatory:
            if m not in origins:
                origins.append(m)
        return origins

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
