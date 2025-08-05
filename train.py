import seaborn as sns
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import f1_score
import xgboost as xgb
import pickle
from pathlib import Path
from typing import Tuple, Dict
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_data() -> pd.DataFrame:
    """Load the penguins dataset from Seaborn."""
    logger.info("Loading penguins dataset")
    df = sns.load_dataset("penguins")
    logger.info(f"Original dataset size: {len(df)} rows")
    df = df.dropna()
    logger.info(f"Dataset size after dropping NaN: {len(df)} rows")
    return df

def preprocess_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, Dict[str, list], LabelEncoder]:
    """Preprocess data: one-hot encode categorical features and label encode target."""
    logger.info("Preprocessing data")
    # Capitalize categorical values to match API expectations
    df["sex"] = df["sex"].str.capitalize()
    df["island"] = df["island"].str.capitalize()
    categorical_cols = ["sex", "island"]
    target_col = "species"
    df_encoded = pd.get_dummies(df, columns=categorical_cols, prefix=categorical_cols)
    encoder_info = {col: df[col].unique().tolist() for col in categorical_cols}
    le = LabelEncoder()
    y = le.fit_transform(df[target_col])
    X = df_encoded.drop(columns=[target_col])
    logger.info("Data preprocessing completed")
    return X, y, encoder_info, le

def train_and_evaluate(X: pd.DataFrame, y: pd.Series) -> Tuple[xgb.XGBClassifier, Dict[str, float]]:
    """Train and evaluate XGBoost model."""
    logger.info("Splitting data into train and test sets")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    logger.info("Training XGBoost model")
    model = xgb.XGBClassifier(
        max_depth=3,
        n_estimators=100,
        learning_rate=0.1,
        random_state=42,
        eval_metric="mlogloss"
    )
    model.fit(X_train, y_train)
    y_train_pred = model.predict(X_train)
    y_test_pred = model.predict(X_test)
    train_f1 = f1_score(y_train, y_train_pred, average="weighted")
    test_f1 = f1_score(y_test, y_test_pred, average="weighted")
    logger.info(f"Train F1-score: {train_f1:.4f}")
    logger.info(f"Test F1-score: {test_f1:.4f}")
    return model, {"train_f1": train_f1, "test_f1": test_f1}

def save_model_and_metadata(model: xgb.XGBClassifier, encoder_info: Dict[str, list], le: LabelEncoder) -> None:
    """Save the model and metadata to files."""
    logger.info("Saving model and metadata")
    Path("app/data").mkdir(parents=True, exist_ok=True)
    model.save_model("app/data/model.json")
    with open("app/data/encoder_info.pkl", "wb") as f:
        pickle.dump({"encoder_info": encoder_info, "label_encoder": le}, f)

def main() -> None:
    """Main function to execute the training pipeline."""
    df = load_data()
    X, y, encoder_info, le = preprocess_data(df)
    model, metrics = train_and_evaluate(X, y)
    save_model_and_metadata(model, encoder_info, le)

if __name__ == "__main__":
    main()