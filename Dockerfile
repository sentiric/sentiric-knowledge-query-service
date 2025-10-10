# --- STAGE 1: Builder ---
FROM python:3.11-slim-bullseye AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    git && \
    rm -rf /var/lib/apt/lists/*

# TAVSİYE: Kararlı ve modern bir Poetry versiyonu kullan
RUN pip install poetry==1.8.2

RUN poetry config virtualenvs.create false

ARG GIT_COMMIT="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_VERSION="0.0.0"

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --no-root
COPY app ./app
COPY README.md .

# --- STAGE 2: Production (Değişiklik yok) ---
FROM python:3.11-slim-bullseye
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    curl \
    ca-certificates \
    libgomp1 && \
    rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1001 appuser
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app/app ./app
RUN chown -R appuser:appuser /app
ARG GIT_COMMIT
ARG BUILD_DATE
ARG SERVICE_VERSION
ENV GIT_COMMIT=${GIT_COMMIT}
ENV BUILD_DATE=${BUILD_DATE}
ENV SERVICE_VERSION=${SERVICE_VERSION}
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "12041"]