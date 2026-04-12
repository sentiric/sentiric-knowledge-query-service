# app/runner.py
import asyncio
import uvicorn
import structlog
import uuid
from app.main import app
from app.core.logging import setup_logging
from app.core.config import settings

logger = structlog.get_logger()


async def main():
    # SUTS v4.0: Log motorunu en erken aşamada başlat
    setup_logging()

    # Startup (Lifespan) bağlamı için izole Trace/Span ID
    structlog.contextvars.bind_contextvars(
        trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4())
    )

    logger.info("Starting background services...", event_name="SYSTEM_INIT")

    # Uvicorn başlatılıyor. FastAPI lifespan eventi tetiklenecek ve
    # gRPC + Metrics sunucuları main.py içinden otomatik olarak ayağa kalkacaktır.
    uvicorn_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=settings.KNOWLEDGE_QUERY_SERVICE_HTTP_PORT,  # [ARCH-COMPLIANCE FIX]: Doğrudan kendi portu
        log_config=None,
        access_log=False,
    )

    uvicorn_server = uvicorn.Server(uvicorn_config)
    await uvicorn_server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        structlog.contextvars.bind_contextvars(
            trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4())
        )
        logger.info("Servers shutting down gracefully.", event_name="SYSTEM_SHUTDOWN")
