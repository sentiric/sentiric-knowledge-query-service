# app/core/engine.py
import asyncio
import structlog
from typing import List, Optional
from sentence_transformers import SentenceTransformer
from qdrant_client import AsyncQdrantClient
from app.core.config import settings
from app.schemas import QueryResult

logger = structlog.get_logger(__name__)

class RAGEngine:
    """
    Knowledge Query Service'in motoru.
    Modeli thread-safe yönetir, Qdrant ile async konuşur.
    """
    def __init__(self):
        self.model: Optional[SentenceTransformer] = None
        self.qdrant: Optional[AsyncQdrantClient] = None
        self._ready = False

    async def initialize(self):
        """Servis başlarken çağrılır."""
        try:
            logger.info("RAG Engine: Başlatılıyor...")

            # 1. Modeli Yükle (Ağır CPU işlemi -> Thread'e atılır)
            # Bu sayede Kubernetes health check'leri bloklanmaz.
            logger.info(f"Model yükleniyor...", model=settings.QDRANT_DB_EMBEDDING_MODEL_NAME)
            self.model = await asyncio.to_thread(
                SentenceTransformer,
                settings.QDRANT_DB_EMBEDDING_MODEL_NAME,
                cache_folder=settings.HF_HOME
            )
            
            # 2. Qdrant Bağlantısı (Async Client)
            logger.info(f"Qdrant'a bağlanılıyor...", url=settings.QDRANT_HTTP_URL)
            self.qdrant = AsyncQdrantClient(
                url=settings.QDRANT_HTTP_URL,
                api_key=settings.QDRANT_API_KEY
            )
            
            # Bağlantı Testi
            colls = await self.qdrant.get_collections()
            logger.info("Qdrant bağlantısı başarılı.", collections_count=len(colls.collections))

            self._ready = True
            logger.info("RAG Engine: Hazır.")
        except Exception as e:
            self._ready = False
            logger.critical("RAG Engine başlatılamadı!", error=str(e))
            raise e

    async def shutdown(self):
        """Servis kapanırken çağrılır."""
        if self.qdrant:
            await self.qdrant.close()
        self._ready = False
        logger.info("RAG Engine: Kapatıldı.")

    async def check_health(self) -> bool:
        """Derin sağlık kontrolü."""
        if not self._ready or not self.model:
            return False
        try:
            # DB hala orada mı?
            await self.qdrant.get_collections()
            return True
        except Exception:
            return False

    async def search(self, tenant_id: str, query_text: str, top_k: int = 5) -> List[QueryResult]:
        if not self._ready:
            raise RuntimeError("Engine is not ready")

        collection_name = f"{settings.QDRANT_DB_COLLECTION_PREFIX}{tenant_id}"
        
        # 1. Vektörleştirme (Blocking Engelleme -> Thread)
        query_vector = await asyncio.to_thread(self.model.encode, query_text)
        query_vector_list = query_vector.tolist()

        # 2. Arama (Async I/O)
        try:
            search_result = await self.qdrant.search(
                collection_name=collection_name,
                query_vector=query_vector_list,
                limit=top_k,
                score_threshold=settings.SCORE_THRESHOLD,
                with_payload=True
            )
        except Exception as e:
            # 404 normaldir (henüz veri yoksa)
            if "404" in str(e) or "Not found" in str(e):
                logger.warning("Koleksiyon bulunamadı, boş dönülüyor.", collection=collection_name)
                return []
            logger.error("Qdrant arama hatası", error=str(e))
            raise e

        # 3. Dönüştürme
        results = []
        for hit in search_result:
            payload = hit.payload or {}
            results.append(QueryResult(
                content=payload.get("content", ""),
                score=hit.score,
                source=payload.get("source_uri", "unknown"),
                metadata=payload
            ))
        return results

# Singleton
engine = RAGEngine()