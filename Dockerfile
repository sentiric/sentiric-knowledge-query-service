### 📄 File: knowledge-query-service/Dockerfile (YENİ STANDART)

ARG PYTHON_VERSION=3.11
ARG BASE_IMAGE_TAG=${PYTHON_VERSION}-slim-bullseye
# Build sırasında hangi torch versiyonunun kurulacağını belirler (CPU/GPU)
ARG TORCH_INDEX_URL="--extra-index-url https://download.pytorch.org/whl/cpu"

# ==================================
#      Aşama 1: Builder
# ==================================
FROM python:${BASE_IMAGE_TAG} AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
# Builder aşamasında Torch'u ve diğer bağımlılıkları kur
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt ${TORCH_INDEX_URL}

# ==================================
#      Aşama 2: Final Image
# ==================================
FROM python:${BASE_IMAGE_TAG}
WORKDIR /app
ARG GIT_COMMIT="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_VERSION="0.0.0"
ENV GIT_COMMIT=${GIT_COMMIT} BUILD_DATE=${BUILD_DATE} SERVICE_VERSION=${SERVICE_VERSION} PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH" \
    # Hugging Face cache dizinini, yazma iznimiz olan bir yere yönlendiriyoruz
    HF_HOME="/app/model-cache"

# Sadece çalışma zamanı için gerekli sistem kütüphaneleri
RUN apt-get update && apt-get install -y --no-install-recommends netcat-openbsd curl ca-certificates libgomp1 && rm -rf /var/lib/apt/lists/*

# Root olmayan kullanıcı oluştur
RUN addgroup --system --gid 1001 appgroup && adduser --system --no-create-home --uid 1001 --ingroup appgroup appuser

# Builder'dan sanal ortamı kopyala
COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv
# Uygulama kodunu kopyala
COPY --chown=appuser:appuser app ./app

# Model cache dizinini oluştur ve sahipliğini appuser'a ver
RUN mkdir -p /app/model-cache && \
    chown -R appuser:appgroup /app/model-cache

USER appuser
EXPOSE 17020 17021 17022
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "17020"]