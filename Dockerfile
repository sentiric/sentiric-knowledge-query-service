### 📄 File: Dockerfile (YENİ VE DÜZELTİLMİŞ VERSİYON - v2.1)
# Bu Dockerfile, hem CPU hem de GPU imajlarını dinamik ve uyumlu bir şekilde oluşturur.

# --- Build Argümanları ---
ARG TARGET_DEVICE=cpu
ARG PYTHON_VERSION=3.11

# --- Temel İmajları Tanımlama ---
FROM python:${PYTHON_VERSION}-slim-bullseye AS cpu-base
FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime AS gpu-base

# --- Hedef İmajı Seçme ---
FROM ${TARGET_DEVICE}-base AS base

# ==================================
#      Aşama 1: Builder
# ==================================
FROM base AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .

# --- DÜZELTİLMİŞ VE DAHA SAĞLAM BAĞIMLILIK KURULUMU ---
# Process substitution (<(...)) yerine standart shell komutları kullanıyoruz.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    if [ "$TARGET_DEVICE" = "gpu" ]; then \
        echo "GPU imajı: PyTorch zaten mevcut, diğer bağımlılıklar kuruluyor."; \
        # 'torch' içeren satırları atlayarak geçici bir requirements dosyası oluştur
        grep -v 'torch' requirements.txt > requirements.tmp.txt; \
        pip install --no-cache-dir -r requirements.tmp.txt; \
    else \
        echo "CPU imajı: Hafif PyTorch ve diğer bağımlılıklar kuruluyor."; \
        pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu; \
    fi

# ==================================
#      Aşama 2: Final Image
# ==================================
FROM base AS final

WORKDIR /app

ARG GIT_COMMIT="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_VERSION="0.0.0"
ENV GIT_COMMIT=${GIT_COMMIT} \
    BUILD_DATE=${BUILD_DATE} \
    SERVICE_VERSION=${SERVICE_VERSION} \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME="/app/model-cache"

RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    curl \
    ca-certificates \
    libpq5 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --no-create-home --uid 1001 --ingroup appgroup appuser

COPY --from=builder --chown=appuser:appgroup /opt/venv /opt/venv
COPY --chown=appuser:appgroup app ./app

RUN mkdir -p /app/model-cache && \
    chown -R appuser:appgroup /app/model-cache

USER appuser

# knowledge-query-service için:
EXPOSE 17020 17021 17022

# knowledge-query-service için:
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "17020", "--no-access-log"]