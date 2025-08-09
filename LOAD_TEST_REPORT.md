Load Test – Penguin API (Cloud Run)
URL: https://penguin-api-130371288341.us-central1.run.app
Duration: 5 min
Users: 10 (normal scenario)
Tool: Locust (locustfile.py)

Results (key endpoint)
/predict

Requests: 4,621

Failures: 0 (0%)

RPS: ~15.4

Latency: avg 101 ms, p50 71 ms, p95 170 ms, p99 470 ms

Min/Max: 39 ms / 3,494 ms

Misc (GET / warm-up/health)

10 requests, very slow (13–17 s). Not user traffic—these are cold-start hits.

What this means
Under ~15 RPS, predictions are stable and fast (p95 ≈ 170 ms, 0% errors).

A few slow first requests are from cold starts (new instance spin-up).

Bottlenecks
Cold starts (first requests after scale to zero or scale up).

Possible CPU contention at higher concurrency (XGBoost is CPU-bound).


Baseline (Cloud) — 1 user, 60s
Target: https://penguin-api-130371288341.us-central1.run.app
Script: locustfile.py
Duration: 1 min

/predict
Requests: 90

Failures: 0 (0%)

Throughput (RPS): ~1.5

Latency: avg 164 ms, p50 160 ms, p95 280 ms, p99 380 ms

Min/Max: 61 ms / 383 ms

GET /
Requests: 1

Latency: ~589 ms (likely first-hit warmup)

Takeaways
Under light load the service is stable and fast (p95 < 300 ms, 0% errors).

The single / (root) request at ~590 ms is consistent with cold start/warmup overhead.

Bottleneck (observed)
Cold start adds ~0.6s on the first request when the service has scaled to zero.


Stress (Cloud) — 50 users, 2 minutes
Target: https://penguin-api-130371288341.us-central1.run.app
Script: locustfile.py
Duration: 2 min

/predict
Requests: 6,366

Failures: 0 (0%)

Throughput (RPS): ~53.0

Latency: avg 230 ms, p50 240 ms, p95 350 ms, p99 440 ms

Min/Max: 41 ms / 1000 ms

GET /
Requests: 50

Latency: avg 464 ms (warmup/health checks)

Min/Max: 337 ms / 835 ms

Takeaways
Service sustained ~53 req/s with zero errors.

Tail latency appears around ~1s max under burst, but p99 stays < 450 ms, which is solid.

Likely bottlenecks
Per-instance concurrency pressure during bursts → occasional 1s outliers.

Root endpoint is slower than API calls (likely startup/health pings), but not user-facing.


pike Test (1 → 100 users over 1 minute)
When: 2025-08-08 21:12–21:13
Target: https://penguin-api-130371288341.us-central1.run.app
Script: locustfile.py

Summary (POST /predict)
Requests: 2,389

Failures: 0 (0.00%)

Throughput: ~39.8 RPS (Agg. ~40.8 RPS)

Latency (ms): avg 199, p50 180, p90 370, p95 430, p99 560, max 1000

Warmup/Health (GET /)
Requests: 60

Latency (ms): avg 525, p50 540, max 780 (likely health checks/warmup)

Observations
No errors under a sharp spike to 100 users; service stayed healthy.

p95 ~430 ms and p99 ~560 ms during the ramp—brief tail latency while new instances spin up.

Occasional max ~1s on /predict lines up with autoscaling/warmup; steady-state typical latency is far lower.

GET “/” averages ~525 ms (non-critical) and looks like health or readiness checks rather than app hot path.

Bottlenecks / Causes
Instance warmup: first requests on new Cloud Run instances pay model load/init costs.

CPU-bound inference: XGBoost on CPU means burst spikes contend for CPU until new instances come online.

Container concurrency: default concurrency may let many requests share one CPU during spikes, increasing p95/p99.