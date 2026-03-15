# app/main.py (İlgili eklemelerle birlikte güncellenmiş hali)
import asyncio
import grpc
import structlog
import uuid # YENİ: Trace ID üretimi için
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status, Response, Request # Request YENİ eklendi
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from structlog.contextvars import clear_contextvars, bind_contextvars # YENİ: Log context'i için

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.engine import engine
from app.core import metrics
from app.schemas import QueryRequest, QueryResponse
from app.grpc.service import KnowledgeQueryServicer
from sentiric.knowledge.v1 import query_pb2_grpc

setup_logging()
logger = structlog.get_logger(__name__)
grpc_server: grpc.aio.Server = None

async def start_grpc_server():
    global grpc_server
    grpc_server = grpc.aio.server()
    
    # Servisleri Kaydet
    query_pb2_grpc.add_KnowledgeQueryServiceServicer_to_server(KnowledgeQueryServicer(), grpc_server)
    
    # Standart gRPC Health Check (Consul/K8s için)
    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, grpc_server)
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)

    listen_addr = f'[::]:{settings.KNOWLEDGE_QUERY_SERVICE_GRPC_PORT}'

    # --- AKILLI SERTİFİKA KONTROLÜ ---
    certs_available = (
        settings.KNOWLEDGE_QUERY_SERVICE_CERT_PATH and 
        Path(settings.KNOWLEDGE_QUERY_SERVICE_CERT_PATH).exists() and
        settings.KNOWLEDGE_QUERY_SERVICE_KEY_PATH and 
        Path(settings.KNOWLEDGE_QUERY_SERVICE_KEY_PATH).exists()
    )

    if certs_available:
        logger.info("🔒 Sertifikalar bulundu, mTLS başlatılıyor...")
        try:
            private_key = Path(settings.KNOWLEDGE_QUERY_SERVICE_KEY_PATH).read_bytes()
            cert_chain = Path(settings.KNOWLEDGE_QUERY_SERVICE_CERT_PATH).read_bytes()
            root_ca = Path(settings.GRPC_TLS_CA_PATH).read_bytes() if settings.GRPC_TLS_CA_PATH else None
            
            creds = grpc.ssl_server_credentials(
                [(private_key, cert_chain)],
                root_certificates=root_ca,
                require_client_auth=(root_ca is not None)
            )
            grpc_server.add_secure_port(listen_addr, creds)
        except Exception as e:
             logger.error("Sertifika yükleme hatası! Insecure moda dönülüyor.", error=str(e))
             grpc_server.add_insecure_port(listen_addr)
    else:
        logger.warning("⚠️ Sertifika bulunamadı/tanımlanmadı. INSECURE modda başlatılıyor.")
        grpc_server.add_insecure_port(listen_addr)

    logger.info(f"🚀 gRPC Server dinliyor: {listen_addr}")
    await grpc_server.start()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Servis Başlatılıyor...", env=settings.ENV)
    
    asyncio.create_task(metrics.start_metrics_server())
    await engine.initialize()
    asyncio.create_task(start_grpc_server())
    
    yield
    
    logger.info("Servis Kapatılıyor...")
    if grpc_server:
        await grpc_server.stop(grace=5)
    await engine.shutdown()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.SERVICE_VERSION,
    lifespan=lifespan
)

# --- YENİ: HTTP Trace ID Middleware ---
# Mimari Kural (ARCH-OBSERVABILITY): Tüm senkron ve asenkron iletişimlerde 'trace_id' context propagation ile taşınmalıdır.
@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    # 1. Önceki istekten kalan context değişkenlerini temizle (Thread/Async sızıntılarını önler)
    clear_contextvars()
    
    # 2. İstemciden gelen 'x-trace-id' var mı kontrol et. Yoksa (sistemin ilk giriş noktasıysa) yeni üret.
    trace_id = request.headers.get("x-trace-id") or uuid.uuid4().hex
    
    # 3. trace_id'yi Structlog context'ine bağla. Artık bu isteğe ait tüm loglarda (derin fonksiyonlar dahil) otomatik yazılacak.
    bind_contextvars(trace_id=trace_id)
    
    # İstek işleniyor...
    response = await call_next(request)
    
    # 4. Yanıt başlıklarına ekleyerek diğer servislerin (veya istemcinin) trace_id'yi bilmesini sağla
    response.headers["x-trace-id"] = trace_id
    return response
# --------------------------------------

# --- Playground UI Mounting ---
static_path = Path("app/static")
if static_path.exists():
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    
    @app.get("/", include_in_schema=False)
    async def root():
        return FileResponse("app/static/index.html")

@app.get("/health")
async def health_check():
    if await engine.check_health():
        return {"status": "healthy", "mode": "standalone" if not settings.GRPC_TLS_CA_PATH else "cluster"}
    
    return Response(
        content='{"status": "unhealthy", "detail": "RAG Engine Not Ready"}', 
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
        media_type="application/json"
    )

@app.post(f"{settings.API_V1_STR}/query", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest):
    try:
        results = await engine.search(request.tenant_id, request.query, request.top_k)
        # Log örneği: structlog otomatik olarak trace_id'yi buraya basacak
        logger.info("HTTP sorgusu başarıyla işlendi", tenant_id=request.tenant_id, results_count=len(results))
        return QueryResponse(results=results)
    except Exception as e:
        logger.error("API Query Hatası", error=str(e))
        raise HTTPException(status_code=500, detail="Internal Error")