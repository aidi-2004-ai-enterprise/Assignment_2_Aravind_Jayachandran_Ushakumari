# DEPLOYMENT.md

This document explains how the container is built and deployed to Google Cloud Run, including the exact commands used, issues hit, and how they were fixed.

**Final Cloud Run URL:**  
https://penguin-api-130371288341.us-central1.run.app

---

## 1) Prerequisites

- Docker Desktop installed and running
- Google Cloud SDK (`gcloud`) installed and authenticated
- A Google Cloud project (we used: `penguin-xgboost-api`)
- Artifact Registry repository (we used: `us-central1 / penguin-api-repo`)
- Service Account for runtime with least privilege (we used: `penguin-api-sa@penguin-xgboost-api.iam.gserviceaccount.com`)
- GCS bucket containing the model artifacts:
  - Bucket: `penguin-model-bucket-2025`
  - Objects: `models/model.json` and `models/encoder_info.pkl`

> For local development against GCS, put your SA key (JSON) in the repo root as `penguin-sa.json` and **never commit it**.

---

## 2) Project Structure (relevant bits)

app/
main.py
data/ # (optional local model cache)
model.json
encoder_info.pkl
Dockerfile
requirements.txt
tests/
train.py


---

## 3) Dockerfile (production-ready)

Key choices:
- `python:3.11-slim-bookworm`
- Install only runtime OS deps (`libgomp1` for XGBoost)
- Non-root user (`appuser`)
- Only copy `app/` (tests are not needed in the runtime image)
- Expose `8080` and start FastAPI with `uvicorn`

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# XGBoost runtime dependency
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# Non-root
RUN useradd -u 10001 -ms /bin/bash appuser
USER appuser

# Install Python deps
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# Copy app only
COPY --chown=appuser:appuser app/ ./app

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]


4) Build & Test Locally
Build (Linux/amd64 for Cloud Run)
PowerShell (Windows):

powershell

docker build --pull --platform linux/amd64 -t penguin-api:latest .
Run (local, no GCS):

powershell

docker run -p 8080:8080 penguin-api:latest
Open http://localhost:8080/ to see:

json

{"message":"Penguin Species Prediction API"}
Run (local with GCS model):

powershell

docker run -d --name penguin-test -p 8080:8080 `
  -v "$PWD/penguin-sa.json:/gcp/sa-key.json:ro" `
  -e GOOGLE_APPLICATION_CREDENTIALS=/gcp/sa-key.json `
  -e GCS_BUCKET_NAME=penguin-model-bucket-2025 `
  -e GCS_MODEL_BLOB_NAME=models/model.json `
  -e GCS_ENCODER_BLOB_NAME=models/encoder_info.pkl `
  penguin-api:latest
Verify logs:

powershell

docker logs penguin-test --tail 200
Test request (PowerShell):

powershell

$base = "http://localhost:8080"
$body = @{
  bill_length_mm = 39.1
  bill_depth_mm = 18.7
  flipper_length_mm = 181
  body_mass_g = 3750
  year = 2007
  sex = "Female"
  island = "Biscoe"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/predict" -ContentType "application/json" -Body $body
5) Push Image to Artifact Registry
Tag:

powershell

docker tag penguin-api:latest `
  us-central1-docker.pkg.dev/penguin-xgboost-api/penguin-api-repo/penguin-api:latest
Auth Docker to AR (region-specific, one-time):

powershell

gcloud auth configure-docker us-central1-docker.pkg.dev
Push:

powershell

docker push `
  us-central1-docker.pkg.dev/penguin-xgboost-api/penguin-api-repo/penguin-api:latest
Give Cloud Run permission to pull from AR (one-time):

powershell

$PROJECT="penguin-xgboost-api"
$PN = (gcloud projects describe $PROJECT --format="value(projectNumber)")
gcloud artifacts repositories add-iam-policy-binding penguin-api-repo `
  --location=us-central1 `
  --member="serviceAccount:service-$PN@serverless-robot-prod.iam.gserviceaccount.com" `
  --role=roles/artifactregistry.reader
6) Deploy to Cloud Run
Important: Quote your env var list so they don’t get concatenated.

powershell

gcloud run deploy penguin-api `
  --image us-central1-docker.pkg.dev/penguin-xgboost-api/penguin-api-repo/penguin-api:latest `
  --region us-central1 `
  --allow-unauthenticated `
  --port 8080 `
  --service-account penguin-api-sa@penguin-xgboost-api.iam.gserviceaccount.com `
  --set-env-vars "GCS_BUCKET_NAME=penguin-model-bucket-2025,GCS_MODEL_BLOB_NAME=models/model.json,GCS_ENCODER_BLOB_NAME=models/encoder_info.pkl" `
  --cpu 1 --memory 4Gi --min-instances 1 --max-instances 50
