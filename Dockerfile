### 📄 File: Dockerfile (v2.4 - Protobuf Re-compilation Fix)

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

# git ve build araçlarını kur
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .

# 1. Temel bağımlılıkları kur (grpcio-tools dahil)
RUN pip install --upgrade pip && \
    if [ "$TARGET_DEVICE" = "gpu" ]; then \
        echo "GPU imajı: PyTorch zaten mevcut, diğer bağımlılıklar kuruluyor."; \
        grep -v 'torch' requirements.txt > requirements.tmp.txt; \
        pip install --no-cache-dir -r requirements.tmp.txt; \
    else \
        echo "CPU imajı: Hafif PyTorch ve diğer bağımlılıklar kuruluyor."; \
        pip install --no-cache-dir -r requirements.txt; \
    fi

# 2. Sentiric Contracts'ı Klonla
WORKDIR /tmp/contracts
RUN git clone -b v1.9.0 https://github.com/sentiric/sentiric-contracts.git .

# 3. PROTO DOSYALARINI YENİDEN DERLE (CRITICAL FIX)
# Bu adım, contracts içindeki .proto dosyalarını bulur ve mevcut ortamın
# protobuf/grpcio versiyonlarını kullanarak Python kodlarını yeniden üretir.
# Böylece "VersionError" ortadan kalkar.
RUN echo "Proto dosyaları yeniden derleniyor..." && \
    # Proto dosyalarını bul
    find proto -name "*.proto" > protos.txt && \
    # Python paket dizinini oluştur (eğer yoksa)
    # Genelde contracts repo yapısı: proto/sentiric/... -> paket yapısı
    # Biz proto/ dizinini include path (-I) olarak kullanacağız.
    # grpc_tools.protoc ile derle
    while read p; do \
        echo "Compiling $p"; \
        python -m grpc_tools.protoc -Iproto --python_out=. --grpc_python_out=. "$p"; \
    done < protos.txt

# 4. Yeniden derlenmiş paketi kur
# Mevcut dizin (setup.py veya pyproject.toml içeren) üzerinden kurulum yap
RUN pip install --no-cache-dir .

# Çalışma dizinine geri dön
WORKDIR /app

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

EXPOSE 17020 17021 17022

CMD ["python", "-m", "app.runner"]