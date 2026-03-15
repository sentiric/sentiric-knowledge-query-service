# app/grpc/service.py
import grpc
import structlog
import uuid # YENİ: Trace ID üretimi için
from structlog.contextvars import clear_contextvars, bind_contextvars # YENİ: Log context için

from sentiric.knowledge.v1 import query_pb2, query_pb2_grpc
from app.core.engine import engine
from app.core.config import settings

logger = structlog.get_logger(__name__)

class KnowledgeQueryServicer(query_pb2_grpc.KnowledgeQueryServiceServicer):
    async def Query(self, request: query_pb2.QueryRequest, context: grpc.aio.ServicerContext) -> query_pb2.QueryResponse:
        
        # --- YENİ: gRPC Trace ID Extraction (Mimari Kural Uygulaması) ---
        clear_contextvars() # Her yeni çağrıda context'i temizle
        
        # Metadata'dan 'x-trace-id' yakala (Tuple formatında gelir)
        metadata = context.invocation_metadata()
        trace_id = None
        if metadata:
            for key, value in metadata:
                if key.lower() == "x-trace-id":
                    trace_id = value
                    break
        
        # Yoksa yeni bir trace_id üret
        if not trace_id:
            trace_id = uuid.uuid4().hex
            
        # Loglama context'ine kaydet (Bu noktadan sonraki tüm engine.search vb. loglarında trace_id olacak)
        bind_contextvars(trace_id=trace_id)
        # ----------------------------------------------------------------

        logger.info("gRPC Query isteği alındı", tenant_id=request.tenant_id)

        # Basit validasyon
        if not request.tenant_id or not request.query:
             logger.warning("Eksik parametre ile sorgu isteği")
             await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Eksik parametreler.")

        try:
            limit = request.top_k if request.top_k > 0 else settings.KNOWLEDGE_QUERY_DEFAULT_TOP_K
            
            # Engine'i çağır
            results = await engine.search(
                tenant_id=request.tenant_id,
                query_text=request.query,
                top_k=limit
            )
            
            # Proto'ya çevir
            proto_results = [
                query_pb2.QueryResult(
                    content=r.content,
                    score=r.score,
                    source=r.source,
                    metadata=r.metadata
                ) for r in results
            ]
            
            logger.info("gRPC Query başarıyla tamamlandı", results_count=len(proto_results))
            return query_pb2.QueryResponse(results=proto_results)

        except Exception as e:
            logger.error("gRPC Hatası", error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, "Sunucu hatası")