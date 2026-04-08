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
)
import structlog
from app.core.config import settings

logger = structlog.get_logger()

SERVICE_INFO = Info("service_info", "Knowledge Query Service static information")
REQUESTS_TOTAL = Counter(
    "requests_total",
    "Total number of requests by method and status code.",
    ["method", "status_code"],
)
REQUEST_LATENCY_SECONDS = Histogram(
    "request_latency_seconds", "Request latency in seconds.", ["method"]
)
REQUESTS_IN_PROGRESS = Gauge(
    "requests_in_progress", "Number of requests currently in progress.", ["method"]
)


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.end_headers()
            self.wfile.write(generate_latest(REGISTRY))
        else:
            self.send_response(404)
            self.end_headers()

    # [ARCH-COMPLIANCE] BaseHTTPRequestHandler default loglamasını sustur (JSON stdout'u bozar)
    def log_message(self, format, *args):
        pass


async def start_metrics_server():
    port = settings.KNOWLEDGE_QUERY_SERVICE_METRICS_PORT
    server = HTTPServer(("", port), MetricsHandler)
    logger.info(
        "Metrics server starting...",
        event_name="METRICS_SERVER_START",
        address=f"http://0.0.0.0:{port}/metrics",
    )

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, server.serve_forever)
