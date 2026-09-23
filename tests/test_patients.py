"""
Basic integration tests for the REST API layer (bonus: Automated Tests).
Uses a throwaway SQLite file so it never touches the real patients.db.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "sqlite:///./test_patients.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine

client = TestClient(app)


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("test_patients.db"):
        os.remove("test_patients.db")


VALID_PATIENT = {
    "first_name": "Alex",
    "last_name": "Kim",
    "date_of_birth": "1995-06-15",
    "sex": "Other",
    "phone_number": "555-222-3333",
    "email": "alex.kim@example.com",
    "address_line_1": "789 Elm St",
    "city": "Seattle",
    "state": "wa",
    "zip_code": "98101",
}


def test_health_check():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ok"


def test_create_patient_success():
    resp = client.post("/patients", json=VALID_PATIENT)
    assert resp.status_code == 201
    body = resp.json()
    assert body["error"] is None
    assert body["data"]["first_name"] == "Alex"
    assert body["data"]["phone_number"] == "5552223333"  # normalized
    assert body["data"]["state"] == "WA"  # uppercased
    global created_id
    created_id = body["data"]["patient_id"]


def test_create_patient_invalid_phone():
    bad = dict(VALID_PATIENT, phone_number="123")
    resp = client.post("/patients", json=bad)
    assert resp.status_code == 422


def test_create_patient_invalid_state():
    bad = dict(VALID_PATIENT, state="ZZ")
    resp = client.post("/patients", json=bad)
    assert resp.status_code == 422


def test_create_patient_future_dob():
    bad = dict(VALID_PATIENT, date_of_birth="2999-01-01")
    resp = client.post("/patients", json=bad)
    assert resp.status_code == 422


def test_list_and_filter_patients():
    resp = client.get("/patients", params={"last_name": "Kim"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert any(p["last_name"] == "Kim" for p in data)


def test_get_patient_by_id():
    create_resp = client.post("/patients", json=dict(VALID_PATIENT, phone_number="5559990000"))
    patient_id = create_resp.json()["data"]["patient_id"]
    resp = client.get(f"/patients/{patient_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["patient_id"] == patient_id


def test_get_patient_not_found():
    resp = client.get("/patients/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_update_patient_partial():
    create_resp = client.post("/patients", json=dict(VALID_PATIENT, phone_number="5551110000"))
    patient_id = create_resp.json()["data"]["patient_id"]
    resp = client.put(f"/patients/{patient_id}", json={"city": "Tacoma"})
    assert resp.status_code == 200
    assert resp.json()["data"]["city"] == "Tacoma"
    assert resp.json()["data"]["first_name"] == "Alex"  # unchanged fields preserved


def test_soft_delete_patient():
    create_resp = client.post("/patients", json=dict(VALID_PATIENT, phone_number="5552220000"))
    patient_id = create_resp.json()["data"]["patient_id"]
    resp = client.delete(f"/patients/{patient_id}")
    assert resp.status_code == 200
    # soft-deleted patients should no longer be retrievable
    get_resp = client.get(f"/patients/{patient_id}")
    assert get_resp.status_code == 404
