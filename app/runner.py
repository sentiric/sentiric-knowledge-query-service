# app/runner.py
import uvicorn
import structlog
from app.core.config import settings

logger = structlog.get_logger()

if __name__ == "__main__":
    logger.info("Initiating Uvicorn runner", event_name="SYSTEM_RUNNER_START")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.KNOWLEDGE_QUERY_SERVICE_HTTP_PORT,
        reload=(settings.ENV == "development"),
        log_config=None, # Kendi logger'ımızı kullanacağımız için uvicorn'u susturuyoruz
        access_log=False
    )