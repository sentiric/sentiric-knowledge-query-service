### 📄 File: Dockerfile (YENİ VE OPTİMİZE EDİLMİŞ VERSİYON - v2.0)
# Bu Dockerfile, hem CPU hem de GPU imajlarını dinamik olarak oluşturabilir.

# --- Build Argümanları ---
# Hangi temel imajın kullanılacağını build sırasında belirleyeceğiz.
ARG TARGET_DEVICE=cpu
ARG PYTHON_VERSION=3.11

# --- Temel İmajları Tanımlama ---
# CPU için hafif bir temel imaj
FROM python:${PYTHON_VERSION}-slim-bullseye AS cpu-base
# GPU için, içinde zaten PyTorch, CUDA ve cuDNN'in kurulu olduğu resmi PyTorch imajı
FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime AS gpu-base

# --- Hedef İmajı Seçme ---
# TARGET_DEVICE argümanına göre ya cpu-base ya da gpu-base'i seçiyoruz.
FROM ${TARGET_DEVICE}-base AS base

# ==================================
#      Aşama 1: Builder
# ==================================
FROM base AS builder

WORKDIR /app

# Gerekli sistem bağımlılıklarını kur.
# PyTorch imajı Ubuntu tabanlı olduğu için apt-get kullanıyoruz, bu her iki durumda da çalışır.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Sanal ortamı oluştur (best practice)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# requirements.txt'yi kopyala ve bağımlılıkları kur
COPY requirements.txt .

# --- Dinamik Bağımlılık Kurulumu ---
# Eğer GPU imajı oluşturuyorsak, PyTorch zaten imajda var, bu yüzden requirements.txt'den atlayarak kur.
# Eğer CPU imajı oluşturuyorsak, hafif CPU versiyonunu kur.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    if [ "$TARGET_DEVICE" = "gpu" ]; then \
        echo "GPU imajı: PyTorch zaten mevcut, diğer bağımlılıklar kuruluyor."; \
        pip install --no-cache-dir -r <(grep -v 'torch' requirements.txt); \
    else \
        echo "CPU imajı: Hafif PyTorch ve diğer bağımlılıklar kuruluyor."; \
        pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu; \
    fi

# ==================================
#      Aşama 2: Final Image
# ==================================
FROM base AS final

WORKDIR /app

# Build argümanlarını ve ortam değişkenlerini ayarla
ARG GIT_COMMIT="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_VERSION="0.0.0"
ENV GIT_COMMIT=${GIT_COMMIT} \
    BUILD_DATE=${BUILD_DATE} \
    SERVICE_VERSION=${SERVICE_VERSION} \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME="/app/model-cache"

# Sadece runtime için gerekli sistem kütüphanelerini kur
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    curl \
    ca-certificates \
    libpq5 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Güvenlik için root olmayan bir kullanıcı oluştur
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --no-create-home --uid 1001 --ingroup appgroup appuser

# Builder aşamasından sanal ortamı ve uygulama kodunu kopyala
COPY --from=builder --chown=appuser:appgroup /opt/venv /opt/venv
COPY --chown=appuser:appgroup app ./app

# Model cache dizinini oluştur ve izinlerini ayarla
RUN mkdir -p /app/model-cache && \
    chown -R appuser:appgroup /app/model-cache

USER appuser

# Servisinizin portlarını expose edin
EXPOSE 17020 17021 17022

# Servisinizi başlatın
CMD ["python", "-m", "app.main"]