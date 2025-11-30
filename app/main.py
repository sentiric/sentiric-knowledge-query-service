# app/main.py
import asyncio
from pathlib import Path
import time
from contextlib import asynccontextmanager
import importlib.metadata

import grpc
import structlog
from fastapi import FastAPI, HTTPException, Response, status, Request
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.logging import setup_logging
from app.core import metrics
from app import schemas

from sentiric.knowledge.v1 import query_pb2, query_pb2_grpc

class AppState:
    def __init__(self):
        self.is_ready = False
        self.qdrant_client: QdrantClient | None = None
        self.embedding_model: SentenceTransformer | None = None
        self.grpc_server: grpc.aio.Server | None = None

app_state = AppState()
logger = structlog.get_logger(__name__)

async def load_dependencies():
    """Ağır bağımlılıkları yükler ve durumu günceller."""
    try:
        # --- DIAGNOSTICS START ---
        try:
            version = importlib.metadata.version("qdrant-client")
            logger.info(f"📦 Installed Qdrant Client Version: {version}")
        except Exception:
            logger.warning("Could not determine Qdrant Client version via metadata.")
        # --- DIAGNOSTICS END ---

        logger.info("Qdrant istemcisi başlatılıyor...", url=settings.QDRANT_HTTP_URL)
        
        # Sync Client
        client = QdrantClient(url=settings.QDRANT_HTTP_URL, api_key=settings.QDRANT_API_KEY)
        
        # --- INTROSPECTION START ---
        # Client'ın metotlarını kontrol et
        available_methods = dir(client)
        has_search = "search" in available_methods
        has_query_points = "query_points" in available_methods
        
        logger.info(f"🔍 Qdrant Client Introspection: Has 'search'={has_search}, Has 'query_points'={has_query_points}")
        
        if not has_search:
            logger.error("CRITICAL: 'search' method missing from QdrantClient! Dumping partial attributes:", attributes=available_methods[:20])
        # --- INTROSPECTION END ---

        # Bağlantı testi
        client.get_collections()
        
        app_state.qdrant_client = client
        logger.info("Qdrant bağlantısı başarılı (Sync Client).")

        logger.info(f"Embedding modeli yükleniyor...", model=settings.QDRANT_DB_EMBEDDING_MODEL_NAME)
        model = await asyncio.to_thread(
            SentenceTransformer,
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

# ... (gRPC Interceptor ve Servicer aynı kalıyor) ...
class MetricsInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        start_time = time.perf_counter()
        method_name = handler_call_details.method.split('/')[-1]
        metrics.REQUESTS_IN_PROGRESS.labels(method='grpc').inc()
        status_code = grpc.StatusCode.OK
        try:
            response = await continuation(handler_call_details)
            return response
        except grpc.RpcError as e:
            status_code = e.code()
            raise
        finally:
            latency = time.perf_counter() - start_time
            metrics.REQUEST_LATENCY_SECONDS.labels(method='grpc').observe(latency)
            metrics.REQUESTS_TOTAL.labels(method='grpc', status_code=status_code.name).inc()
            metrics.REQUESTS_IN_PROGRESS.labels(method='grpc').dec()

class KnowledgeQueryServicer(query_pb2_grpc.KnowledgeQueryServiceServicer):
    async def Query(self, request: query_pb2.QueryRequest, context: grpc.aio.ServicerContext) -> query_pb2.QueryResponse:
        if not app_state.is_ready:
            await context.abort(grpc.StatusCode.UNAVAILABLE, "Servis henüz başlatılıyor.")
        try:
            results = await _perform_query(
                tenant_id=request.tenant_id,
                query=request.query,
                top_k=request.top_k if request.top_k > 0 else settings.KNOWLEDGE_QUERY_DEFAULT_TOP_K,
            )
            grpc_results = [
                query_pb2.QueryResult(content=r.content, score=r.score, source=r.source, metadata=r.metadata)
                for r in results
            ]
            return query_pb2.QueryResponse(results=grpc_results)
        except HTTPException as e:
            if e.status_code == 404:
                await context.abort(grpc.StatusCode.NOT_FOUND, e.detail)
            else:
                await context.abort(grpc.StatusCode.INTERNAL, e.detail)
        except Exception as e:
            logger.error("gRPC Query hatası", error=str(e), exc_info=True)
            await context.abort(grpc.StatusCode.INTERNAL, "İç sunucu hatası.")

async def serve_grpc():
    server = grpc.aio.server(interceptors=[MetricsInterceptor()])
    query_pb2_grpc.add_KnowledgeQueryServiceServicer_to_server(KnowledgeQueryServicer(), server)
    try:
        private_key = Path(settings.KNOWLEDGE_QUERY_SERVICE_KEY_PATH).read_bytes()
        certificate_chain = Path(settings.KNOWLEDGE_QUERY_SERVICE_CERT_PATH).read_bytes()
        ca_cert = Path(settings.GRPC_TLS_CA_PATH).read_bytes()
        server_credentials = grpc.ssl_server_credentials(
            private_key_certificate_chain_pairs=[(private_key, certificate_chain)],
            root_certificates=ca_cert,
            require_client_auth=True
        )
        listen_addr = f'[::]:{settings.KNOWLEDGE_QUERY_SERVICE_GRPC_PORT}'
        server.add_secure_port(listen_addr, server_credentials)
        logger.info("Güvenli (mTLS) gRPC sunucusu başlatılıyor...", address=listen_addr)
    except FileNotFoundError:
        logger.warning("Sertifika dosyaları bulunamadı, güvensiz gRPC portu kullanılıyor.")
        listen_addr = f'[::]:{settings.KNOWLEDGE_QUERY_SERVICE_GRPC_PORT}'
        server.add_insecure_port(listen_addr)
    app_state.grpc_server = server
    await server.start()
    await server.wait_for_termination()

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    metrics.SERVICE_INFO.info({'version': settings.SERVICE_VERSION})
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
    description="RAG sorgu motoru (Okuma bacağı).",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan
)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    metrics.REQUESTS_IN_PROGRESS.labels(method='http').inc()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        latency = time.perf_counter() - start_time
        metrics.REQUEST_LATENCY_SECONDS.labels(method='http').observe(latency)
        metrics.REQUESTS_TOTAL.labels(method='http', status_code=status_code).inc()
        metrics.REQUESTS_IN_PROGRESS.labels(method='http').dec()

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Monitoring"])
async def health_check():
    if app_state.is_ready:
        return {"status": "healthy"}
    else:
        return Response(content='{"status": "initializing"}', status_code=status.HTTP_503_SERVICE_UNAVAILABLE, headers={"Retry-After": "30"}, media_type="application/json")