Get service URL:

powershell

gcloud run services describe penguin-api `
  --region us-central1 `
  --format="value(status.url)"
Tail logs (optional):

powershell

gcloud beta run services logs tail penguin-api --region us-central1
Query the Cloud Run URL (PowerShell):

powershell

Invoke-RestMethod -Uri "https://penguin-api-130371288341.us-central1.run.app/" -Method Get
7) Issues Encountered & Solutions
Issue	Symptom	Fix
Missing deps (uvicorn, dotenv, httpx for tests)	ImportError during run/tests	Add to requirements.txt and rebuild
Tests failing due to GCS env	500 in tests (env not set)	Implement local-first model load in main.py (load from app/data if present)
Docker build failed copying tests	COPY tests/ not found	Don’t copy tests into runtime image (only copy app/)
Version mismatch (contourpy with py3.10)	No matching distribution during build	Use python:3.11-slim-bookworm base
Cloud Run failed to start	“failed to resolve binary path: uvicorn” or not listening on PORT	Ensure uvicorn in requirements and CMD ["uvicorn", ..., "--port", "8080"]
Env vars concatenated	In revision, GCS_BUCKET_NAME held entire string	Quote the list: --set-env-vars "A=a,B=b,C=c"
GCS perms denied	storage.objects.create / storage.objects.get denied	Grant bucket IAM: runtime SA → roles/storage.objectViewer; for upload from CLI, use your user or add objectCreator to the SA
Cloud Resource Manager API disabled	gcloud said SERVICE_DISABLED	Enable API in the console and retry
Vulnerability scan findings	AR flagged some medium/low	Rebuild with --pull, use slim base; pin deps; (non-root user)

8) Image Size & Layers
Inspect image:

powershell

docker image inspect penguin-api:latest --format='{{.Id}} {{.Size}}'
docker history penguin-api:latest
Notes

Base: python:3.11-slim-bookworm

Small OS footprint + only libgomp1

Python deps in a single cached layer

App layer minimal

9) Verifying After Deploy
Health:

powershell

Invoke-RestMethod -Uri "https://penguin-api-130371288341.us-central1.run.app/" -Method Get
Predict:

powershell

$base = "https://penguin-api-130371288341.us-central1.run.app"
$body = @{
  bill_length_mm = 39.1
  bill_depth_mm = 18.7
  flipper_length_mm = 181
  body_mass_g = 3750
  year = 2007
  sex = "Female"
  island = "Biscoe"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/predict" -ContentType "application/json" -Body $body
10) Performance & Scaling Notes
Keep --min-instances=1 to reduce cold starts.

Tune --max-instances and concurrency (Cloud Run default 80; try 20–40 for this API).

Observed p95 on Cloud Run from Locust: ~170–430 ms depending on load; 0% failures.

Monitor CPU/mem; if memory is high, reduce concurrency or increase memory.

11) Rollback / Troubleshooting
Rollback to previous revision (Console or CLI):

powershell

gcloud run services update-traffic penguin-api `
  --region us-central1 `
  --to-latest=false `
  --splits <PREVIOUS_REVISION>=1
Read error logs quickly:

powershell
gcloud logging read `
  'resource.type="cloud_run_revision"
   AND resource.labels.service_name="penguin-api"
   AND resource.labels.location="us-central1"
   AND severity>=ERROR' `
  --project penguin-xgboost-api `
  --limit 100 `
  --format='value(textPayload)'
Common checks:

Is the container listening on PORT=8080?

Is uvicorn installed and on PATH?

Are env vars set correctly (quoted)?

Does the runtime SA have roles/storage.objectViewer on the bucket?

12) Security Considerations
Non-root container user (appuser)

No secrets baked into the image; SA key only used locally via volume mount

Narrow IAM on runtime SA (viewer for model objects only)

.dockerignore and .gitignore exclude .env and key files

13) Final URL
Service URL: https://penguin-api-130371288341.us-central1.run.app
