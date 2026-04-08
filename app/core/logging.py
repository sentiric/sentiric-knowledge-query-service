import logging
import sys
import os
import uuid
import structlog
from datetime import datetime, timezone
from app.core.config import settings

_log_setup_done = False

os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["GRPC_VERBOSITY"] = "ERROR"


class InterceptHandler(logging.Handler):
    """Standart Python loglarını Structlog JSON yapısına çevirir (Anti-RAW)"""

    def emit(self, record):
        level_name = logging.getLevelName(record.levelno).lower()
        logger = structlog.get_logger(record.name)
        log_method = getattr(logger, level_name, logger.info)

        kwargs = {}
        if record.exc_info:
            kwargs["exc_info"] = record.exc_info

        log_method(
            record.getMessage(),
            event_name="THIRD_PARTY_LOG",
            logger_name=record.name,
            **kwargs,
        )


def suts_v4_processor(logger, method_name: str, event_dict: dict) -> dict:
    message = event_dict.pop("event", "")
    suts_event = event_dict.pop("event_name", event_dict.pop("event_id", "LOG_EVENT"))

    trace_id = event_dict.pop("trace_id", None)
    span_id = event_dict.pop("span_id", None)
    tenant_id = event_dict.pop("tenant_id", settings.TENANT_ID)

    if not trace_id:
        trace_id = "00000000-0000-0000-0000-000000000000"
    if not span_id:
        span_id = str(uuid.uuid4())

    event_dict.pop("timestamp", None)
    event_dict.pop("level", None)
    event_dict.pop("logger", None)

    return {
        "schema_v": "1.0.0",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "severity": method_name.upper() if method_name else "INFO",
        "tenant_id": tenant_id,
        "resource": {
            "service.name": settings.PROJECT_NAME.lower()
            .replace(" ", "-")
            .replace("sentiric-", ""),
            "service.version": settings.SERVICE_VERSION,
            "service.env": settings.ENV,
            "host.name": settings.NODE_NAME,
        },
        "trace_id": trace_id,
        "span_id": span_id,
        "event": suts_event,
        "message": str(message),
        "attributes": event_dict,
    }


def setup_logging():
    global _log_setup_done
    if _log_setup_done:
        return

    log_level = settings.LOG_LEVEL.upper()

    logging.basicConfig(handlers=[InterceptHandler()], level=log_level, force=True)
    logging.captureWarnings(True)

    intercept_loggers = [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "grpc",
        "_cygrpc",
        "asyncio",
    ]
    for logger_name in intercept_loggers:
        # [ARCH-COMPLIANCE FIX]: Ruff hatası çözüldü, 'l' yerine anlamlı isim kullanıldı
        target_logger = logging.getLogger(logger_name)
        target_logger.handlers = [InterceptHandler()]
        target_logger.propagate = False

    noisy_loggers = [
        "httpx",
        "httpcore",
        "urllib3",
        "qdrant_client",
        "huggingface_hub",
        "sentence_transformers",
        "transformers",
        "py.warnings",
    ]
    for n in noisy_loggers:
        logging.getLogger(n).setLevel(logging.ERROR)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        suts_v4_processor,
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.WriteLoggerFactory(file=sys.stdout),
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level)
        ),
        cache_logger_on_first_use=True,
    )

    _log_setup_done = True
    logger = structlog.get_logger()
    logger.info(
        "Structured logging configured to SUTS v4.0 with Anti-Noise Engine",
        event_name="SYSTEM_LOGGING_INIT",
    )
