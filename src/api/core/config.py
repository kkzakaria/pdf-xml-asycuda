"""
Configuration FastAPI pour l'API de conversion PDF RFCV → XML ASYCUDA
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Configuration de l'application API"""

    # API Configuration
    api_title: str = "API Convertisseur PDF RFCV → XML ASYCUDA"
    api_version: str = "1.0.0"
    api_description: str = "API REST pour convertir les documents RFCV PDF en XML ASYCUDA"

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # CORS Configuration
    cors_origins: List[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]

    # File Storage
    upload_dir: str = "uploads"
    output_dir: str = "output"
    max_upload_size: int = 50 * 1024 * 1024  # 50MB
    allowed_extensions: List[str] = [".pdf"]

    # Job Management
    job_expiry_hours: int = 24
    cleanup_interval_hours: int = 6

    # Batch Processing
    default_workers: int = 4
    max_workers: int = 8

    # Rate Limiting (optional)
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="API_",
        case_sensitive=False
    )


# Instance globale
settings = Settings()
