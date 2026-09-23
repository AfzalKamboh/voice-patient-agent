"""
Using Pydantic schemas for both input request and output response for the REST API.

Every response uses the consistent envelope required by the spec:
    { "data": {...}, "error": null }
"""
from datetime import date, datetime
from typing import Optional, Any, Generic, TypeVar
from pydantic import BaseModel, field_validator

from app.validators import (
    validate_name, validate_dob, validate_sex, validate_phone,
    validate_state, validate_zip, validate_email,
)


class PatientBase(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone_number: str
    email: Optional[str] = None
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    state: str
    zip_code: str
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = "English"
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def _check_name(cls, v):
        ok, err = validate_name(v)
        if not ok:
            raise ValueError(f"invalid name: {err}")
        return v

    @field_validator("sex")
    @classmethod
    def _check_sex(cls, v):
        ok, err = validate_sex(v)
        if not ok:
            raise ValueError(err)
        return v

    @field_validator("phone_number")
    @classmethod
    def _check_phone(cls, v):
        ok, err, normalized = validate_phone(v)
        if not ok:
            raise ValueError(err)
        return normalized

    @field_validator("emergency_contact_phone")
    @classmethod
    def _check_emerg_phone(cls, v):
        if v in (None, ""):
            return v
        ok, err, normalized = validate_phone(v)
        if not ok:
            raise ValueError(err)
        return normalized

    @field_validator("email")
    @classmethod
    def _check_email(cls, v):
        ok, err = validate_email(v)
        if not ok:
            raise ValueError(err)
        return v

    @field_validator("state")
    @classmethod
    def _check_state(cls, v):
        ok, err, normalized = validate_state(v)
        if not ok:
            raise ValueError(err)
        return normalized

    @field_validator("zip_code")
    @classmethod
    def _check_zip(cls, v):
        ok, err = validate_zip(v)
        if not ok:
            raise ValueError(err)
        return v


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    """All fields optional to support partial updates (PUT /patients/:id)."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None


class PatientOut(BaseModel):
    patient_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone_number: str
    email: Optional[str] = None
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    state: str
    zip_code: str
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    data: Optional[T] = None
    error: Optional[str] = None
