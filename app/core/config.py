# sentiric-knowledge-query-service/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Sentiric Knowledge Query Service"
    API_V1_STR: str = "/api/v1"
    
    ENV: str = "production"
    LOG_LEVEL: str = "INFO"
    SERVICE_VERSION: str = "0.1.0"
    
    # Vector Database (Qdrant) Ayarları
    QDRANT_HTTP_URL: str
    QDRANT_GRPC_URL: Optional[str] = None
    QDRANT_API_KEY: Optional[str] = None
    
    # Qdrant'ta oluşturulacak koleksiyonların ön eki. Sonuna tenant_id eklenecek.
    QDRANT_DB_COLLECTION_PREFIX: str = "sentiric_kb_"
    
    # Metinleri vektöre çevirmek için kullanılacak model. İki servisin de aynı modeli kullanması şarttır.
    QDRANT_DB_EMBEDDING_MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    
    # Bu servise özgü ayarlar
    KNOWLEDGE_QUERY_DEFAULT_TOP_K: int = 3

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()