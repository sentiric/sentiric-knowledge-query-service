# sentiric-knowledge-query-service/app/main.py
from fastapi import FastAPI, Response, status
from contextlib import asynccontextmanager
import structlog
import asyncio

from app.core.logging import setup_logging
from app.core.config import settings
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

logger = structlog.get_logger(__name__)

# Uygulamanın durumunu ve bağımlılıklarını tutacak global nesne
class AppState:
    def __init__(self):
        self.is_ready = False
        self.qdrant_client = None
        self.embedding_model = None

app_state = AppState()

async def load_dependencies():
    """Ağır bağımlılıkları (model, db istemcisi) yükler ve durumu günceller."""
    try:
        logger.info("Qdrant istemcisi başlatılıyor...")
        client = QdrantClient(url=settings.QDRANT_HTTP_URL, api_key=settings.QDRANT_API_KEY)
        client.get_collections() # Bağlantıyı test et
        app_state.qdrant_client = client
        logger.info("Qdrant bağlantısı başarılı.")

        logger.info(f"Embedding modeli yükleniyor: {settings.QDRANT_DB_EMBEDDING_MODEL_NAME}...")
        model = SentenceTransformer(settings.QDRANT_DB_EMBEDDING_MODEL_NAME)
        app_state.embedding_model = model
        logger.info("Embedding modeli başarıyla yüklendi.")

        app_state.is_ready = True # Her şey hazır, servis sağlıklı.
    except Exception as e:
        logger.critical("Başlangıç sırasında kritik bir bağımlılık yüklenemedi!", error=str(e), exc_info=True)
        app_state.is_ready = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Knowledge Query Service başlatılıyor", version=settings.SERVICE_VERSION, env=settings.ENV)
    
    # Model yüklemeyi arka planda başlat, sunucunun açılmasını engelleme.
    asyncio.create_task(load_dependencies())
    
    yield
    
    logger.info("Knowledge Query Service kapatılıyor")

app = FastAPI(
    title="Sentiric Knowledge Query Service",
    description="RAG sorgu motoru (Okuma bacağı).",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan
)

@app.get("/health", status_code=status.HTTP_200_OK, include_in_schema=False)
async def health_check():
    """Model ve DB bağlantısı hazır olduğunda 200, değilse 503 döner."""
    if app_state.is_ready:
        return {"status": "healthy"}
    else:
        return Response(
            content='{"status": "initializing"}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json"
        )