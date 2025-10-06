### 📄 File: `README.md` | 🏷️ Markdown

```markdown
# 📚 Sentiric Knowledge Query Service

[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![Language](https://img.shields.io/badge/language-Python-blue.svg)]()
[![Engine](https://img.shields.io/badge/engine-RAGQuery-orange.svg)]()

**Sentiric Knowledge Query Service**, Sentiric platformunun Retrieval Augmented Generation (RAG) mimarisindeki ana sorgulama bileşenidir. Görevi, Agent'ın ihtiyaç duyduğu kurumsal bilgiyi Vector Database (Qdrant) üzerinden hızlı ve alakalı bir şekilde çekmektir.

Bu servis, LLM'in halüsinasyon yapma riskini azaltmak için kritik rol oynar.

## 🎯 Temel Sorumluluklar

*   **Sorgu Vektörleştirme:** Gelen metin sorgularını Embedding Model'i kullanarak vektörlere dönüştürme.
*   **Vektör Arama:** Qdrant'ta yüksek boyutlu benzerlik aramaları yapma.
*   **Sonuç Derleme:** Çekilen en alakalı parçaları (chunks) birleştirerek LLM'in kullanabileceği nihai bağlamı oluşturma.
*   **CQRS Query:** Yalnızca okuma (Query) işlemlerini yürütür.

## 🛠️ Teknoloji Yığını

*   **Dil:** Python 3.11
*   **Web Çerçevesi:** FastAPI / Uvicorn (Yüksek I/O için)
*   **Vector DB:** Qdrant Client
*   **Embedding:** Sentence Transformers
*   **Bağımlılıklar:** `sentiric-contracts` v1.9.0

## 🔌 API Etkileşimleri

*   **Gelen (Sunucu):**
    *   `sentiric-agent-service` (gRPC): `Query` RPC'si.
*   **Giden (İstemci):**
    *   Qdrant (Vector Database).

---
## 🏛️ Anayasal Konum

Bu servis, [Sentiric Anayasası'nın](https://github.com/sentiric/sentiric-governance) **Horizontal Capability Layer**'ında yer alan uzman bir bileşendir.