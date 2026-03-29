# app/runner.py
import asyncio
import uvicorn
import structlog
from app.main import app
try:
    from app.main import serve_grpc # Indexing Service
    from app.core.metrics import start_metrics_server
    is_indexing = True
except ImportError:
    is_indexing = False # Query Service

from app.core.config import settings

logger = structlog.get_logger()

async def main():
    logger.info("Starting background services...", event_name="SYSTEM_INIT")
    
    uvicorn_config = uvicorn.Config(
        app, 
        host="0.0.0.0", 
        # Portlar conf'tan çekilir
        port=settings.KNOWLEDGE_INDEXING_SERVICE_HTTP_PORT if is_indexing else settings.KNOWLEDGE_QUERY_SERVICE_HTTP_PORT,
        log_config=None, # [ARCH-COMPLIANCE] Uvicorn default loglarını engelle
        access_log=False # [ARCH-COMPLIANCE] HTTP Get/Post gürültüsünü engelle
    )
    uvicorn_server = uvicorn.Server(uvicorn_config)
    
    if is_indexing:
        await asyncio.gather(
            uvicorn_server.serve(),
            serve_grpc(),
            start_metrics_server()
        )
    else:
        # Query service handle grpc & metrics inside main.py lifespan
        await uvicorn_server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Servers shutting down gracefully.", event_name="SYSTEM_SHUTDOWN")