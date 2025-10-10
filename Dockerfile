# Dockerfile - Simplified for pip installation

# === Final Production Image ===
# Using a single-stage build for simplicity as Poetry is removed.
FROM python:3.11-slim-bullseye

# Set the working directory
WORKDIR /app

# Install system dependencies
# - git is required to install the git-based dependency (sentiric-contracts-py)
# - netcat & curl are useful for health checks and debugging
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    netcat-openbsd \
    curl \
    ca-certificates \
    libgomp1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1001 appuser

# Copy the requirements file first to leverage Docker layer caching
COPY --chown=appuser:appuser requirements.txt .

# Install Python dependencies using pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
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
# Port 12041 is the Harmony Port for this service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "12041"]