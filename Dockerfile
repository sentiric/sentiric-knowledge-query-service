### 📄 File: knowledge-query-service/Dockerfile (DÜZELTİLMİŞ)

# ==============================================================================
# STAGE 1: Builder
# ==============================================================================
FROM python:3.11-slim-bullseye AS builder

ARG TORCH_INDEX_URL

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git build-essential && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt ${TORCH_INDEX_URL}


# ==============================================================================
# STAGE 2: Final Image
# ==============================================================================
FROM python:3.11-slim-bullseye

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends netcat-openbsd curl ca-certificates libgomp1 && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash --uid 1001 appuser

COPY --chown=appuser:appgroup --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appgroup app ./app

ARG GIT_COMMIT
ARG BUILD_DATE
ARG SERVICE_VERSION
ENV GIT_COMMIT=${GIT_COMMIT} BUILD_DATE=${BUILD_DATE} SERVICE_VERSION=${SERVICE_VERSION}
ENV PATH="/opt/venv/bin:$PATH"

USER appuser

# --- DÜZELTME: uvicorn komutunu tam yoluyla çağırıyoruz ---
CMD ["/opt/venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "12401"]