# app/main.py
import asyncio
import sys
import grpc
import structlog
import uuid 
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status, Response, Request 
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from structlog.contextvars import clear_contextvars, bind_contextvars 

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.engine import engine
from app.core import metrics
from app.schemas import QueryRequest, QueryResponse
from app.grpc.service import KnowledgeQueryServicer
from sentiric.knowledge.v1 import query_pb2_grpc

setup_logging()
logger = structlog.get_logger()
grpc_server: grpc.aio.Server = None

async def start_grpc_server():
    global grpc_server
    grpc_server = grpc.aio.server()
    
    query_pb2_grpc.add_KnowledgeQueryServiceServicer_to_server(KnowledgeQueryServicer(), grpc_server)
    
    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, grpc_server)
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)

    listen_addr = f'[::]:{settings.KNOWLEDGE_QUERY_SERVICE_GRPC_PORT}'

    certs_available = (
        settings.KNOWLEDGE_QUERY_SERVICE_CERT_PATH and 
        Path(settings.KNOWLEDGE_QUERY_SERVICE_CERT_PATH).exists() and
        settings.KNOWLEDGE_QUERY_SERVICE_KEY_PATH and 
        Path(settings.KNOWLEDGE_QUERY_SERVICE_KEY_PATH).exists()
    )

    if certs_available:
        logger.info("Certificates found, initializing mTLS...", event_name="GRPC_MTLS_INIT")
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
            if settings.ENV == "production":
                logger.fatal(f"Certificate load error. Insecure mode forbidden in production. Error: {e}", event_name="MTLS_CONFIG_ERROR")
                sys.exit(1) # [ARCH-COMPLIANCE] Crash instead of silent degradation
            else:
                logger.error("Certificate load error. Reverting to insecure mode.", event_name="MTLS_FALLBACK", error=str(e))
                grpc_server.add_insecure_port(listen_addr)
    else:
        if settings.ENV == "production":
            logger.fatal("Certificates missing! mTLS is MANDATORY in production.", event_name="MTLS_MISSING_FATAL")
            sys.exit(1) # [ARCH-COMPLIANCE]
        else:
            logger.warning("Certificates missing. Starting in INSECURE mode.", event_name="GRPC_INSECURE_START")
            grpc_server.add_insecure_port(listen_addr)

    logger.info(f"gRPC Server listening on: {listen_addr}", event_name="GRPC_SERVER_STARTED")
    await grpc_server.start()

@asynccontextmanager
async def lifespan(app: FastAPI):
    clear_contextvars()
    # [ARCH-COMPLIANCE] Explicit span_id allocation for system initialization
    structlog.contextvars.bind_contextvars(trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4()))
    logger.info("Service Booting Up", event_name="SYSTEM_STARTUP", version=settings.SERVICE_VERSION, env=settings.ENV)
    
    asyncio.create_task(metrics.start_metrics_server())
    await engine.initialize()
    asyncio.create_task(start_grpc_server())
    
    yield
    
    logger.info("Service Shutting Down", event_name="SERVICE_STOPPED")
    if grpc_server:
        await grpc_server.stop(grace=5)
    await engine.shutdown()
    clear_contextvars()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.SERVICE_VERSION,
    lifespan=lifespan
)

@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    clear_contextvars()
    trace_id = request.headers.get("x-trace-id") or uuid.uuid4().hex
    span_id = uuid.uuid4().hex
    
    bind_contextvars(trace_id=trace_id, span_id=span_id)
    response = await call_next(request)
    response.headers["x-trace-id"] = trace_id
    return response

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
    bind_contextvars(tenant_id=request.tenant_id)
    try:
        logger.info("HTTP Query request received", event_name="HTTP_QUERY_RECEIVED")
        results = await engine.search(request.tenant_id, request.query, request.top_k)
        logger.info("HTTP Query processed successfully", event_name="HTTP_QUERY_SUCCESS", results_count=len(results))
        return QueryResponse(results=results)
    except TimeoutError:
        logger.error("RAG Engine Timed Out", event_name="HTTP_QUERY_TIMEOUT")
        raise HTTPException(status_code=504, detail="Vector Database Timeout")
    except Exception as e:
        logger.error("API Query Error", event_name="HTTP_QUERY_ERROR", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")