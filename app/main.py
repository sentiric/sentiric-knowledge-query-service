# app/main.py
import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Response, status
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.logging import setup_logging
from app import schemas

# Global uygulama durumu
class AppState:
    def __init__(self):
        self.is_ready = False
        self.qdrant_client: QdrantClient | None = None
        self.embedding_model: SentenceTransformer | None = None

app_state = AppState()
logger = structlog.get_logger(__name__)

async def load_dependencies():
    """Ağır bağımlılıkları (model, db istemcisi) yükler ve durumu günceller."""
    try:
        logger.info("Qdrant istemcisi başlatılıyor...", url=settings.QDRANT_HTTP_URL)
        client = QdrantClient(url=settings.QDRANT_HTTP_URL, api_key=settings.QDRANT_API_KEY)
        # Bağlantıyı test et
        client.get_collections()
        app_state.qdrant_client = client
        logger.info("Qdrant bağlantısı başarılı.")

        logger.info(f"Embedding modeli yükleniyor...", model=settings.QDRANT_DB_EMBEDDING_MODEL_NAME)
        model = SentenceTransformer(
            settings.QDRANT_DB_EMBEDDING_MODEL_NAME,
            cache_folder=settings.HF_HOME
        )
        app_state.embedding_model = model
        logger.info("Embedding modeli başarıyla yüklendi.")

        app_state.is_ready = True
        logger.info("Tüm bağımlılıklar yüklendi, servis hazır.")
    except Exception as e:
        logger.critical("Başlangıç sırasında kritik bir bağımlılık yüklenemedi!", error=str(e), exc_info=True)
        app_state.is_ready = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Knowledge Query Service başlatılıyor", version=settings.SERVICE_VERSION, env=settings.ENV)
    
    # Model ve DB yüklemeyi arka planda başlat, sunucunun açılmasını engelleme.
    asyncio.create_task(load_dependencies())
    
    yield
    
    logger.info("Knowledge Query Service kapatılıyor.")
    if app_state.qdrant_client:
        app_state.qdrant_client.close()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="RAG sorgu motoru (Okuma bacağı).",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan
)

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Monitoring"])
async def health_check():
    """Model ve DB bağlantısı hazır olduğunda 200, değilse 503 döner."""
    if app_state.is_ready:
        return {"status": "healthy"}
    else:
        return Response(
            content='{"status": "initializing"}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            headers={"Retry-After": "30"},
            media_type="application/json"
        )

@app.post(f"{settings.API_V1_STR}/query", response_model=schemas.QueryResponse, tags=["RAG"])
async def query_knowledge_base(request: schemas.QueryRequest):
    """Doğal dil sorgusunu vektörleştirir ve Qdrant'ta arama yapar."""
    if not app_state.is_ready or not app_state.embedding_model or not app_state.qdrant_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servis henüz başlatılıyor, lütfen daha sonra tekrar deneyin."
        )

    collection_name = f"{settings.QDRANT_DB_COLLECTION_PREFIX}{request.tenant_id}"
    log = logger.bind(tenant_id=request.tenant_id, collection=collection_name)

    try:
        log.info("Sorgu vektörleştiriliyor...")
        query_vector = app_state.embedding_model.encode(request.query).tolist()

        log.info("Vektör veritabanında arama yapılıyor...", top_k=request.top_k)
        search_result = app_state.qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=request.top_k,
            with_payload=True,
        )

        results = [
            schemas.QueryResult(
                content=hit.payload.get("content", ""),
                score=hit.score,
                source=hit.payload.get("source", "unknown"),
                metadata=hit.payload.get("metadata", {})
            )
            for hit in search_result
        ]
        
        log.info(f"{len(results)} sonuç bulundu.")
        return schemas.QueryResponse(results=results)

    except UnexpectedResponse as e:
        # Qdrant'tan HTTP hatalarını yakala
        if e.status_code == 404:
             log.warning("Koleksiyon bulunamadı.", error=str(e), collection=collection_name)
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bilgi tabanı (koleksiyon: {collection_name}) bulunamadı."
             )
        # Diğer Qdrant HTTP hatalarını 500 olarak döndür
        log.error("Qdrant ile iletişimde hata oluştu.", http_status=e.status_code, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vektör veritabanıyla iletişimde bir sorun oluştu."
        )
    
    except Exception as e:
        log.error("Sorgu işlenirken bir hata oluştu.", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="İç sunucu hatası."
        )