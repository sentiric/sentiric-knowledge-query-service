# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """
    Servis yapılandırmasını ortam değişkenlerinden veya .env dosyasından okur.
    """
    # Proje Meta Verileri
    PROJECT_NAME: str = "Sentiric Knowledge Query Service"
    API_V1_STR: str = "/api/v1"
    SERVICE_VERSION: str = "0.1.0"

    # Ortam Ayarları
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # Network ve Port Ayarları (Docker Compose ile senkronize edildi)
    KNOWLEDGE_QUERY_SERVICE_HTTP_PORT: int = 17020
    KNOWLEDGE_QUERY_SERVICE_GRPC_PORT: int = 17021 # Planlanan gRPC için
    KNOWLEDGE_QUERY_SERVICE_METRICS_PORT: int = 17022 # Planlanan Metrics için

    # Qdrant (Vector DB) Ayarları
    QDRANT_HTTP_URL: str
    QDRANT_GRPC_URL: Optional[str] = None
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_DB_COLLECTION_PREFIX: str = "sentiric_kb_"

    # Embedding Modeli Ayarları
    QDRANT_DB_EMBEDDING_MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    
    # Servise Özgü Ayarlar
    KNOWLEDGE_QUERY_DEFAULT_TOP_K: int = 3
    
    # Model indirme için cache dizini
    HF_HOME: str = "/app/model-cache"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()