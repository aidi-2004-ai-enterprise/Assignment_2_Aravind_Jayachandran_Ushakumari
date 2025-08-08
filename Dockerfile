# syntax=docker/dockerfile:1.7
FROM python:3.11-slim-bookworm

# Safe defaults
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    MODEL_DIR=/tmp/model_cache

WORKDIR /app

# xgboost needs libgomp1 at runtime
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -u 10001 -ms /bin/bash appuser
USER appuser

# Python deps
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# App code
COPY --chown=appuser:appuser app/ ./app

EXPOSE 8080

# Use module form so we don’t depend on a shell-resolved uvicorn binary
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
