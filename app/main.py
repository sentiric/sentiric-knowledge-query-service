# app/main.py
import asyncio
from contextlib import asynccontextmanager

import grpc
import structlog
from fastapi import FastAPI, HTTPException, Response, status
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.logging import setup_logging
from app import schemas

# Sentiric Contracts'tan gRPC stubs'larını import et
from sentiric.knowledge.v1 import query_pb2
from sentiric.knowledge.v1 import query_pb2_grpc

# Global uygulama durumu
class AppState:
    def __init__(self):
        self.is_ready = False
        self.qdrant_client: QdrantClient | None = None
        self.embedding_model: SentenceTransformer | None = None
        self.grpc_server: grpc.aio.Server | None = None

app_state = AppState()
logger = structlog.get_logger(__name__)

async def load_dependencies():
    """Ağır bağımlılıkları (model, db istemcisi) yükler ve durumu günceller."""
    try:
        logger.info("Qdrant istemcisi başlatılıyor...", url=settings.QDRANT_HTTP_URL)
        client = QdrantClient(url=settings.QDRANT_HTTP_URL, api_key=settings.QDRANT_API_KEY)
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

# --- YENİ: gRPC Sunucu Mantığı ---
class KnowledgeQueryServicer(query_pb2_grpc.KnowledgeQueryServiceServicer):
    """gRPC servis metotlarını implemente eden sınıf."""
    
    async def Query(self, request: query_pb2.QueryRequest, context: grpc.aio.ServicerContext) -> query_pb2.QueryResponse:
        if not app_state.is_ready:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details("Servis henüz başlatılıyor, lütfen daha sonra tekrar deneyin.")
            return query_pb2.QueryResponse()
        
        try:
            results = await _perform_query(
                tenant_id=request.tenant_id,
                query=request.query,
                top_k=request.top_k
            )
            
            grpc_results = [
                query_pb2.QueryResult(
                    content=res.content,
                    score=res.score,
                    source=res.source,
                    metadata=res.metadata
                ) for res in results
            ]
            return query_pb2.QueryResponse(results=grpc_results)
        
        except HTTPException as http_exc:
            if http_exc.status_code == status.HTTP_404_NOT_FOUND:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(http_exc.detail)
            else:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(http_exc.detail)
            return query_pb2.QueryResponse()
        except Exception as e:
            logger.error("gRPC Query işlenirken bir hata oluştu.", error=str(e), exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("İç sunucu hatası.")
            return query_pb2.QueryResponse()

async def serve_grpc():
    """gRPC sunucusunu başlatır ve yönetir."""
    server = grpc.aio.server()
    query_pb2_grpc.add_KnowledgeQueryServiceServicer_to_server(KnowledgeQueryServicer(), server)
    listen_addr = f'[::]:{settings.KNOWLEDGE_QUERY_SERVICE_GRPC_PORT}'
    server.add_insecure_port(listen_addr)
    app_state.grpc_server = server
    logger.info("gRPC sunucusu başlatılıyor...", address=listen_addr)
    await server.start()
    await server.wait_for_termination()
    logger.info("gRPC sunucusu kapatıldı.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Knowledge Query Service başlatılıyor", version=settings.SERVICE_VERSION, env=settings.ENV)
    
    asyncio.create_task(load_dependencies())
    
    yield
    
    logger.info("Knowledge Query Service kapatılıyor.")
    if app_state.qdrant_client:
        app_state.qdrant_client.close()
    if app_state.grpc_server:
        await app_state.grpc_server.stop(grace=1)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="RAG sorgu motoru (Okuma bacağı). HTTP ve gRPC arayüzleri sağlar.",
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

# --- REFAKTÖR EDİLMİŞ ÇEKİRDEK MANTIK ---
async def _perform_query(tenant_id: str, query: str, top_k: int) -> list[schemas.QueryResult]:
    """Hem HTTP hem de gRPC tarafından paylaşılan sorgu mantığı."""
    collection_name = f"{settings.QDRANT_DB_COLLECTION_PREFIX}{tenant_id}"
    log = logger.bind(tenant_id=tenant_id, collection=collection_name)

    if not app_state.embedding_model or not app_state.qdrant_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Model veya DB istemcisi hazır değil.")

    try:
        log.info("Sorgu vektörleştiriliyor...")
        query_vector = app_state.embedding_model.encode(query).tolist()

        log.info("Vektör veritabanında arama yapılıyor...", top_k=top_k)
        search_result = app_state.qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
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
        return results

    except UnexpectedResponse as e:
        if e.status_code == 404:
            log.warning("Koleksiyon bulunamadı.", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bilgi tabanı (koleksiyon: {collection_name}) bulunamadı."
            )
        log.error("Qdrant ile iletişimde hata oluştu.", http_status=e.status_code, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vektör veritabanıyla iletişimde bir sorun oluştu."
        )
    except Exception as e:
        log.error("Sorgu işlenirken genel bir hata oluştu.", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="İç sunucu hatası.")

@app.post(f"{settings.API_V1_STR}/query", response_model=schemas.QueryResponse, tags=["RAG"])
async def query_knowledge_base(request: schemas.QueryRequest):
    """Doğal dil sorgusunu vektörleştirir ve Qdrant'ta arama yapar."""
    if not app_state.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servis henüz başlatılıyor, lütfen daha sonra tekrar deneyin."
        )

    results = await _perform_query(
        tenant_id=request.tenant_id,
        query=request.query,
        top_k=request.top_k
    )
    return schemas.QueryResponse(results=results)