async def _perform_query(tenant_id: str, query: str, top_k: int) -> list[schemas.QueryResult]:
    collection_name = f"{settings.QDRANT_DB_COLLECTION_PREFIX}{tenant_id}"
    log = logger.bind(tenant_id=tenant_id, collection=collection_name)

    if not app_state.embedding_model or not app_state.qdrant_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Model veya DB istemcisi hazır değil.")

    try:
        log.info("Sorgu vektörleştiriliyor...")
        query_vector = await asyncio.to_thread(app_state.embedding_model.encode, query)
        query_vector = query_vector.tolist()

        log.info("Vektör veritabanında arama yapılıyor...", top_k=top_k)
        
        # FALLBACK MANTIKLI ARAMA
        def do_search():
            # Eğer search varsa kullan
            if hasattr(app_state.qdrant_client, 'search'):
                return app_state.qdrant_client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=top_k,
                    with_payload=True
                )
            # Eğer yoksa (çok düşük ihtimal ama) query_points dene
            elif hasattr(app_state.qdrant_client, 'query_points'):
                log.warning("'search' metodu bulunamadı, 'query_points' deneniyor.")
                return app_state.qdrant_client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    limit=top_k,
                    with_payload=True
                ).points
            else:
                raise AttributeError("QdrantClient ne 'search' ne de 'query_points' metoduna sahip!")

        search_result = await asyncio.to_thread(do_search)

        results = [
            schemas.QueryResult(
                content=hit.payload.get("content", ""), 
                score=hit.score, 
                source=hit.payload.get("source_uri", "unknown"), 
                metadata=hit.payload
            )
            for hit in search_result
        ]
        log.info(f"{len(results)} sonuç bulundu.")
        return results
    except UnexpectedResponse as e:
        if e.status_code == 404:
            log.warning("Koleksiyon bulunamadı.", error=str(e))
            return []
        log.error("Qdrant ile iletişimde hata.", http_status=e.status_code, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Vektör veritabanı hatası.")
    except Exception as e:
        log.error("Sorgu işlenirken hata.", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="İç sunucu hatası.")

@app.post(f"{settings.API_V1_STR}/query", response_model=schemas.QueryResponse, tags=["RAG"])
async def query_knowledge_base(request: schemas.QueryRequest):
    if not app_state.is_ready:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Servis henüz başlatılıyor.")
    results = await _perform_query(tenant_id=request.tenant_id, query=request.query, top_k=request.top_k)
    return schemas.QueryResponse(results=results)