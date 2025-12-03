# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

class Settings(BaseSettings):
    """
    Servis yapılandırmasını yönetir.
    Production-Ready kuralı: Varsayılan değerler 'fail-safe' olmalıdır.
    """
    # Meta
    PROJECT_NAME: str = "Sentiric Knowledge Query Service"
    SERVICE_VERSION: str = "1.0.0-prod"
    API_V1_STR: str = "/api/v1"
    
    # Environment
    ENV: str = "production"
    LOG_LEVEL: str = "INFO"

    # Ports
    KNOWLEDGE_QUERY_SERVICE_HTTP_PORT: int = 17020
    KNOWLEDGE_QUERY_SERVICE_GRPC_PORT: int = 17021
    KNOWLEDGE_QUERY_SERVICE_METRICS_PORT: int = 17022

    # Security (mTLS) - Opsiyonel hale getirildi (Standalone mod için)
    GRPC_TLS_CA_PATH: Optional[str] = None
    KNOWLEDGE_QUERY_SERVICE_CERT_PATH: Optional[str] = None
    KNOWLEDGE_QUERY_SERVICE_KEY_PATH: Optional[str] = None

    # Vector DB (Qdrant)
    QDRANT_HTTP_URL: str = "http://localhost:6333"
    QDRANT_GRPC_URL: Optional[str] = None
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_DB_COLLECTION_PREFIX: str = "sentiric_kb_"

    # AI Models
    # Bu model Production için dengeli (Hız/Kalite) bir seçimdir.
    QDRANT_DB_EMBEDDING_MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    HF_HOME: str = "/app/model-cache"
    
    # Tuning
    KNOWLEDGE_QUERY_DEFAULT_TOP_K: int = 5
    SCORE_THRESHOLD: float = 0.40 # Bu skorun altındaki sonuçlar elenir (Noise reduction)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()