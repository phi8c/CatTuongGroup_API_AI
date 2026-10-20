
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


from app.core.environment import get_backend_dir, resolve_env_file


BACKEND_DIR = get_backend_dir()
ENV_FILE = resolve_env_file()


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str | None = None

    # Supabase
    SUPABASE_URL: str | None = None
    SUPABASE_ANON_KEY: str | None = None

    # Microsoft Entra ID
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""
    AZURE_CLIENT_SECRET: str = ""

    # Azure AI Search
    AZURE_SEARCH_ENDPOINT: str | None = None
    AZURE_SEARCH_INDEX: str | None = None
    AZURE_SEARCH_KEY: str | None = None

    # SharePoint
    SHAREPOINT_SITE_ID: str = ""
    SHAREPOINT_DRIVE_ID: str = ""

    # Logic App
    LOGIC_APP_URL: str = ""

    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_API_VERSION: str = ""

    AZURE_OPENAI_REWRITE_DEPLOYMENT: str = "gpt-5.1"
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = ""

    # Project tracking
    PROJECT_TRACKING_SITE_NAME: str = ""
    PROJECT_TRACKING_LIBRARY_NAME: str = ""
    PROJECT_TRACKING_MODEL_ID: UUID | None = None

    # Azure Document Intelligence
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str = ""
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str = ""

    # Legal database
    LEGAL_DB_PATH: str = "./data/legal_vbpl.duckdb"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
