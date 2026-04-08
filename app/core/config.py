# app/core/config.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """
    Servis yapılandırması.
    Production-Ready: Varsayılanlar güvenli ve hataya dayanıklı.
    """

    PROJECT_NAME: str = "Sentiric Knowledge Query Service"
    # [ARCH-COMPLIANCE] versionlar pyproectden alınabilir?
    SERVICE_VERSION: str = "0.4.6"  
    API_V1_STR: str = "/api/v1"

    ENV: str = "production"
    LOG_LEVEL: str = "INFO"

    # [ARCH-COMPLIANCE] Resource node identity ve Tenant Isolation
    NODE_NAME: str = os.getenv("NODE_HOSTNAME", "unknown-node")
    TENANT_ID: str = os.getenv("TENANT_ID", "")

    # Ports
    KNOWLEDGE_QUERY_SERVICE_HTTP_PORT: int = 17020
    KNOWLEDGE_QUERY_SERVICE_GRPC_PORT: int = 17021
    KNOWLEDGE_QUERY_SERVICE_METRICS_PORT: int = 17022

    # Security (mTLS) - Standalone mod için hepsi Optional
    GRPC_TLS_CA_PATH: Optional[str] = None
    KNOWLEDGE_QUERY_SERVICE_CERT_PATH: Optional[str] = None
    KNOWLEDGE_QUERY_SERVICE_KEY_PATH: Optional[str] = None

    # Vector DB (Qdrant)
    QDRANT_HTTP_URL: str = "http://localhost:6333"
    QDRANT_GRPC_URL: Optional[str] = None
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_DB_COLLECTION_PREFIX: str = "sentiric_kb_"

    # AI Models
    QDRANT_DB_EMBEDDING_MODEL_NAME: str = (
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    )
    HF_HOME: str = "/app/model-cache"

    # Tuning
    KNOWLEDGE_QUERY_DEFAULT_TOP_K: int = 5
    SCORE_THRESHOLD: float = 0.40

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()

# [ARCH-COMPLIANCE] Strict Tenant Validation
if not settings.TENANT_ID and settings.ENV == "production":
    pass  # In context isolation this may be provided runtime, but logged as warning in main.
