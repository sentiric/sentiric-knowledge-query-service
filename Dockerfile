# Dockerfile - Final version with build tools

FROM python:3.11-slim-bullseye

WORKDIR /app

# Install system dependencies
# - git: for installing git-based dependencies
# - build-essential: provides C/C++ compilers (needed by sentence-transformers/torch)
# - netcat & curl: for health checks and debugging
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    netcat-openbsd \
    curl \
    ca-certificates \
    libgomp1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd --create-home --shell /bin/bash --uid 1001 appuser

# Copy requirements file
COPY --chown=appuser:appuser requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appuser app ./app

# Set build-time arguments as environment variables
ARG GIT_COMMIT
ARG BUILD_DATE
ARG SERVICE_VERSION
ENV GIT_COMMIT=${GIT_COMMIT}
ENV BUILD_DATE=${BUILD_DATE}
ENV SERVICE_VERSION=${SERVICE_VERSION}

# Switch to the non-root user
USER appuser

# The command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "12401"]