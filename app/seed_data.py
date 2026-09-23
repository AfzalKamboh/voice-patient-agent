"""
File for seeding data for new entries with dummy data.
"""
from datetime import date

from app.database import SessionLocal
from app.models import Patient
from app.logging_config import logger

SEED_PATIENTS = [
    dict(
        first_name="Jane", last_name="Doe", date_of_birth=date(1990, 4, 12),
        sex="Female", phone_number="5551234567", email="jane.doe@example.com",
        address_line_1="123 Main St", city="Austin", state="TX", zip_code="78701",
        preferred_language="English",
    ),
    dict(
        first_name="Carlos", last_name="Mendez", date_of_birth=date(1985, 11, 2),
        sex="Male", phone_number="5559876543", email="carlos.mendez@example.com",
        address_line_1="456 Oak Ave", address_line_2="Apt 2B", city="Phoenix",
        state="AZ", zip_code="85001", insurance_provider="Blue Cross",
        insurance_member_id="BC-88213", preferred_language="Spanish",
    ),
]


def seed_if_empty():
    db = SessionLocal()
    try:
        if db.query(Patient).count() == 0:
            for data in SEED_PATIENTS:
                db.add(Patient(**data))
            db.commit()
            logger.info(f"Seeded {len(SEED_PATIENTS)} demo patient records")
    finally:
        db.close()
