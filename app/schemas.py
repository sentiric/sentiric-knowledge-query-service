# app/schemas.py
from pydantic import BaseModel, Field
from typing import List

from app.core.config import settings

class QueryResult(BaseModel):
    """Tek bir RAG arama sonucunu temsil eder."""
    content: str
    score: float
    source: str
    metadata: dict

class QueryRequest(BaseModel):
    """Knowledge Query servisine gönderilen sorgu isteği."""
    query: str
    tenant_id: str
    # top_k, 1 ile 20 arasında olmalıdır.
    top_k: int = Field(default=settings.KNOWLEDGE_QUERY_DEFAULT_TOP_K, gt=0, le=20)

class QueryResponse(BaseModel):
    """RAG aramasının sonuç listesini döndürür."""
    results: List[QueryResult]