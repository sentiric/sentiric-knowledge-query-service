# sentiric-knowledge-query-service/app/core/health.py
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class HealthState:
    def __init__(self):
        self._lock = threading.Lock()
        self.model_ready = False
        self.qdrant_ready = False

    def set_model_ready(self, status: bool):
        with self._lock:
            self.model_ready = status

    def set_qdrant_ready(self, status: bool):
        with self._lock:
            self.qdrant_ready = status

    def is_healthy(self) -> bool:
        with self._lock:
            return self.model_ready and self.qdrant_ready

health_state = HealthState()

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            if health_state.is_healthy():
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')
            else:
                self.send_response(503)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "unhealthy"}')
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server(port: int):
    server = HTTPServer(('', port), HealthCheckHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    print(f"🩺 Health check sunucusu port {port} üzerinde başlatıldı.")