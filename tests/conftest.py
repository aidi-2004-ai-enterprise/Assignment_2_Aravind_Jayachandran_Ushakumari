# tests/conftest.py

import os

# 1) Set ALL required env-vars up front so _ensure_model_loaded never errors
os.environ.update({
    "GOOGLE_APPLICATION_CREDENTIALS": "dummy",
    "GCS_BUCKET_NAME":             "dummy-bucket",
    "GCS_MODEL_BLOB_NAME":         "model.json",
    "GCS_ENCODER_BLOB_NAME":       "encoder_info.pkl",
})

import pytest
from fastapi.testclient import TestClient

# 2) Now import your app module and stub GCS
import app.main as main_mod
from app.main import app

@pytest.fixture(autouse=True)
def skip_gcs_and_load(monkeypatch):
    # Prevent any real GCS calls
    monkeypatch.setattr(main_mod, "download_from_gcs", lambda *a, **k: None)
    # Force loading the model/encoder from local files
    main_mod._ensure_model_loaded()
    yield

@pytest.fixture
def client():
    return TestClient(app)
