# app/grpc/service.py
import grpc
import structlog
from sentiric.knowledge.v1 import query_pb2, query_pb2_grpc
from app.core.engine import engine
from app.core.config import settings

logger = structlog.get_logger(__name__)

class KnowledgeQueryServicer(query_pb2_grpc.KnowledgeQueryServiceServicer):
    async def Query(self, request: query_pb2.QueryRequest, context: grpc.aio.ServicerContext) -> query_pb2.QueryResponse:
        # Basit validasyon
        if not request.tenant_id or not request.query:
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
            return query_pb2.QueryResponse(results=proto_results)

        except Exception as e:
            logger.error("gRPC Hatası", error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, "Sunucu hatası")