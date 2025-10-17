# app/core/logging.py
import logging
import sys
import structlog
from app.core.config import settings

_log_setup_done = False

def setup_logging():
    """
    Tüm servislerde kullanılacak standart loglama yapılandırması.
    Ortama göre (development/production) farklı formatlayıcılar kullanır.
    """
    global _log_setup_done
    if _log_setup_done:
        return

    log_level = settings.LOG_LEVEL.upper()
    env = settings.ENV.lower()

    # Standart Python loglamasını structlog'a yönlendir
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level
    )

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(), # <-- HATAYI DÜZELTEN SATIR
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    renderer = (
        structlog.dev.ConsoleRenderer(colors=True)
        if env == "development"
        else structlog.processors.JSONRenderer()
    )

    # structlog yapılandırması
    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    
    if root_logger.hasHandlers():
         root_logger.handlers.clear()
         
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    _log_setup_done = True

    logger = structlog.get_logger("sentiric_knowledge_query_service")
    logger.info(
        "Loglama başarıyla yapılandırıldı.",
        env=env,
        log_level=log_level
    )