# app/core/metrics.py
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    REGISTRY,
    multiprocess,
)
import structlog
from app.core.config import settings

logger = structlog.get_logger(__name__)

# --- Metrik Tanımları ---

# Servis hakkında statik bilgi (versiyon vb.)
SERVICE_INFO = Info(
    'service_info', 
    'Knowledge Query Service static information'
)

# Gelen isteklerin toplam sayısını sayar (HTTP/gRPC)
REQUESTS_TOTAL = Counter(
    'requests_total',
    'Total number of requests by method and status code.',
    ['method', 'status_code']
)

# İsteklerin gecikme süresini ölçer
REQUEST_LATENCY_SECONDS = Histogram(
    'request_latency_seconds',
    'Request latency in seconds.',
    ['method']
)

# Anlık olarak işlenmekte olan istek sayısını gösterir
REQUESTS_IN_PROGRESS = Gauge(
    'requests_in_progress',
    'Number of requests currently in progress.',
    ['method']
)

# --- Metrik Sunucusu ---

class MetricsHandler(BaseHTTPRequestHandler):
    """Prometheus metriklerini sunan HTTP handler."""
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; version=0.0.4')
            self.end_headers()
            # En son metrik verilerini oluştur ve gönder
            self.wfile.write(generate_latest(REGISTRY))
        else:
            self.send_response(404)
            self.end_headers()

async def start_metrics_server():
    """Prometheus metrik sunucusunu asenkron olarak başlatır."""
    port = settings.KNOWLEDGE_QUERY_SERVICE_METRICS_PORT
    server = HTTPServer(('', port), MetricsHandler)
    logger.info("Metrik sunucusu başlatılıyor...", address=f"http://0.0.0.0:{port}/metrics")
    
    # Senkron sunucuyu bir thread'de çalıştırmak için asyncio'nun executor'ını kullan
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, server.serve_forever)