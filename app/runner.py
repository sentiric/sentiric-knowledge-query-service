# app/runner.py
import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    # Production'da bu dosya yerine doğrudan uvicorn komutu veya gunicorn kullanılır.
    # Bu sadece geliştirme/debug içindir.
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.KNOWLEDGE_QUERY_SERVICE_HTTP_PORT,
        reload=(settings.ENV == "development"),
        log_config=None # Structlog kullandığımız için uvicorn loglarını eziyoruz
    )