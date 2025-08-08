from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from enum import Enum
import pandas as pd
import xgboost as xgb
import pickle
from pathlib import Path
from typing import Dict
import logging
import os
from google.cloud import storage
from dotenv import load_dotenv

# ── Load .env for local dev ─────────────────────────────────────────────────────
dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

# ── Logging (Cloud Run FS is read-only except /tmp) ─────────────────────────────
RUNNING_ON_CLOUDRUN = bool(os.getenv("K_SERVICE"))
DEFAULT_LOG_PATH = "/tmp/prediction.log" if RUNNING_ON_CLOUDRUN else str(
    Path(__file__).resolve().parent / "prediction.log"
)
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", DEFAULT_LOG_PATH)

handlers = [logging.StreamHandler()]
# If you prefer stdout-only on Cloud Run, comment out the next line.
handlers.append(logging.FileHandler(LOG_FILE_PATH))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=handlers,
)
logger = logging.getLogger(__name__)

# ── Enums / schema ───────────────────────────────────────────────────────────────
class Island(str, Enum):
    Torgersen = "Torgersen"
    Biscoe = "Biscoe"
    Dream = "Dream"

class Sex(str, Enum):
    Male = "Male"
    Female = "Female"

class PenguinFeatures(BaseModel):
    bill_length_mm: float = Field(..., gt=0)
    bill_depth_mm: float = Field(..., gt=0)
    flipper_length_mm: float = Field(..., gt=0)
    body_mass_g: float = Field(..., gt=0)
    year: int
    sex: Sex
    island: Island

app = FastAPI(title="Penguin Species Prediction API")

# ── Paths & globals ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
# Use /tmp on Cloud Run; local uses app/data. Can override with MODEL_DIR env var.
DATA_DIR = Path(
    os.getenv(
        "MODEL_DIR",
        "/tmp/model_cache" if RUNNING_ON_CLOUDRUN else str(BASE_DIR / "data"),
    )
)
MODEL_PATH = DATA_DIR / "model.json"
ENCODER_PATH = DATA_DIR / "encoder_info.pkl"

model = None
encoder_info = None
label_encoder = None

# ── GCS helpers ─────────────────────────────────────────────────────────────────
def download_from_gcs(bucket_name: str, blob_name: str, destination_path: str):
    """Download file from GCS to local path using ADC (works on Cloud Run)."""
    try:
        client = storage.Client()  # Uses ADC (service account on Cloud Run)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(destination_path)
        logger.info(f"Downloaded {blob_name} from bucket {bucket_name} to {destination_path}")
    except Exception as e:
        logger.error(f"Failed to download {blob_name} from {bucket_name}: {e}")
        raise

def _load_local():
    """Load model/encoders from local files."""
    global model, encoder_info, label_encoder
    logger.info("Loading local model and encoder—skipping GCS")
    temp_model = xgb.XGBClassifier()
    temp_model.load_model(str(MODEL_PATH))
    with open(ENCODER_PATH, "rb") as f:
        metadata = pickle.load(f)
        temp_encoder_info = metadata["encoder_info"]
        temp_label_encoder = metadata["label_encoder"]
    model = temp_model
    encoder_info = temp_encoder_info
    label_encoder = temp_label_encoder

def _load_from_gcs():
    """Download model/encoders from GCS and load them."""
    global model, encoder_info, label_encoder
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    model_blob = os.getenv("GCS_MODEL_BLOB_NAME")
    encoder_blob = os.getenv("GCS_ENCODER_BLOB_NAME")
    if not all([bucket_name, model_blob, encoder_blob]):
        raise RuntimeError(
            "Missing GCS env vars. Set GCS_BUCKET_NAME, GCS_MODEL_BLOB_NAME, GCS_ENCODER_BLOB_NAME."
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading model from GCS...")
    download_from_gcs(bucket_name, model_blob, str(MODEL_PATH))
    logger.info("Downloading encoder info from GCS...")
    download_from_gcs(bucket_name, encoder_blob, str(ENCODER_PATH))

    logger.info("Loading model from file...")
    temp_model = xgb.XGBClassifier()
    temp_model.load_model(str(MODEL_PATH))

    logger.info("Loading encoder info from file...")
    with open(ENCODER_PATH, "rb") as f:
        metadata = pickle.load(f)
        temp_encoder_info = metadata["encoder_info"]
        temp_label_encoder = metadata["label_encoder"]

    model = temp_model
    encoder_info = temp_encoder_info
    label_encoder = temp_label_encoder
    logger.info("Model and encoders loaded successfully.")

def _ensure_model_loaded():
    """Load model and encoder once (local first unless FORCE_GCS=1)."""
    global model, encoder_info, label_encoder
    if model is not None and label_encoder is not None and encoder_info is not None:
        return

    force_gcs = os.getenv("FORCE_GCS", "").lower() in ("1", "true", "yes")

    # Local-first if not forcing GCS and files exist
    if not force_gcs and MODEL_PATH.exists() and ENCODER_PATH.exists():
        _load_local()
        return

    logger.info("Loading model and encoder via GCS...")
    _load_from_gcs()

# Try load at import (won't crash app if it fails here).
try:
    _ensure_model_loaded()
except Exception as e:
    logger.warning(f"Model not loaded at import (okay if starting with Uvicorn): {e}")

@app.on_event("startup")
def load_model_and_metadata() -> None:
    _ensure_model_loaded()

# ── Inference helpers ───────────────────────────────────────────────────────────
def encode_features(data: PenguinFeatures) -> pd.DataFrame:
    """Encode categorical variables and prepare features for prediction."""
    if encoder_info is None:
        raise HTTPException(status_code=500, detail="Encoder not loaded")

    logger.info("Encoding input features")
    input_dict = data.model_dump()
    df = pd.DataFrame([input_dict])

    # Validate categorical values against training metadata
    for col in ["sex", "island"]:
        valid_values = encoder_info[col]
        val = input_dict[col]
        if val not in valid_values:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {col}: {val}. Must be one of {valid_values}"
            )

    df_encoded = pd.get_dummies(df, columns=["sex", "island"], prefix=["sex", "island"])
    df_encoded.rename(columns={"sex_male": "sex_Male", "sex_female": "sex_Female"}, inplace=True)

    expected_columns = [
        "bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g",
        "sex_Female", "sex_Male", "island_Biscoe", "island_Dream", "island_Torgersen",
    ]
    for col in expected_columns:
        if col not in df_encoded.columns:
            df_encoded[col] = 0

    return df_encoded[expected_columns]

# ── Routes ──────────────────────────────────────────────────────────────────────
@app.post("/predict")
async def predict(data: PenguinFeatures) -> Dict[str, str]:
    try:
        _ensure_model_loaded()
        X = encode_features(data)
        pred = model.predict(X)[0]
        species = label_encoder.inverse_transform([pred])[0]
        return {"species": species}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")

@app.get("/")
async def root() -> Dict[str, str]:
    return {"message": "Penguin Species Prediction API"}
