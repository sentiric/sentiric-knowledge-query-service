### 📄 File: knowledge-query-service/Dockerfile (GÜNCELLENMİŞ)

ARG PYTHON_VERSION=3.11
ARG BASE_IMAGE_TAG=${PYTHON_VERSION}-slim-bullseye
ARG TORCH_INDEX_URL="--extra-index-url https://download.pytorch.org/whl/cpu"

FROM python:${BASE_IMAGE_TAG} AS builder
# ... (builder aşaması aynı kalır) ...
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt ${TORCH_INDEX_URL}

FROM python:${BASE_IMAGE_TAG}
WORKDIR /app
ARG GIT_COMMIT="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_VERSION="0.0.0"
ENV GIT_COMMIT=${GIT_COMMIT} BUILD_DATE=${BUILD_DATE} SERVICE_VERSION=${SERVICE_VERSION} PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH" \
    # --- YENİ EKLENEN SATIR ---
    # Hugging Face cache dizinini /app/model-cache olarak ayarla
    HF_HOME="/app/model-cache"

RUN apt-get update && apt-get install -y --no-install-recommends netcat-openbsd curl ca-certificates libgomp1 && rm -rf /var/lib/apt/lists/*
RUN adduser --system --no-create-home --uid 1001 appuser
COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv
COPY --chown=appuser:appuser app ./app

# --- YENİ EKLENEN BÖLÜM ---
# Model cache dizinini oluştur ve sahipliğini appuser'a ver.
RUN mkdir -p /app/model-cache && \
    chown -R appuser:appgroup /app/model-cache
# --- BÖLÜM SONU ---

USER appuser
EXPOSE 17020 17021 17022
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "17020"]