"""
this file is like Data-access layer. for API routing layer and from the
voice-agent logic 
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import Patient


def create_patient(db: Session, data: dict) -> Patient:
    patient = Patient(**data)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def get_patient(db: Session, patient_id: str) -> Optional[Patient]:
    return (
        db.query(Patient)
        .filter(Patient.patient_id == patient_id, Patient.deleted_at.is_(None))
        .first()
    )


def get_patient_by_phone(db: Session, phone_number: str) -> Optional[Patient]:
    return (
        db.query(Patient)
        .filter(Patient.phone_number == phone_number, Patient.deleted_at.is_(None))
        .first()
    )


def list_patients(
    db: Session,
    last_name: Optional[str] = None,
    date_of_birth=None,
    phone_number: Optional[str] = None,
) -> List[Patient]:
    filters = [Patient.deleted_at.is_(None)]
    if last_name:
        filters.append(Patient.last_name.ilike(last_name))
    if date_of_birth:
        filters.append(Patient.date_of_birth == date_of_birth)
    if phone_number:
        filters.append(Patient.phone_number == phone_number)
    return db.query(Patient).filter(and_(*filters)).all()


def update_patient(db: Session, patient: Patient, updates: dict) -> Patient:
    for key, value in updates.items():
        if value is not None:
            setattr(patient, key, value)
    patient.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(patient)
    return patient


def soft_delete_patient(db: Session, patient: Patient) -> Patient:
    patient.deleted_at = datetime.utcnow()
    db.commit()
    db.refresh(patient)
    return patient
