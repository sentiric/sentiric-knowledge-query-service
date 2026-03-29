# app/core/logging.py
import logging
import logging.config
import sys
import structlog
from datetime import datetime, timezone
from app.core.config import settings

_log_setup_done = False

def suts_v4_processor(logger, method_name: str, event_dict: dict) -> dict:
    message = event_dict.pop("event", "")
    suts_event = event_dict.pop("event_name", event_dict.pop("event_id", "LOG_EVENT"))
    
    trace_id = event_dict.pop("trace_id", None)
    span_id = event_dict.pop("span_id", None)
    tenant_id = event_dict.pop("tenant_id", settings.TENANT_ID)

    event_dict.pop("timestamp", None)
    event_dict.pop("level", None)
    event_dict.pop("logger", None)

    return {
        "schema_v": "1.0.0",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "severity": method_name.upper() if method_name else "INFO",
        "tenant_id": tenant_id,
        "resource": {
            "service.name": settings.PROJECT_NAME.lower().replace(" ", "-").replace("sentiric-", ""),
            "service.version": settings.SERVICE_VERSION,
            "service.env": settings.ENV,
            "host.name": settings.NODE_NAME
        },
        "trace_id": trace_id,
        "span_id": span_id,
        "event": suts_event,
        "message": str(message),
        "attributes": event_dict
    }

def setup_logging():
    global _log_setup_done
    if _log_setup_done:
        return

    log_level = settings.LOG_LEVEL.upper()

    # 1. Kök Logger Yapılandırması
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

    # 2. Python Warnings Yakalama (Qdrant insecure warning vb.)
    logging.captureWarnings(True)

    # 3. Uvicorn ve FastAPI Loglarını Root Logger'a Yönlendirme (Hijack)
    intercept_loggers = ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"]
    for logger_name in intercept_loggers:
        l = logging.getLogger(logger_name)
        l.handlers.clear()
        l.propagate = True

    # 4. Gürültücü Kütüphaneleri Susturma (Sadece ERROR fırlatırlarsa logla)
    noisy_loggers = [
        "httpx", 
        "httpcore", 
        "urllib3", 
        "qdrant_client", 
        "huggingface_hub", 
        "sentence_transformers",
        "py.warnings" # Warning'ler JSON'a akar ama gereksiz olanları filtrelemek için ERROR yapılabilir, ancak captureWarnings(True) kullandığımız için devrede kalsın.
    ]
    for n in noisy_loggers:
        logging.getLogger(n).setLevel(logging.ERROR)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        suts_v4_processor,
        structlog.processors.JSONRenderer() 
    ]

    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    _log_setup_done = True
    logger = structlog.get_logger()
    logger.info("Structured logging configured to SUTS v4.0 with Anti-Noise Engine", event_name="SYSTEM_LOGGING_INIT")