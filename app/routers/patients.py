from datetime import date as date_type
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud
from app.schemas import PatientCreate, PatientUpdate, PatientOut, Envelope
from app.logging_config import logger

router = APIRouter(prefix="/patients", tags=["patients"])


def _envelope_error(status_code: int, message: str):
    raise HTTPException(status_code=status_code, detail=message)



@router.get("", response_model=Envelope[list])
def list_patients(
    last_name: Optional[str] = Query(None),
    date_of_birth: Optional[date_type] = Query(None),
    phone_number: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    patients = crud.list_patients(db, last_name, date_of_birth, phone_number)
    return {"data": [PatientOut.model_validate(p).model_dump(mode="json") for p in patients], "error": None}


@router.get("/{patient_id}", response_model=Envelope[dict])
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = crud.get_patient(db, patient_id)
    if not patient:
        _envelope_error(404, "patient not found")
    return {"data": PatientOut.model_validate(patient).model_dump(mode="json"), "error": None}


@router.post("", response_model=Envelope[dict], status_code=201)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)):
    try:
        patient = crud.create_patient(db, payload.model_dump())
    except Exception as e:  # e.g. constraint violations
        logger.error(f"Failed to create patient via API: {e}")
        _envelope_error(400, f"could not create patient: {e}")
    logger.info(f"Created patient {patient.patient_id} via REST API")
    return {"data": PatientOut.model_validate(patient).model_dump(mode="json"), "error": None}


@router.put("/{patient_id}", response_model=Envelope[dict])
def update_patient(patient_id: str, payload: PatientUpdate, db: Session = Depends(get_db)):
    patient = crud.get_patient(db, patient_id)
    if not patient:
        _envelope_error(404, "patient not found")

    updates = payload.model_dump(exclude_unset=True)

    # Re-validating any provided fields using the same rules as creation, andby merging onto the existing record and running it through PatientCreate.
    try:
        merged = PatientOut.model_validate(patient).model_dump()
        merged.update(updates)
        # Strip fields PatientCreate doesn't accept
        for k in ("patient_id", "created_at", "updated_at"):
            merged.pop(k, None)
        validated = PatientCreate(**merged)
    except ValidationError as e:
        _envelope_error(422, str(e))

    patient = crud.update_patient(db, patient, validated.model_dump())
    logger.info(f"Updated patient {patient.patient_id} via REST API")
    return {"data": PatientOut.model_validate(patient).model_dump(mode="json"), "error": None}


@router.delete("/{patient_id}", response_model=Envelope[dict])
def delete_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = crud.get_patient(db, patient_id)
    if not patient:
        _envelope_error(404, "patient not found")
    crud.soft_delete_patient(db, patient)
    logger.info(f"Soft-deleted patient {patient_id} via REST API")
    return {"data": {"patient_id": patient_id, "deleted": True}, "error": None}
