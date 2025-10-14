# sentiric-knowledge-query-service/app/main.py (YENİ VE TUTARLI HALİ)

from fastapi import FastAPI, status
from contextlib import asynccontextmanager
import structlog

from app.core.logging import setup_logging
from app.core.config import settings
from app.core.health import start_health_server, health_state # <-- YENİ IMPORT

# --- YENİ İMPORTLAR ---
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Başlangıç İşlemleri ---
    setup_logging()
    
    # Kendi gözlemlenebilirlik portunda health sunucusunu başlat
    # NOT: Bu portun Docker Compose'da EXPOSE edilmesi gerekiyor.
    start_health_server(port=17022) # <-- HARMONİK PORT KULLANIMI
    
    logger.info("Knowledge Query Service başlatılıyor", 
                version=settings.SERVICE_VERSION, 
                env=settings.ENV)
    
    try:
        # Qdrant Client'ı başlat ve bağlantıyı test et
        logger.info("Qdrant istemcisi başlatılıyor...")
        client = QdrantClient(url=settings.QDRANT_HTTP_URL, api_key=settings.QDRANT_API_KEY)
        client.get_collections()
        app.state.qdrant_client = client
        health_state.set_qdrant_ready(True) # <-- SAĞLIK DURUMUNU GÜNCELLE
        logger.info("Qdrant bağlantısı başarılı.")

        # Embedding Model'i başlat
        logger.info(f"Embedding modeli yükleniyor: {settings.QDRANT_DB_EMBEDDING_MODEL_NAME}...")
        model = SentenceTransformer(settings.QDRANT_DB_EMBEDDING_MODEL_NAME)
        app.state.embedding_model = model
        health_state.set_model_ready(True) # <-- SAĞLIK DURUMUNU GÜNCELLE
        logger.info("Embedding modeli başarıyla yüklendi.")

    except Exception as e:
        logger.critical("Başlangıç sırasında kritik bir hata oluştu!", error=str(e), exc_info=True)
        health_state.set_qdrant_ready(False)
        health_state.set_model_ready(False)

    yield
    
    # --- Kapanış İşlemleri ---
    logger.info("Knowledge Query Service kapatılıyor")

app = FastAPI(
    title="Sentiric Knowledge Query Service",
    description="RAG sorgu motoru (Okuma bacağı)",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan
)

# Ana API endpoint'i (artık /health burada değil)
@app.get("/", status_code=status.HTTP_200_OK, include_in_schema=False)
async def root():
    return {"message": "Sentiric Knowledge Query Service is running."}

# ... (gelecekteki /api/v1/query gibi diğer endpoint'ler buraya eklenecek) ...