# app/grpc/service.py
import grpc
import structlog
import uuid
from structlog.contextvars import clear_contextvars, bind_contextvars

from sentiric.knowledge.v1 import query_pb2, query_pb2_grpc
from app.core.engine import engine
from app.core.config import settings

logger = structlog.get_logger()


class KnowledgeQueryServicer(query_pb2_grpc.KnowledgeQueryServiceServicer):
    async def Query(
        self, request: query_pb2.QueryRequest, context: grpc.aio.ServicerContext
    ) -> query_pb2.QueryResponse:

        clear_contextvars()

        metadata = context.invocation_metadata()
        trace_id = None
        if metadata:
            for key, value in metadata:
                if key.lower() == "x-trace-id":
                    trace_id = value
                    break

        if not trace_id:
            trace_id = uuid.uuid4().hex

        # [ARCH-COMPLIANCE] AI Streaming Compliance & Context Propagation
        span_id = uuid.uuid4().hex
        bind_contextvars(
            trace_id=trace_id, span_id=span_id, tenant_id=request.tenant_id
        )

        logger.info(
            "gRPC Query request received",
            event_name="RPC_QUERY_RECEIVED",
            tenant_id=request.tenant_id,
        )

        if not request.tenant_id or not request.query:
            logger.warning(
                "Missing parameters in query request", event_name="RPC_INVALID_ARGUMENT"
            )
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Eksik parametreler.")

        try:
            limit = (
                request.top_k
                if request.top_k > 0
                else settings.KNOWLEDGE_QUERY_DEFAULT_TOP_K
            )

            logger.info(
                "Executing RAG Search...", event_name="RAG_SEARCH_START", top_k=limit
            )
            results = await engine.search(
                tenant_id=request.tenant_id, query_text=request.query, top_k=limit
            )

            proto_results = [
                query_pb2.QueryResult(
                    content=r.content,
                    score=r.score,
                    source=r.source,
                    metadata=r.metadata,
                )
                for r in results
            ]

            logger.info(
                "gRPC Query completed successfully",
                event_name="RPC_QUERY_SUCCESS",
                results_count=len(proto_results),
            )
            return query_pb2.QueryResponse(results=proto_results)

        except TimeoutError:
            logger.error("RAG engine timed out", event_name="RPC_QUERY_TIMEOUT")
            await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "Vector DB timeout")
        except Exception as e:
            logger.error(
                "gRPC Internal Error",
                event_name="RPC_QUERY_ERROR",
                error=str(e),
                exc_info=True,
            )
            await context.abort(grpc.StatusCode.INTERNAL, "Sunucu hatası")
        finally:
            clear_contextvars()
