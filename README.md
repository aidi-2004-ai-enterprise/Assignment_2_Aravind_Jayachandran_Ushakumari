# Assignment_2_Aravind_Jayachandran_Ushakumari

# Penguin Species Prediction API 🐧

FastAPI + XGBoost microservice that predicts penguin species from measurements (Palmer Penguins dataset).

**Live URL:** https://penguin-api-130371288341.us-central1.run.app

---

## Features
- `POST /predict` → species prediction
- Strict validation with Pydantic (enums + numeric > 0)
- Loads model from **local files** or **Google Cloud Storage** (GCS)
- Unit tests with coverage
- Dockerized; deployable to Cloud Run
- Locust load tests

---

## Quickstart (local)

```powershell
# 1) Create & activate venv (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Install deps
uv pip install -r requirements.txt
# (or) pip install -r requirements.txt

# 3) (optional) train & save model locally to app/data/
python -c "import train; train.main()"

# 4) Run the API
uvicorn app.main:app --host 0.0.0.0 --port 8080


## API Documentation

Base URL (Cloud Run): `https://penguin-api-130371288341.us-central1.run.app`  
Local: `http://localhost:8080`

OpenAPI/Swagger:
- Swagger UI: `{BASE_URL}/docs`
- ReDoc: `{BASE_URL}/redoc`
- OpenAPI JSON: `{BASE_URL}/openapi.json`

### Authentication
None (public). Consider adding auth if you expose this beyond coursework.

---

### Endpoints

#### 1) Health
**GET** `/`  
Returns a simple message to confirm the service is running.

**Response 200**
```json
{ "message": "Penguin Species Prediction API" }


## Production Q&A

### What edge cases might break your model in production that aren't in your training data?
- **Out-of-distribution inputs:** new islands/sex labels; unrealistic measurements (e.g., bill_length=5000).
- **Unit mistakes:** cm vs mm, kg vs g.
- **Malformed payloads:** missing fields, empty JSON, strings where numbers are expected.
- **Casing/whitespace:** "female", " FEMALE ".
- **Concept drift:** future data distributions differ from Palmer Penguins.

**Mitigation:** strict schema validation (done), reject unknown enums (done), input sanitation, monitor input stats, retrain periodically.

---

### What happens if your model file becomes corrupted?
- Load fails → startup/readiness fails or 500s on predict.
- Cloud Run revision won’t become ready / gets restarted.

**Mitigation:** checksum/size verify on load, fail fast, `/healthz` that checks predictability, keep previous **versioned** artifact in GCS and **fallback**.

---

### What’s a realistic load for a penguin classification service?
- From Locust on Cloud Run: **~15–55 RPS per service** with 0% errors.
  - Normal (10 users, 5m): ~15 RPS, p95 ≈ **170 ms**
  - Stress (50 users, 2m): ~53 RPS, p95 ≈ **350 ms**
  - Spike (→100 in 1m): ~41 RPS during ramp, p95 ≈ **430 ms**
- Scale horizontally by raising `max-instances` and tuning concurrency.

---

### How would you optimize if response times are too slow?
- **Keep warm:** `--min-instances=1+`; (optionally CPU always allocated).
- **Tune concurrency:** try `20–40` to reduce queueing.
- **Right-size:** give at least 1 vCPU; raise memory if GC thrashes.
- **Avoid cold downloads:** cache model on local disk; hit GCS only on cold start (implemented).
- **Slim image/deps:** smaller image → faster cold starts.
- **Model tweaks:** fewer trees/depth, or distill if needed.

---

### What metrics matter most for ML inference APIs?
- **Latency percentiles:** p50/p90/p95/p99
- **Error rate:** 4xx/5xx/timeouts
- **Throughput & queueing:** RPS, in-flight, queue time
- **Cold starts:** count & duration
- **Resources:** CPU, memory, restarts, instance count
- **Data quality:** validation failures, prediction distribution

---

### Why is Docker layer caching important for build speed? (Did you leverage it?)
- Reuses unchanged layers (esp. dependency install), making rebuilds **much faster**.
- **Yes:** `requirements.txt` is copied and installed **before** app code, so the deps layer is cached until requirements change.

---

### What security risks exist with running containers as root?
- Compromise = root inside container → larger blast radius, easier breakout.
- Can write to system paths, bind privileged ports.

**Mitigation:** run as **non-root** (we use `appuser`), least-privilege service account, read-only mounts, minimal base image.

---

### How does cloud auto-scaling affect your load test results?
- During spikes, new instances need warm-up → **temporary p95/p99 spikes**.
- After scaling out, latency settles. Results depend on `min-instances`, concurrency, and image size.

---

### What would happen with 10x more traffic?
- Cloud Run scales out up to `--max-instances`; if capped, expect **queueing/timeouts**.
- Plan: increase max instances, tune concurrency, consider multi-region and request budgets/quotas; add caching if applicable.

---

### How would you monitor performance in production?
- **Cloud Monitoring dashboards:** latency percentiles, RPS, 5xx, cold starts, CPU/mem, instance count.
- **Cloud Logging:** structured logs for validation errors and failures.
- **Alerts:** high p95/p99, 5xx rate, OOM/restarts, cold-start bursts.
- **(Optional) Cloud Trace:** end-to-end latency breakdown.

---

### How would you implement blue-green deployment?
- Deploy new **revision/service** (“green”), smoke test, then **traffic split** (e.g., 5% → 25% → 100%).
- One-click/CLI **rollback** to previous revision if errors spike.

---

### What would you do if deployment fails in production?
- **Rollback** to last healthy revision; keep `min-instances` on the stable one to avoid downtime.
- Check logs/events (missing envs, wrong PORT, missing deps), fix, redeploy.

---

### What happens if your container uses too much memory?
- Kernel **OOMKills** the container → request fails, instance restarts; latency and 5xx spike.

**Mitigation:** raise memory limit, reduce concurrency, profile memory, trim deps/model size, set alerts on memory & restarts.
