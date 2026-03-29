### 📄 File: Dockerfile (Her iki servis için geçerlidir)

ARG TARGET_DEVICE=cpu
ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-slim-bullseye AS cpu-base
FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime AS gpu-base

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

RUN pip install --upgrade pip && \
    if [ "$TARGET_DEVICE" = "gpu" ]; then \
        echo "GPU imajı: PyTorch zaten mevcut, diğer bağımlılıklar kuruluyor."; \
        grep -v 'torch' requirements.txt > requirements.tmp.txt; \
        pip install --no-cache-dir -r requirements.tmp.txt; \
    else \
        echo "CPU imajı: Hafif PyTorch ve diğer bağımlılıklar kuruluyor."; \
        pip install --no-cache-dir -r requirements.txt; \
    fi

WORKDIR /tmp/contracts
RUN git clone -b v1.9.0 https://github.com/sentiric/sentiric-contracts.git .

RUN echo "Proto dosyaları yeniden derleniyor..." && \
    find proto -name "*.proto" > protos.txt && \
    while read p; do \
        echo "Compiling $p"; \
        python -m grpc_tools.protoc -Iproto --python_out=. --grpc_python_out=. "$p"; \
    done < protos.txt

RUN pip install --no-cache-dir .

WORKDIR /app

# ==================================
#      Aşama 2: Final Image
# ==================================
FROM base AS final

WORKDIR /app

ARG GIT_COMMIT="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_VERSION="0.0.0"

# [ARCH-COMPLIANCE] HF_HUB_DISABLE_PROGRESS_BARS eklendi! JSON logları parçalamaması için şarttır.
ENV GIT_COMMIT=${GIT_COMMIT} \
    BUILD_DATE=${BUILD_DATE} \
    SERVICE_VERSION=${SERVICE_VERSION} \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME="/app/model-cache" \
    HF_HUB_DISABLE_PROGRESS_BARS=1 \
    TOKENIZERS_PARALLELISM=false

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

# Indexing service için manage.py kopyalama satırı (Query serviste yok)
# COPY --chown=appuser:appgroup manage.py .

RUN mkdir -p /app/model-cache && \
    chown -R appuser:appgroup /app/model-cache

USER appuser

# Query: 17020 17021 17022
EXPOSE 17020 17021 17022

CMD ["python", "-m", "app.runner"]