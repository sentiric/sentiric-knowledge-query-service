# Dockerfile - v3 FINAL - Optimized with Multi-Stage Build

# ==============================================================================
# STAGE 1: Builder
# Bu aşamada tüm ağır işler yapılır: derleme, paket indirme vs.
# ==============================================================================
FROM python:3.11-slim-bullseye AS builder

WORKDIR /app

# Sistem bağımlılıklarını kur
# git: Git bağımlılıkları için
# build-essential: C++ derlemesi gerektiren paketler için (torch, tokenizers vs.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# requirements.txt dosyasını kopyala
COPY requirements.txt .

# Sanal bir ortam oluşturup paketleri buraya kuracağız.
# Bu, sadece gereken dosyaları bir sonraki aşamaya taşımayı kolaylaştırır.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# pip'i güncelleyip paketleri kuralım
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ==============================================================================
# STAGE 2: Final Image
# Bu aşama, sadece uygulamanın çalışması için gerekenleri içerir. Küçük ve güvenli.
# ==============================================================================
FROM python:3.11-slim-bullseye

WORKDIR /app

# Sadece RUNTIME için gereken sistem kütüphanelerini kur. Derleyiciler yok!
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    curl \
    ca-certificates \
    libgomp1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Güvenlik için non-root kullanıcı oluştur
RUN useradd --create-home --shell /bin/bash --uid 1001 appuser

# Builder aşamasından SADECE kurulu paketleri (sanal ortamı) kopyala
COPY --chown=appuser:appuser --from=builder /opt/venv /opt/venv

# Uygulama kodunu kopyala
COPY --chown=appuser:appuser app ./app

# Ortam değişkenlerini ayarla
ARG GIT_COMMIT
ARG BUILD_DATE
ARG SERVICE_VERSION
ENV GIT_COMMIT=${GIT_COMMIT}
ENV BUILD_DATE=${BUILD_DATE}
ENV SERVICE_VERSION=${SERVICE_VERSION}

# Sanal ortamın PATH'ini aktif hale getir
ENV PATH="/opt/venv/bin:$PATH"

# Kullanıcıyı değiştir
USER appuser

# Uygulamayı çalıştır
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "12401"]