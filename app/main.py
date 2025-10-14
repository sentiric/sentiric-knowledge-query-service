# sentiric-knowledge-query-service/app/main.py
from fastapi import FastAPI, status
from contextlib import asynccontextmanager
from app.core.logging import setup_logging
from app.core.config import settings
import structlog
# from qdrant_client import QdrantClient # İleride eklenecek

logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Knowledge Query Service başlatılıyor", 
                version=settings.SERVICE_VERSION, 
                env=settings.ENV,
                qdrant_url=settings.QDRANT_HTTP_URL)
    
    # TODO: Qdrant Client ve Embedding Model'i başlat
    # global QDRANT_CLIENT, EMBEDDING_MODEL
    
    yield
    
    logger.info("Knowledge Query Service kapatılıyor")

app = FastAPI(
    title="Sentiric Knowledge Query Service",
    description="RAG sorgu motoru (Okuma bacağı)",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan
)

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    # TODO: Qdrant'a basit bir ping atarak health check'i gerçekle
    # if QDRANT_CLIENT.get_health_status().ok():
    #     return {"status": "ok", "service": "knowledge-query"}
    
    return {"status": "ok", "service": "knowledge-query"}

# RPC'ler burada tanımlanacak (Query RPC'si)
# @app.post(settings.API_V1_STR + "/query")
# async def run_query(request: QueryRequest):
#    # 1. Query metnini vektörleştir
#    # 2. Qdrant'ta sorgula
#    # 3. Sonuçları döndür
#    pass