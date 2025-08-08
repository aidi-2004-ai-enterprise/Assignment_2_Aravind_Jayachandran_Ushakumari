# Deployment Documentation for Penguin API

## Overview
This document outlines the steps taken to containerize and deploy the Penguin API application using Docker. The goal was to create a portable and production-ready Docker container optimized for performance and security.

---

## Dockerfile Summary
- **Base Image:** `python:3.10-slim` (minimal size, good for production)
- **Installed Dependencies:** From `requirements.txt` including FastAPI, XGBoost, scikit-learn, and other libraries.
- **Application Code:** Copied the `app` directory and tests into the container.
- **Port Exposed:** 8080 (to align with Cloud Run and container runtime)
- **Run Command:** `uvicorn app.main:app --host 0.0.0.0 --port 8080`

---

## .dockerignore File
To keep the image size small and avoid copying unnecessary files, the following are excluded:


---

## Build and Run Commands

### Build the Docker Image
```bash
docker build -t penguin-api .

docker run -p 8080:8080 \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/penguin-xgboost-api-b8dd6181f02c.json \
  -e GCS_BUCKET_NAME=penguin-model-ju \
  -e GCS_MODEL_BLOB_NAME=model.json \
  -e GCS_ENCODER_BLOB_NAME=encoder_info.pkl \
  -v "D:\Sem 2\2004 Ai in enterprise systems Bipin\Assignment_2\Assignment_2_Aravind_Jayachandran_Ushakumari\penguin-xgboost-api-b8dd6181f02c.json:/app/penguin-xgboost-api-b8dd6181f02c.json:ro" \
  penguin-api

docker inspect penguin-api

Total Image Size: Approximately 833 MB

Number of Layers: 10