# app/core/engine.py
import asyncio
import structlog
from typing import List, Optional
from sentence_transformers import SentenceTransformer
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
from app.core.config import settings
from app.schemas import QueryResult

logger = structlog.get_logger(__name__)

class RAGEngine:
    """
    Retrieval-Augmented Generation (RAG) motorunun çekirdeği.
    Modeli yönetir, vektörleştirmeyi yapar ve DB sorgularını yürütür.
    Singleton pattern'e uygun tasarlanmıştır.
    """
    def __init__(self):
        self.model: Optional[SentenceTransformer] = None
        self.qdrant: Optional[AsyncQdrantClient] = None
        self._ready = False

    async def initialize(self):
        """Motoru başlatır: Modeli yükler ve DB bağlantısını kurar."""
        try:
            logger.info("RAG Engine: Başlatılıyor...")

            # 1. Embedding Modelini Yükle (CPU-Bound, Thread'e atıyoruz)
            logger.info(f"Model yükleniyor: {settings.QDRANT_DB_EMBEDDING_MODEL_NAME}")
            self.model = await asyncio.to_thread(
                SentenceTransformer,
                settings.QDRANT_DB_EMBEDDING_MODEL_NAME,
                cache_folder=settings.HF_HOME
            )
            
            # 2. Qdrant Bağlantısı (I/O Bound, Async Client)
            logger.info(f"Qdrant'a bağlanılıyor: {settings.QDRANT_HTTP_URL}")
            self.qdrant = AsyncQdrantClient(
                url=settings.QDRANT_HTTP_URL,
                api_key=settings.QDRANT_API_KEY
            )
            
            # Bağlantı Testi
            collections = await self.qdrant.get_collections()
            logger.info(f"Qdrant bağlantısı başarılı. Mevcut koleksiyon sayısı: {len(collections.collections)}")

            self._ready = True
            logger.info("RAG Engine: Hazır.")
        except Exception as e:
            self._ready = False
            logger.critical("RAG Engine başlatılamadı!", error=str(e))
            raise e

    async def shutdown(self):
        """Kaynakları temizler."""
        if self.qdrant:
            await self.qdrant.close()
        self._ready = False
        logger.info("RAG Engine: Kapatıldı.")

    async def check_health(self) -> bool:
        """Derin sağlık kontrolü yapar."""
        if not self._ready or not self.model:
            return False
        try:
            # DB'nin canlı olup olmadığını kontrol et
            await self.qdrant.get_collections()
            return True
        except Exception:
            return False

    async def search(self, tenant_id: str, query_text: str, top_k: int = 5) -> List[QueryResult]:
        """
        Verilen metni vektörleştirir ve ilgili tenant koleksiyonunda arar.
        """
        if not self._ready:
            raise RuntimeError("Engine is not ready")

        collection_name = f"{settings.QDRANT_DB_COLLECTION_PREFIX}{tenant_id}"
        
        # 1. Vektörleştirme (Thread Pool'da çalışır - Blocking engelleme)
        query_vector = await asyncio.to_thread(self.model.encode, query_text)
        query_vector_list = query_vector.tolist()

        # 2. Vektör Arama (Async - Non-blocking)
        try:
            search_result = await self.qdrant.search(
                collection_name=collection_name,
                query_vector=query_vector_list,
                limit=top_k,
                score_threshold=settings.SCORE_THRESHOLD,
                with_payload=True
            )
        except Exception as e:
            # Koleksiyon yoksa boş dön (İlk kurulumda normaldir)
            if "Not found: Collection" in str(e) or "404" in str(e):
                logger.warning(f"Koleksiyon bulunamadı: {collection_name}")
                return []
            logger.error("Qdrant arama hatası", error=str(e))
            raise e

        # 3. Sonuçları Dönüştürme
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

# Global Singleton Instance
engine = RAGEngine()