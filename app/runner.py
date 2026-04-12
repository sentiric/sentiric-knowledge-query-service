# app/runner.py
import asyncio
import uvicorn
import structlog
import uuid
from app.main import app

try:
    # [ARCH-COMPLIANCE FIX]: 'serve_grpc' adı Query Service tarafında start_grpc_server olarak değiştirilmişti.
    # Indexing_service uyumluluğu için bunu doğru eşleştiriyoruz.
    from app.main import start_grpc_server as serve_grpc
    from app.core.metrics import start_metrics_server

    is_indexing = True
except ImportError:
    is_indexing = False  # Query Service

from app.core.config import settings

logger = structlog.get_logger()


async def main():
    structlog.contextvars.bind_contextvars(
        trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4())
    )
    logger.info("Starting background services...", event_name="SYSTEM_INIT")

    uvicorn_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=settings.KNOWLEDGE_INDEXING_SERVICE_HTTP_PORT
        if is_indexing
        else settings.KNOWLEDGE_QUERY_SERVICE_HTTP_PORT,
        log_config=None,
        access_log=False,
    )
    uvicorn_server = uvicorn.Server(uvicorn_config)

    if is_indexing:
        await asyncio.gather(
            uvicorn_server.serve(), serve_grpc(), start_metrics_server()
        )
    else:
        await uvicorn_server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        structlog.contextvars.bind_contextvars(
            trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4())
        )
        logger.info("Servers shutting down gracefully.", event_name="SYSTEM_SHUTDOWN")
