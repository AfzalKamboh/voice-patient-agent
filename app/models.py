"""
SQLAlchemy ORM models — the persistent data layer. for storing data in database.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Patient(Base): 
    __tablename__ = "patients"   # table with patient name.

    patient_id = Column(String(36), primary_key=True, default=gen_uuid)

    # Required fields
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    sex = Column(String(20), nullable=False)  # Male, Female, Other, Decline to Answer
    phone_number = Column(String(10), nullable=False, index=True)  # normalized 10 digits
    address_line_1 = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(2), nullable=False)
    zip_code = Column(String(10), nullable=False)

    # Optional fields
    email = Column(String(255), nullable=True)
    address_line_2 = Column(String(255), nullable=True)
    insurance_provider = Column(String(255), nullable=True)
    insurance_member_id = Column(String(64), nullable=True)
    preferred_language = Column(String(50), nullable=True, default="English")
    emergency_contact_name = Column(String(100), nullable=True)
    emergency_contact_phone = Column(String(10), nullable=True)

    # Auto-managed fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)  # soft-delete marker

    call_logs = relationship("CallLog", back_populates="patient")


class CallLog(Base):
    """Transcript/summary of each call, linked to the patient record."""
    __tablename__ = "call_logs"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    call_sid = Column(String(64), nullable=False, index=True)
    patient_id = Column(String(36), ForeignKey("patients.patient_id"), nullable=True)
    transcript = Column(Text, nullable=True)  # newline-delimited turn log
    final_payload = Column(Text, nullable=True)  # JSON snapshot of collected fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    patient = relationship("Patient", back_populates="call_logs")
