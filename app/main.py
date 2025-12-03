# app/main.py
import asyncio
import grpc
import structlog
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, status, Response
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.engine import engine
from app.core import metrics
from app.schemas import QueryRequest, QueryResponse
from app.grpc.service import KnowledgeQueryServicer
from sentiric.knowledge.v1 import query_pb2_grpc

# Logger kurulumu (İlk iş)
setup_logging()
logger = structlog.get_logger(__name__)

# Global gRPC sunucusu referansı
grpc_server: grpc.aio.Server = None

async def start_grpc_server():
    """gRPC sunucusunu başlatır (mTLS veya Insecure)."""
    global grpc_server
    grpc_server = grpc.aio.server()
    
    # Servisleri ekle
    query_pb2_grpc.add_KnowledgeQueryServiceServicer_to_server(KnowledgeQueryServicer(), grpc_server)
    
    # Health Check Servisi ekle (Consul/Kubernetes için kritik)
    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, grpc_server)
    # Tüm servislerin sağlıklı olduğunu işaretle
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)

    listen_addr = f'[::]:{settings.KNOWLEDGE_QUERY_SERVICE_GRPC_PORT}'

    # mTLS Yapılandırması
    if settings.KNOWLEDGE_QUERY_SERVICE_CERT_PATH and Path(settings.KNOWLEDGE_QUERY_SERVICE_CERT_PATH).exists():
        logger.info("🔒 mTLS ile güvenli gRPC başlatılıyor...")
        try:
            private_key = Path(settings.KNOWLEDGE_QUERY_SERVICE_KEY_PATH).read_bytes()
            certificate_chain = Path(settings.KNOWLEDGE_QUERY_SERVICE_CERT_PATH).read_bytes()
            ca_cert = Path(settings.GRPC_TLS_CA_PATH).read_bytes()
            
            creds = grpc.ssl_server_credentials(
                [(private_key, certificate_chain)],
                root_certificates=ca_cert,
                require_client_auth=True
            )
            grpc_server.add_secure_port(listen_addr, creds)
        except Exception as e:
             logger.critical("Sertifika hatası! Insecure moda düşülüyor.", error=str(e))
             grpc_server.add_insecure_port(listen_addr)
    else:
        logger.warning("⚠️ Sertifikalar bulunamadı. INSECURE (Güvensiz) gRPC başlatılıyor.")
        grpc_server.add_insecure_port(listen_addr)

    logger.info(f"🚀 gRPC Server dinliyor: {listen_addr}")
    await grpc_server.start()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama Yaşam Döngüsü Yönetimi"""
    # 1. Başlangıç
    logger.info("Servis Başlatılıyor...", version=settings.SERVICE_VERSION)
    
    # Metrics sunucusunu başlat
    asyncio.create_task(metrics.start_metrics_server())
    
    # RAG Engine'i başlat (Model yükleme + DB bağlantısı)
    await engine.initialize()
    
    # gRPC Sunucusunu başlat
    asyncio.create_task(start_grpc_server())
    
    yield
    
    # 2. Kapanış (Graceful Shutdown)
    logger.info("Servis Kapatılıyor...")
    if grpc_server:
        await grpc_server.stop(grace=5)
    await engine.shutdown()
    logger.info("Güle güle.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.SERVICE_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENV == "development" else None, # Prod'da Swagger kapatılabilir
    redoc_url=None
)

@app.get("/health", tags=["Monitoring"])
async def health_check():
    """
    Derin sağlık kontrolü. Load Balancer ve Orchestrator'lar buraya bakar.
    """
    is_healthy = await engine.check_health()
    if is_healthy:
        return {"status": "healthy", "version": settings.SERVICE_VERSION, "engine": "ready"}
    
    # 503 dönmek, trafiğin kesilmesini sağlar (Circuit Breaker mantığı)
    return Response(
        content='{"status": "unhealthy", "detail": "Engine not ready"}', 
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
        media_type="application/json"
    )

@app.post(f"{settings.API_V1_STR}/query", response_model=QueryResponse, tags=["RAG"])
async def query_knowledge_base(request: QueryRequest):
    """
    HTTP üzerinden RAG sorgusu yapar.
    """
    try:
        results = await engine.search(
            tenant_id=request.tenant_id, 
            query_text=request.query, 
            top_k=request.top_k
        )
        return QueryResponse(results=results)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Servis henüz hazır değil.")
    except Exception as e:
        logger.error("HTTP Query hatası", error=str(e))
        raise HTTPException(status_code=500, detail="Sorgu işlenemedi.")