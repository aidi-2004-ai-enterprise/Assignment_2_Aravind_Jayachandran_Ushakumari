# locustfile.py
import random
from locust import FastHttpUser, task, between, events

ISLANDS = ["Torgersen", "Biscoe", "Dream"]
SEXES = ["Male", "Female"]

def make_payload():
    # Very rough realistic ranges pulled from penguins dataset
    return {
        "bill_length_mm": round(random.uniform(32.0, 60.0), 1),
        "bill_depth_mm":  round(random.uniform(13.0, 22.0), 1),
        "flipper_length_mm": int(random.uniform(170, 230)),
        "body_mass_g": int(random.uniform(2700, 6300)),
        "year": random.choice([2007, 2008, 2009]),
        "sex": random.choice(SEXES),
        "island": random.choice(ISLANDS),
    }

class PenguinUser(FastHttpUser):
    # small think time so we can push RPS; adjust if you want slower users
    wait_time = between(0.2, 0.8)

    def on_start(self):
        # Warm up the instance (also triggers model download on cold starts)
        self.client.get("/", name="GET /")

    @task(5)
    def predict(self):
        payload = make_payload()
        with self.client.post("/predict", json=payload, name="POST /predict", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}: {resp.text}")
            elif "species" not in resp.json():
                resp.failure("No 'species' in response")
