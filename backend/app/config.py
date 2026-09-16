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
    RESEND_FROM_EMAIL: str = "manga-dl <onboarding@resend.dev>"  # swap for verified domain email in prod
    SUPPORT_EMAIL: str = "zenmisan@gmail.com"  # where support ticket notifications go
    
    # AniList OAuth (Authorization Code flow — backend exchanges code for token)
    ANILIST_CLIENT_ID: str | None = None
    ANILIST_CLIENT_SECRET: str | None = None
    # MAL OAuth — client secret required even for PKCE flows
    MAL_CLIENT_ID: str | None = None
    MAL_CLIENT_SECRET: str | None = None

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
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
