# app/core/engine.py
import asyncio
import structlog
import torch
from typing import List, Optional
from sentence_transformers import SentenceTransformer
from qdrant_client import AsyncQdrantClient
from app.core.config import settings
from app.schemas import QueryResult

logger = structlog.get_logger()


class RAGEngine:
    def __init__(self):
        self.model: Optional[SentenceTransformer] = None
        self.qdrant: Optional[AsyncQdrantClient] = None
        self._ready = False

    async def initialize(self):
        try:
            logger.info("RAG Engine: Başlatılıyor...", event_name="RAG_ENGINE_START")

            device = "cuda" if torch.cuda.is_available() else "cpu"

            # [ARCH-COMPLIANCE FIX]: Ruff linter hatası f-string takısı kaldırıldı
            logger.info(
                "Model Ana Thread üzerinde yükleniyor...",
                event_name="MODEL_LOADING_SYNC",
                model=settings.QDRANT_DB_EMBEDDING_MODEL_NAME,
                device=device,
            )

            self.model = SentenceTransformer(
                settings.QDRANT_DB_EMBEDDING_MODEL_NAME,
                cache_folder=settings.HF_HOME,
                device=device,
            )

            # [ARCH-COMPLIANCE FIX]: Ruff linter hatası f-string takısı kaldırıldı
            logger.info(
                "Qdrant'a bağlanılıyor...",
                event_name="DB_CONNECTING",
                url=settings.QDRANT_HTTP_URL,
            )
            self.qdrant = AsyncQdrantClient(
                url=settings.QDRANT_HTTP_URL, api_key=settings.QDRANT_API_KEY
            )

            colls = await asyncio.wait_for(self.qdrant.get_collections(), timeout=10.0)
            logger.info(
                "Qdrant bağlantısı başarılı.",
                event_name="DB_CONNECTED",
                collections_count=len(colls.collections),
            )

            self._ready = True
            logger.info("RAG Engine: Hazır.", event_name="RAG_ENGINE_READY")
        except asyncio.TimeoutError:
            self._ready = False
            logger.error(
                "Qdrant connection timed out during initialization.",
                event_name="DB_TIMEOUT",
            )
            raise
        except Exception as e:
            self._ready = False
            logger.critical(
                "RAG Engine başlatılamadı!",
                event_name="RAG_ENGINE_FAIL",
                error=str(e),
                exc_info=True,
            )
            raise e

    async def shutdown(self):
        if self.qdrant:
            await self.qdrant.close()
        self._ready = False
        logger.info("RAG Engine: Kapatıldı.", event_name="RAG_ENGINE_STOPPED")

    async def check_health(self) -> bool:
        if not self._ready or not self.model:
            return False
        try:
            await asyncio.wait_for(self.qdrant.get_collections(), timeout=5.0)
            return True
        except Exception:
            return False

    async def search(
        self, tenant_id: str, query_text: str, top_k: int = 5
    ) -> List[QueryResult]:
        if not self._ready:
            raise RuntimeError("Engine is not ready")

        collection_name = f"{settings.QDRANT_DB_COLLECTION_PREFIX}{tenant_id}"

        # [ARCH-COMPLIANCE FIX]: PyTorch OOM engellemek için asyncio.to_thread kaldırıldı!
        # Doğrudan senkron olarak çalışacak.
        query_vector = self.model.encode(query_text)
        query_vector_list = query_vector.tolist()

        try:
            search_result = await asyncio.wait_for(
                self.qdrant.search(
                    collection_name=collection_name,
                    query_vector=query_vector_list,
                    limit=top_k,
                    score_threshold=settings.SCORE_THRESHOLD,
                    with_payload=True,
                ),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Qdrant search timed out (Exceeded 5s limit).",
                event_name="DB_SEARCH_TIMEOUT",
                collection=collection_name,
            )
            raise TimeoutError("Vector DB request timed out")
        except Exception as e:
            if "404" in str(e) or "Not found" in str(e):
                logger.warning(
                    "Koleksiyon bulunamadı, boş dönülüyor.",
                    event_name="DB_COLLECTION_NOT_FOUND",
                    collection=collection_name,
                )
                return []
            logger.error(
                "Qdrant arama hatası",
                event_name="DB_SEARCH_ERROR",
                error=str(e),
                exc_info=True,
            )
            raise e

        results = []
        for hit in search_result:
            payload = hit.payload or {}
            results.append(
                QueryResult(
                    content=payload.get("content", ""),
                    score=hit.score,
                    source=payload.get("source_uri", "unknown"),
                    metadata=payload,
                )
            )
        return results


engine = RAGEngine()
