# app/runner.py
import asyncio
import uvicorn
import structlog
from app.main import app, serve_grpc
from app.core.config import settings
from app.core.metrics import start_metrics_server

logger = structlog.get_logger(__name__)

async def main():
    """
    Uvicorn (HTTP), gRPC ve Prometheus Metrics sunucularını aynı anda asenkron olarak çalıştırır.
    """
    logger.info("Starting all servers...")
    
    # Uvicorn sunucusunu bir coroutine olarak yapılandır
    uvicorn_config = uvicorn.Config(
        app, 
        host="0.0.0.0", 
        port=settings.KNOWLEDGE_QUERY_SERVICE_HTTP_PORT,
        log_config=None, # Loglamayı structlog'a devretmek için
        access_log=False
    )
    uvicorn_server = uvicorn.Server(uvicorn_config)
    
    # Üç sunucuyu da asyncio.gather ile paralel olarak başlat
    await asyncio.gather(
        uvicorn_server.serve(),
        serve_grpc(),
        start_metrics_server()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Servers shutting down gracefully.")