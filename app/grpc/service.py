# app/grpc/service.py
import grpc
import structlog
from sentiric.knowledge.v1 import query_pb2, query_pb2_grpc
from app.core.engine import engine
from app.core.config import settings

logger = structlog.get_logger(__name__)

class KnowledgeQueryServicer(query_pb2_grpc.KnowledgeQueryServiceServicer):
    """
    gRPC İsteklerini karşılar ve RAG Engine'e yönlendirir.
    """
    async def Query(self, request: query_pb2.QueryRequest, context: grpc.aio.ServicerContext) -> query_pb2.QueryResponse:
        logger.info("gRPC Query alındı", tenant_id=request.tenant_id)
        
        if not request.tenant_id or not request.query:
             await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Tenant ID ve Query zorunludur.")

        try:
            limit = request.top_k if request.top_k > 0 else settings.KNOWLEDGE_QUERY_DEFAULT_TOP_K
            
            results = await engine.search(
                tenant_id=request.tenant_id,
                query_text=request.query,
                top_k=limit
            )
            
            # Protobuf yanıtına dönüştür
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
            logger.error("gRPC Query hatası", error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, "Internal processing error")