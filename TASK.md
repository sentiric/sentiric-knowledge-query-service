# File: task.md

## Observability (Tracing) Compliance Task

**Tarih:** 2026-03-15
**Servis:** `sentiric-knowledge-query-service`
**Görev Tipi:** Architectural Compliance (Mimari Uyumluluk)
**İlgili Kural:** `constraints.yaml` -> "Tüm senkron ve asenkron iletişimlerde 'trace_id' context propagation ile taşınmalıdır."

### Yapılan İşlemler:
1. **HTTP Katmanı (FastAPI):**
   - `app/main.py` dosyasına asenkron `trace_id_middleware` eklendi.
   - Her gelen istek için `x-trace-id` header'ı kontrol edildi. Eğer yoksa benzersiz bir UUID (hex) üretildi.
   - Üretilen veya okunan bu trace ID, `structlog.contextvars.bind_contextvars` yardımıyla yapılandırılmış log engine'ine (structlog) bağlandı. Artık loglar otomatik olarak bu benzersiz ID'yi STDOUT'a json formatında basacak.
   - Dönüş yanıtlarına (Response) `x-trace-id` header'ı eklendi.

2. **gRPC Katmanı:**
   - `app/grpc/service.py` içerisindeki `KnowledgeQueryServicer.Query` metoduna interceptor mantığı uygulandı.
   - `context.invocation_metadata()` üzerinden gRPC metadata header'ları tarandı.
   - Bulunan veya sıfırdan oluşturulan `x-trace-id`, yine `structlog` contextvars'a bind edilerek engine katmanlarına (Search, Vektörizasyon işlemleri) kadar inen logların izlenebilir olması sağlandı.

3. **Güvenlik / State Koruması:**
   - Her iki entegrasyon noktasında da asenkron framework'lerde context sızıntılarını önlemek adına işleme başlamadan önce `clear_contextvars()` komutu koşturuldu.

**Durum:** Başarılı (✅). Artık tüm mikroservis zincirinde tek bir isteğin yolculuğu izlenebilir hale geldi.