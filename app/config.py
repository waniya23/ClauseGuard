# app/config.py

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # App info
    APP_NAME: str = "ClauseGuard"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # API Keys
    GROQ_API_KEY: str = ""

    # File upload settings
    MAX_FILE_SIZE_MB: int = 10
    UPLOAD_DIR: str = "uploads"

    # Vector store settings
    VECTOR_COLLECTION_NAME: str = "clauseguard_docs"

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global instance 
settings = Settings()