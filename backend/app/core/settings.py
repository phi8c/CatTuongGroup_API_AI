import os
from pathlib import Path
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = Path(os.getenv("CTG_ENV_FILE", ".env"))
if not ENV_FILE.is_absolute():
    ENV_FILE = BACKEND_DIR / ENV_FILE


class Settings(BaseSettings):
    DATABASE_URL: str | None = None

    SUPABASE_URL: str | None = None

    SUPABASE_ANON_KEY: str | None = None

    AZURE_TENANT_ID: str = ""

    AZURE_CLIENT_ID: str = ""

    AZURE_CLIENT_SECRET: str = ""

    AZURE_SEARCH_ENDPOINT: str | None = None

    AZURE_SEARCH_INDEX: str | None = None

    AZURE_SEARCH_KEY: str | None = None

    GEMINI_API_KEY: str = ""

    OPENAI_API_KEY: str = ""

    GROQ_API_KEY: str = ""

    GOOGLE_API_KEY: str = ""

    OPENROUTER_API_KEY: str = ""

    SHAREPOINT_SITE_ID: str = ""

    SHAREPOINT_DRIVE_ID: str =""

    LOGIC_APP_URL: str

    AZURE_OPENAI_ENDPOINT: str

    AZURE_OPENAI_API_KEY: str

    AZURE_OPENAI_API_VERSION: str

    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str

    MAX_FILE_REVIEW: int = 5

    MIN: int = 0

    PROJECT_TRACKING_SITE_NAME: str

    PROJECT_TRACKING_LIBRARY_NAME: str

    PROJECT_TRACKING_MODEL_ID: UUID

    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str

    AZURE_DOCUMENT_INTELLIGENCE_KEY: str

    LEGAL_DB_PATH: str = "./data/legal_vbpl.duckdb"

    EXECUTIVE_DATA_MODEL_ID: UUID

    MEETING_SYNC_USER_ID: str

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
