# Dockerfile - v4 FINAL - Flexible CPU/GPU builds with Multi-Stage

# ==============================================================================
# STAGE 1: Builder
# ==============================================================================
FROM python:3.11-slim-bullseye AS builder

# Build argümanını en başta tanımla
ARG TORCH_INDEX_URL

WORKDIR /app

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# requirements.txt dosyasını kopyala
COPY requirements.txt .

# Sanal ortam oluştur
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# pip'i güncelle
RUN pip install --upgrade pip

# *** 💡 AKILLI KURULUM BURADA 💡 ***
# requirements.txt'deki torch'u kur, ama build argümanıyla gelen
# özel index'i kullanarak (eğer varsa).
RUN pip install --no-cache-dir -r requirements.txt ${TORCH_INDEX_URL}


# ==============================================================================
# STAGE 2: Final Image
# ==============================================================================
FROM python:3.11-slim-bullseye

WORKDIR /app

# Sadece runtime için gereken sistem kütüphaneleri
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    curl \
    ca-certificates \
    libgomp1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Non-root kullanıcı
RUN useradd --create-home --shell /bin/bash --uid 1001 appuser

# Builder'dan sanal ortamı kopyala
COPY --chown=appuser:appuser --from=builder /opt/venv /opt/venv

# Uygulama kodunu kopyala
COPY --chown=appuser:appuser app ./app

# Ortam değişkenleri
ARG GIT_COMMIT
ARG BUILD_DATE
ARG SERVICE_VERSION
ENV GIT_COMMIT=${GIT_COMMIT}
ENV BUILD_DATE=${BUILD_DATE}
ENV SERVICE_VERSION=${SERVICE_VERSION}

# Sanal ortamı PATH'e ekle
ENV PATH="/opt/venv/bin:$PATH"

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "12401"]