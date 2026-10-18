"""Central configuration. All secrets come from environment variables / backend/.env (never hard-coded)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "EchoCare"
    APP_VERSION: str = "5.0.0"
    ENV: str = "development"  # development | production

    # --- Database: MongoDB Atlas (primary). DB_BACKEND=auto -> atlas if MONGODB_URI set, else in-memory mock
    DB_BACKEND: str = "auto"  # auto | atlas | mock
    MONGODB_URI: str = ""
    MONGODB_DB_NAME: str = "EchoCare"

    # --- Auth
    SECRET_KEY: str = "change-me-in-env-please-use-a-long-random-string"
    ACCESS_TOKEN_MINUTES: int = 60 * 24 * 7
    ADMIN_EMAILS: str = ""  # comma separated; the very first registered user is also admin

    # --- Web
    FRONTEND_URL: str = "http://localhost:3000"
    EXTRA_CORS_ORIGINS: str = ""
    SERVE_FRONTEND: bool = True  # serve frontend/dist from FastAPI when it exists (single-service deploy)

    # --- AI providers (only Gemini + Tavily are used)
    GOOGLE_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    GEMINI_MODEL: str = ""
    EMBED_MODEL: str = "gemini-embedding-001"

    # --- Vector store (ChromaDB)
    CHROMA_DIR: str = str(BACKEND_DIR / "chroma_data")
    EMBED_DIM: int = 384

    # --- Uploads
    MAX_UPLOAD_MB: int = 12

    # --- Optional SMTP for OTP e-mails (if empty, OTP is returned in the API response in development ONLY)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    OTP_MINUTES: int = 10

    @property
    def cors_origins(self) -> list[str]:
        origins = {self.FRONTEND_URL.rstrip("/"), "http://localhost:3000", "http://127.0.0.1:3000",
                   "http://localhost:5173", "http://127.0.0.1:5173"}
        origins |= {o.strip().rstrip("/") for o in self.EXTRA_CORS_ORIGINS.split(",") if o.strip()}
        return sorted(origins)

    @property
    def admin_emails(self) -> set[str]:
        return {e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()}

    @property
    def use_mock_db(self) -> bool:
        if self.DB_BACKEND == "mock":
            return True
        if self.DB_BACKEND == "atlas":
            return False
        return not self.MONGODB_URI.strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
