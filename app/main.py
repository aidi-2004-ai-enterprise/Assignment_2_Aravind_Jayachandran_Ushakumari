from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from enum import Enum
import pandas as pd
import xgboost as xgb
import pickle
from pathlib import Path
from typing import Dict
import logging

logging.basicConfig(
    level=logging.INFO,  # Can be changed to logging.DEBUG for more detail if needed
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app/prediction.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Island(str, Enum):
    Torgersen = "Torgersen"
    Biscoe = "Biscoe"
    Dream = "Dream"

class Sex(str, Enum):
    Male = "Male"
    Female = "Female"

class PenguinFeatures(BaseModel):
    bill_length_mm: float
    bill_depth_mm: float
    flipper_length_mm: float
    body_mass_g: float
    year: int
    sex: Sex
    island: Island

app = FastAPI(title="Penguin Species Prediction API")

MODEL_PATH = Path("app/data/model.json")
ENCODER_PATH = Path("app/data/encoder_info.pkl")
model = None
encoder_info = None
label_encoder = None

@app.on_event("startup")
def load_model_and_metadata() -> None:
    """Load the model and encoder metadata on startup."""
    global model, encoder_info, label_encoder
    try:
        logger.info("Loading model from %s", MODEL_PATH)
        model = xgb.XGBClassifier()
        model.load_model(MODEL_PATH)
        logger.info("Loading encoder info from %s", ENCODER_PATH)
        with open(ENCODER_PATH, "rb") as f:
            metadata = pickle.load(f)
            encoder_info = metadata["encoder_info"]
            label_encoder = metadata["label_encoder"]
        logger.info("Model and metadata loaded successfully")
    except Exception as e:
        logger.error("Failed to load model or metadata: %s", str(e))
        raise HTTPException(status_code=500, detail="Model loading failed")

def encode_features(data: PenguinFeatures) -> pd.DataFrame:
    """Encode input features consistently with training."""
    logger.info("Encoding input features")
    input_dict = data.dict()
    logger.debug("Input dict: %s", input_dict)
    df = pd.DataFrame([input_dict])
    for col in ["sex", "island"]:
        valid_values = encoder_info[col]
        input_value = input_dict[col]
        logger.debug("Valid values for %s: %s, Input value: %s", col, valid_values, input_value)
        if input_value not in valid_values:
            logger.debug("Invalid %s value: %s. Valid values: %s", col, input_value, valid_values)
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {col} value: {input_value}. Must be one of {valid_values}"
            )
    categorical_cols = ["sex", "island"]
    df_encoded = pd.get_dummies(df, columns=categorical_cols, prefix=categorical_cols)
    column_mapping = {"sex_male": "sex_Male", "sex_female": "sex_Female"}
    df_encoded = df_encoded.rename(columns=column_mapping)
    # Enforce exact column order as expected by the model
    expected_columns = [
        "bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g",
        "sex_Female", "sex_Male",
        "island_Biscoe", "island_Dream", "island_Torgersen"
    ]
    for col in expected_columns:
        if col not in df_encoded.columns:
            df_encoded[col] = 0
    df_encoded = df_encoded[expected_columns]
    logger.debug("Encoded DataFrame columns: %s", df_encoded.columns.tolist())
    return df_encoded

@app.post("/predict")
async def predict(data: PenguinFeatures) -> Dict[str, str]:
    """Predict penguin species based on input features."""
    try:
        logger.info("Received prediction request: %s", data.dict())
        X = encode_features(data)
        prediction = model.predict(X)[0]
        species = label_encoder.inverse_transform([prediction])[0]
        logger.info("Prediction successful: %s", species)
        return {"species": species}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error("Prediction failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Prediction failed")

@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint for health check."""
    return {"message": "Penguin Species Prediction API"}