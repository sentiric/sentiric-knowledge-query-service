# app/core/engine.py
import asyncio
import json
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

    def _load_model_sync(self):
        """Modeli senkron olarak yükler (to_thread ile çağrılacak)"""
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(
            "Model arka planda yükleniyor...",
            event_name="MODEL_LOADING_BG",
            model=settings.QDRANT_DB_EMBEDDING_MODEL_NAME,
            device=device,
        )
        return SentenceTransformer(
            settings.QDRANT_DB_EMBEDDING_MODEL_NAME,
            cache_folder=settings.HF_HOME,
            device=device,
        )

    async def initialize(self):
        logger.info("RAG Engine: Başlatılıyor...", event_name="RAG_ENGINE_START")

        # [ARCH-COMPLIANCE FIX]: Asla Event Loop'u bloklama!
        # Modeli ayrı bir OS Thread üzerinde yükle.
        try:
            self.model = await asyncio.to_thread(self._load_model_sync)
            logger.info("Model başarıyla yüklendi.", event_name="MODEL_LOADED")
        except Exception as e:
            logger.critical(
                "Model yüklenemedi!", event_name="MODEL_LOAD_FAIL", error=str(e)
            )
            raise e

        # Qdrant İstemcisini Oluştur (Bu işlem ağa gitmez, sadece objeyi yaratır)
        self.qdrant = AsyncQdrantClient(
            url=settings.QDRANT_HTTP_URL, api_key=settings.QDRANT_API_KEY
        )

        # [ARCH-COMPLIANCE FIX]: Zero-Dependency Boot (Ghost Mode)
        # Qdrant'a bağlanmayı dene, DNS yoksa çökme, arka planda tekrar dene.
        try:
            await asyncio.wait_for(self.qdrant.get_collections(), timeout=3.0)
            self._ready = True
            logger.info("Qdrant bağlantısı başarılı.", event_name="DB_CONNECTED")
        except Exception as e:
            self._ready = False
            logger.warning(
                "Qdrant ağına ulaşılamadı (DNS/Timeout). Servis Ghost Mode'da ayağa kalkıyor. Arka planda tekrar denenecek.",
                event_name="DB_CONNECT_FAIL_GHOST_MODE",
                error=str(e),
            )
            # Ana thread'i bloklamadan arka planda bağlanmaya çalış
            asyncio.create_task(self._background_reconnect())

    async def _background_reconnect(self):
        """Qdrant ayağa kalkana kadar sessizce bağlanmayı dener (Auto-Healing)"""
        backoff = 5
        while not self._ready:
            await asyncio.sleep(backoff)
            try:
                if self.qdrant:
                    await asyncio.wait_for(self.qdrant.get_collections(), timeout=3.0)
                    self._ready = True
                    logger.info(
                        "Qdrant is back online. Syncing restored.",
                        event_name="DB_RECONNECTED",
                    )
                    break
            except Exception:
                backoff = min(backoff * 2, 60)  # Exponential backoff (max 60s)

    async def shutdown(self):
        if self.qdrant:
            await self.qdrant.close()
        self._ready = False
        logger.info("RAG Engine: Kapatıldı.", event_name="RAG_ENGINE_STOPPED")

    async def check_health(self) -> bool:
        if not self._ready or not self.model or not self.qdrant:
            return False
        return True

    async def search(
        self, tenant_id: str, query_text: str, top_k: int = 5
    ) -> List[QueryResult]:
        if not self._ready or not self.model or not self.qdrant:
            logger.warning(
                "Search rejected: Engine is in Ghost Mode (Qdrant offline)",
                event_name="RAG_SEARCH_REJECTED",
            )
            raise RuntimeError("Engine is currently in Ghost Mode (Qdrant offline)")

        collection_name = f"{settings.QDRANT_DB_COLLECTION_PREFIX}{tenant_id}"
        mem_collection = "sentiric_user_memories"

        query_vector = self.model.encode(query_text).tolist()

        try:
            search_task = self.qdrant.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=settings.SCORE_THRESHOLD,
                with_payload=True,
            )

            mem_search_task = self.qdrant.search(
                collection_name=mem_collection,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=0.50,
                with_payload=True,
                query_filter={
                    "must": [{"key": "tenant_id", "match": {"value": tenant_id}}]
                },
            )

            search_result, mem_result = await asyncio.wait_for(
                asyncio.gather(search_task, mem_search_task, return_exceptions=True),
                timeout=5.0,
            )

        except asyncio.TimeoutError:
            logger.error("Qdrant search timed out.", event_name="DB_SEARCH_TIMEOUT")
            raise TimeoutError("Vector DB request timed out")
        except Exception as e:
            logger.error(
                "Qdrant arama hatası",
                event_name="DB_SEARCH_ERROR",
                error=str(e),
                exc_info=True,
            )
            raise e

        results = []

        # --- A. KURUMSAL RAG SONUÇLARI ---
        if isinstance(search_result, list):
            for hit in search_result:
                payload = hit.payload or {}
                results.append(
                    QueryResult(
                        content=payload.get("content", ""),
                        score=hit.score,
                        source=payload.get("source_uri", "knowledge_base"),
                        metadata={"type": "static_document"},
                    )
                )

        # --- B. CRYSTALLINE BİLİŞSEL HAFIZA SONUÇLARI ---
        if isinstance(mem_result, list):
            for hit in mem_result:
                payload = hit.payload or {}
                fact_data = payload.get("fact", {})
                importance = float(fact_data.get("importance", 3)) / 5.0
                final_score = (hit.score * 0.6) + (importance * 0.4)

                category = fact_data.get("category", "BİLGİ").upper()
                summary = fact_data.get("summary", "")
                formatted_content = f"[{category}]: {summary}"

                results.append(
                    QueryResult(
                        content=formatted_content,
                        score=final_score,
                        source="cognitive_memory",
                        metadata={
                            "type": "personal_memory",
                            "raw": json.dumps(fact_data),
                        },
                    )
                )

        results.sort(key=lambda x: x.score, reverse=True)
        final_results = results[:top_k]

        logger.info(
            "Hybrid RAG Search completed",
            event_name="HYBRID_RAG_SUCCESS",
            total_found=len(results),
            returned=len(final_results),
        )

        return final_results


engine = RAGEngine()
