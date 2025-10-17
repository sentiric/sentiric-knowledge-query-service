# 📚 Sentiric Knowledge Query Service

[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![Language](https://img.shields.io/badge/language-Python_3.11-blue.svg)]()
[![Framework](https://img.shields.io/badge/framework-FastAPI-teal.svg)]()

**Sentiric Knowledge Query Service**, Sentiric platformunun Retrieval-Augmented Generation (RAG) mimarisindeki ana sorgulama bileşenidir. Görevi, `agent-service` gibi iç servislerden gelen doğal dil sorgularını alarak, Vector Database (Qdrant) üzerinden en alakalı kurumsal bilgiyi hızlı ve verimli bir şekilde çekmektir.

Bu servis, CQRS prensibine uygun olarak sadece **Okuma (Query)** işlemlerini yürütür ve LLM'in halüsinasyon yapma riskini azaltmada kritik rol oynar.

---

## 🎯 Temel Sorumluluklar

*   **Sorgu Vektörleştirme:** Gelen metin sorgularını `sentence-transformers` modeliyle anlamsal vektörlere dönüştürme.
*   **Vektör Arama:** Qdrant üzerinde yüksek boyutlu benzerlik aramaları yaparak en alakalı bilgi parçacıklarını (`chunks`) bulma.
*   **Sonuç Derleme:** Çekilen sonuçları standart bir `QueryResponse` formatında birleştirerek istemci servise sunma.
*   **Hızlı Başlangıç & Sağlık Kontrolü:** Servis hızla başlar, ancak model ve veritabanı bağlantısı gibi ağır bağımlılıklar hazır olana kadar `503 Service Unavailable` durum kodu döner.

---

## 🛠️ Teknoloji Yığını

*   **Dil:** Python 3.11
*   **Web Çerçevesi:** FastAPI & Uvicorn
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
# QDRANT_API_KEY= # Gerekliyse ekleyin
```

### 4. Çalıştırma
```bash
poetry run uvicorn app.main:app --reload
```
Servis artık `http://localhost:8000` adresinde çalışacaktır. API dokümantasyonuna `http://localhost:8000/docs` adresinden erişebilirsiniz.

---

## 🐳 Docker ile Çalıştırma

Proje, hem CPU hem de GPU için optimize edilmiş Docker imajları oluşturabilir.

```bash
# CPU imajı oluşturma (varsayılan)
docker build -t sentiric-knowledge-query-service:latest .

# GPU imajı oluşturma
docker build --build-arg TARGET_DEVICE=gpu -t sentiric-knowledge-query-service:gpu .

# CPU imajını çalıştırma
docker run -p 17020:17020 \
  -v ./model-cache:/app/model-cache \
  -e QDRANT_HTTP_URL="http://<qdrant_ip>:6333" \
  sentiric-knowledge-query-service:latest
```
- `-v ./model-cache:/app/model-cache` bağlaması, embedding modelinin her container başlatıldığında tekrar indirilmesini önler.
