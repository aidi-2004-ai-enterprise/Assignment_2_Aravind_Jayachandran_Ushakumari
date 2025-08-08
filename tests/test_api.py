from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)

def test_predict_valid_input():
    """Test valid prediction with known penguin data."""
    sample = {
        "bill_length_mm": 39.1,
        "bill_depth_mm": 18.7,
        "flipper_length_mm": 181,
        "body_mass_g": 3750,
        "year": 2007,
        "sex": "Female",
        "island": "Biscoe"
    }
    response = client.post("/predict", json=sample)
    assert response.status_code == 200
    assert "species" in response.json()

def test_predict_missing_field():
    """Test request with a missing required field (e.g., bill_length_mm)."""
    sample = {
        # "bill_length_mm": 39.1,   # Omitted!
        "bill_depth_mm": 18.7,
        "flipper_length_mm": 181,
        "body_mass_g": 3750,
        "year": 2007,
        "sex": "Female",
        "island": "Biscoe"
    }
    response = client.post("/predict", json=sample)
    assert response.status_code == 422  # FastAPI validation

def test_predict_invalid_type():
    """Test request with wrong data type (string instead of float)."""
    sample = {
        "bill_length_mm": "not-a-number",  # Invalid!
        "bill_depth_mm": 18.7,
        "flipper_length_mm": 181,
        "body_mass_g": 3750,
        "year": 2007,
        "sex": "Female",
        "island": "Biscoe"
    }
    response = client.post("/predict", json=sample)
    assert response.status_code == 422  # FastAPI validation

def test_predict_out_of_range():
    """Test out-of-range value (negative body_mass_g)."""
    sample = {
        "bill_length_mm": 39.1,
        "bill_depth_mm": 18.7,
        "flipper_length_mm": 181,
        "body_mass_g": -50,  # Invalid
        "year": 2007,
        "sex": "Female",
        "island": "Biscoe"
    }
    response = client.post("/predict", json=sample)
    # If you have a custom validator, expect 400; otherwise FastAPI will accept the float, so you may want to add a Pydantic validator for this!
    assert response.status_code in [400, 422]

def test_predict_invalid_enum():
    """Test invalid enum value for sex or island."""
    sample = {
        "bill_length_mm": 39.1,
        "bill_depth_mm": 18.7,
        "flipper_length_mm": 181,
        "body_mass_g": 3750,
        "year": 2007,
        "sex": "Other",   # Invalid, should be 'Male' or 'Female'
        "island": "Biscoe"
    }
    response = client.post("/predict", json=sample)
    assert response.status_code == 422

def test_predict_empty_request():
    """Test empty request body."""
    response = client.post("/predict", json={})
    assert response.status_code == 422

def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Penguin Species Prediction API"}
