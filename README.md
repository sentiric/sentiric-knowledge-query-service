# 📚 Sentiric Knowledge Query Service

[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![Language](https://img.shields.io/badge/language-Python_3.11-blue.svg)]()
[![Framework](https://img.shields.io/badge/framework-FastAPI_&_gRPC-teal.svg)]()

**Sentiric Knowledge Query Service**, Sentiric platformunun Retrieval-Augmented Generation (RAG) mimarisindeki ana sorgulama bileşenidir. Görevi, `agent-service` gibi iç servislerden gelen doğal dil sorgularını alarak, Vector Database (Qdrant) üzerinden en alakalı kurumsal bilgiyi hızlı ve verimli bir şekilde çekmektir.

Bu servis, CQRS prensibine uygun olarak sadece **Okuma (Query)** işlemlerini yürütür ve LLM'in halüsinasyon yapma riskini azaltmada kritik rol oynar. Servis, hem **HTTP/REST** hem de yüksek performanslı **gRPC** arayüzleri sunar.

---

## 🎯 Temel Sorumluluklar

*   **Sorgu Vektörleştirme:** Gelen metin sorgularını `sentence-transformers` modeliyle anlamsal vektörlere dönüştürme.
*   **Vektör Arama:** Qdrant üzerinde yüksek boyutlu benzerlik aramaları yaparak en alakalı bilgi parçacıklarını (`chunks`) bulma.
*   **Sonuç Derleme:** Çekilen sonuçları standart `QueryResponse` formatında birleştirerek istemci servise sunma.
*   **Hızlı Başlangıç & Sağlık Kontrolü:** Servis hızla başlar, ancak model ve veritabanı bağlantısı gibi ağır bağımlılıklar hazır olana kadar `503 Service Unavailable` durum kodu döner.

---

## 🛠️ Teknoloji Yığını

*   **Dil:** Python 3.11
*   **Web Çerçevesi:** FastAPI & Uvicorn (HTTP için)
*   **RPC Çerçevesi:** gRPC (Dahili iletişim için)
*   **Vektör Veritabanı:** Qdrant Client
*   **Embedding Modeli:** Sentence Transformers
*   **Paket Yönetimi:** Poetry
*   **Loglama:** Structlog (JSON formatında)
*   **API Kontratları:** `sentiric-contracts` v1.9.0

---

## 🚀 Yerel Geliştirme Ortamı

### 1. Ön Gereksinimler
*   Python 3.11+
*   Poetry
*   Docker (Qdrant için)

### 2. Kurulum
```bash
# Bağımlılıkları kur
poetry install

# Qdrant'ı Docker ile başlat
docker run -p 6333:6333 qdrant/qdrant
```

### 3. Yapılandırma
Proje kök dizininde `.env` adında bir dosya oluşturun ve gerekli ortam değişkenlerini tanımlayın:
```env
# .env
ENV="development"
LOG_LEVEL="DEBUG"
QDRANT_HTTP_URL="http://localhost:6333"
KNOWLEDGE_QUERY_SERVICE_HTTP_PORT=17020
KNOWLEDGE_QUERY_SERVICE_GRPC_PORT=17021
```

### 4. Çalıştırma
```bash
poetry run python -m app.runner
```
Servis artık HTTP için `http://localhost:17020`, gRPC için `localhost:17021` adreslerinde çalışacaktır. API dokümantasyonuna `http://localhost:17020/docs` adresinden erişebilirsiniz.

---

## 🐳 Docker ile Çalıştırma

Proje, hem CPU hem de GPU için optimize edilmiş Docker imajları oluşturabilir.

```bash
# CPU imajı oluşturma (varsayılan)
docker build -t sentiric-knowledge-query-service:latest .

# GPU imajı oluşturma
docker build --build-arg TARGET_DEVICE=gpu -t sentiric-knowledge-query-service:gpu .

# CPU imajını çalıştırma
docker run -p 17020:17020 -p 17021:17021 \
  -v ./model-cache:/app/model-cache \
  -e QDRANT_HTTP_URL="http://<qdrant_ip>:6333" \
  sentiric-knowledge-query-service:latest
```
- `-v ./model-cache:/app/model-cache` bağlaması, embedding modelinin her container başlatıldığında tekrar indirilmesini önler.
```

---

### Özetle Yapılanlar:

1.  **Bağımlılıklar Eklendi:** `grpcio` ve `grpcio-tools` kütüphaneleri projeye dahil edildi.
2.  **Eş Zamanlı Sunucu Yapısı:** Hem FastAPI (HTTP) hem de gRPC sunucularını aynı anda başlatabilen bir `app/runner.py` script'i oluşturuldu.
3.  **gRPC Servisi Implementasyonu:** `sentiric-contracts` deposundaki `.proto` tanımına uygun olarak `KnowledgeQueryServicer` sınıfı yazıldı.
4.  **Kod Tekrarı Önleme:** HTTP ve gRPC endpoint'leri, `_perform_query` adında ortak bir fonksiyonu kullanarak aynı iş mantığını paylaştı.
5.  **Yaşam Döngüsü Yönetimi:** Uygulamanın `lifespan` yöneticisi, başlatma ve kapatma sırasında gRPC sunucusunu da yönetecek şekilde güncellendi.
6.  **Docker Entegrasyonu:** `Dockerfile`, uygulamayı `uvicorn` yerine yeni `runner` script'i üzerinden başlatacak şekilde ayarlandı.
7.  **Dokümantasyon:** `README.md`, yeni gRPC yeteneğini, güncellenmiş çalıştırma komutlarını ve teknoloji yığınını yansıtacak şekilde güncellendi.

### gRPC Arayüzünü Test Etme

Platform `docker-compose` ile çalıştırıldıktan sonra, aşağıdaki `grpcurl` komutu ile gRPC endpoint'ini test edebilirsiniz:

```bash
# Proto dosyasının bulunduğu dizinde çalıştırın (sentiric-contracts/proto)
grpcurl -plaintext \
  -proto sentiric/knowledge/v1/query.proto \
  -d '{"tenant_id": "sentiric_demo", "query": "platform overview", "top_k": 2}' \
  localhost:17021 \
  sentiric.knowledge.v1.KnowledgeQueryService/Query
```