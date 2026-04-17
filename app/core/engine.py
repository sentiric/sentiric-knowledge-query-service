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

    async def initialize(self):
        try:
            logger.info("RAG Engine: Başlatılıyor...", event_name="RAG_ENGINE_START")
            device = "cuda" if torch.cuda.is_available() else "cpu"

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

            logger.info(
                "Qdrant'a bağlanılıyor...",
                event_name="DB_CONNECTING",
                url=settings.QDRANT_HTTP_URL,
            )
            self.qdrant = AsyncQdrantClient(
                url=settings.QDRANT_HTTP_URL, api_key=settings.QDRANT_API_KEY
            )

            assert self.qdrant is not None

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
            logger.error("Qdrant connection timed out.", event_name="DB_TIMEOUT")
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
        if not self._ready or not self.model or not self.qdrant:
            return False
        try:
            await asyncio.wait_for(self.qdrant.get_collections(), timeout=5.0)
            return True
        except Exception:
            return False

    async def search(
        self, tenant_id: str, query_text: str, top_k: int = 5
    ) -> List[QueryResult]:
        if not self._ready or not self.model or not self.qdrant:
            raise RuntimeError("Engine is not ready or dependencies are None")

        collection_name = f"{settings.QDRANT_DB_COLLECTION_PREFIX}{tenant_id}"

        # [ARCH-COMPLIANCE FIX]: Qdrant'ta hem statik dosyaları hem de Crystalline
        # zihin haritasını (Kalıcı Hafıza) aramak için koleksiyon adını belirle
        mem_collection = "sentiric_user_memories"

        query_vector = self.model.encode(query_text).tolist()

        try:
            # 1. Kurumsal PDF/Web RAG Araması
            search_task = self.qdrant.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=settings.SCORE_THRESHOLD,
                with_payload=True,
            )

            # 2. Crystalline Kişisel Hafıza (Cognitive Memory) Araması
            mem_search_task = self.qdrant.search(
                collection_name=mem_collection,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=0.50,  # Hafızada eşik daha düşük olabilir
                with_payload=True,
                # Not: Biyometrik bio_id filtresi eklenebilir, şimdilik tenant_id filtresi uygulanıyor.
                query_filter={
                    "must": [{"key": "tenant_id", "match": {"value": tenant_id}}]
                },
            )

            # İki koleksiyonu paralel ara (Zero-Latency kuralı)
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

        # --- A. KURUMSAL RAG SONUÇLARI (Standard) ---
        if isinstance(search_result, list):
            for hit in search_result:
                payload = hit.payload or {}
                results.append(
                    QueryResult(
                        content=payload.get("content", ""),
                        score=hit.score,  # Sadece Vektör Benzerliği
                        source=payload.get("source_uri", "knowledge_base"),
                        metadata={"type": "static_document"},
                    )
                )

        # --- B. CRYSTALLINE BİLİŞSEL HAFIZA SONUÇLARI (Hybrid Scoring v4.0) ---
        if isinstance(mem_result, list):
            for hit in mem_result:
                payload = hit.payload or {}

                # Master Spec v4.0 Hibrit Skorlama:
                # Final_Score = (Vector_Sim * 0.6) + (Importance * 0.4)
                fact_data = payload.get("fact", {})
                importance = (
                    float(fact_data.get("importance", 3)) / 5.0
                )  # 0.0 - 1.0 arası normalize

                final_score = (hit.score * 0.6) + (importance * 0.4)

                category = fact_data.get("category", "BİLGİ").upper()
                summary = fact_data.get("summary", "")

                # LLM'in anlaması için içeriği formatla
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

        # 3. Re-Rank (Yeniden Sıralama)
        # Kurumsal belgeler ve Kişisel anıları Harmanla ve en yüksek skora göre diz
        results.sort(key=lambda x: x.score, reverse=True)

        # En iyi top_k kadarını dön
        final_results = results[:top_k]

        logger.info(
            "Hybrid RAG Search completed",
            event_name="HYBRID_RAG_SUCCESS",
            total_found=len(results),
            returned=len(final_results),
        )

        return final_results


engine = RAGEngine()
