# 🧠 Sentiric Knowledge Query Service (RAG Engine)

[![Status](https://img.shields.io/badge/status-production_ready-green.svg)]()
[![Architecture](https://img.shields.io/badge/architecture-hybrid_async-blue.svg)]()

Sentiric Knowledge Query Service, metin tabanlı sorguları anlamlandıran, vektörleştiren ve en alakalı bilgileri getiren yüksek performanslı bir **RAG (Retrieval-Augmented Generation) Motorudur.**

Bu servis **iki modda** çalışabilir:
1.  **Standalone (Bağımsız):** Tek başına bir konteyner olarak çalışır. Sertifika gerektirmez. Herhangi bir uygulama (Web UI, Chatbot) için RAG backend'i sağlar.
2.  **Cluster (Sentiric Ekosistemi):** mTLS ile güvenli, dağıtık mimarinin bir parçası olarak çalışır.

---

## 🚀 Özellikler

*   **Hybrid Compute:** Ağır model işlemleri (CPU) ve veritabanı sorguları (I/O) birbirini bloklamaz.
*   **Auto-Model Management:** Gerekli AI modellerini (`sentence-transformers`) otomatik indirir ve cache'ler.
*   **Fail-Safe Security:** Sertifikalar varsa otomatik şifreler (mTLS), yoksa geliştirici modunda (Insecure) açılır.
*   **Deep Healthcheck:** Sadece "ayaktayım" demez, Vektör DB bağlantısını ve model sağlığını test eder.

---

## ⚡ Hızlı Başlangıç (Tak-Çalıştır)

### Ön Gereksinim
*   Docker

### 1. Tek Komutla Başlat
Sadece bu servisi ve veritabanını (Qdrant) ayağa kaldırmak için:

```bash
# Geliştirme/Standalone Modu
make up
```

### 2. Sorgu Yap (cURL / Open Web UI)
Servis ayağa kalktığında `http://localhost:17020` adresinden dinler.

**Örnek Sorgu:**
```bash
curl -X POST "http://localhost:17020/api/v1/query" \
     -H "Content-Type: application/json" \
     -d '{
           "tenant_id": "sentiric_demo",
           "query": "Platformun temel özellikleri nelerdir?",
           "top_k": 3
         }'
```

**Yanıt:**
```json
{
  "results": [
    {
      "content": "Sentiric, iletişim süreçlerini otomatize eden...",
      "score": 0.85,
      "source": "platform_overview.md",
      "metadata": { ... }
    }
  ]
}
```

---

## 🛠️ Yapılandırma (.env)

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `QDRANT_HTTP_URL` | `http://qdrant:6333` | Vektör veritabanı adresi |
| `KNOWLEDGE_QUERY_DEFAULT_TOP_K` | `5` | Varsayılan sonuç sayısı |
| `GRPC_TLS_CA_PATH` | (Boş) | Tanımlanırsa mTLS devreye girer |

---

## 🧩 Entegrasyon Rehberi

### Open Web UI / LangChain Entegrasyonu
Bu servis standart bir REST API sunar. Herhangi bir LLM zincirine (Chain) "Retriever" olarak eklenebilir.

1.  **Endpoint:** `POST /api/v1/query`
2.  **Input:** `{"query": "soru", "tenant_id": "kimlik"}`
3.  **Output:** Context metinleri listesi.

### gRPC Entegrasyonu (Yüksek Performans)
Internal microservice iletişimi için `sentiric-contracts` kütüphanesini kullanın.
```python
# Python Örneği
stub = query_pb2_grpc.KnowledgeQueryServiceStub(channel)
response = stub.Query(query_pb2.QueryRequest(tenant_id="demo", query="test"))
```
