# This file is used for validation of the patient data before saving to the database. 
# It contains functions to validate name, date of birth, sex, phone number, email, state, and zip code. 
# Each function returns a tuple indicating whether the validation passed, an optional error message, and any normalized value if applicable.  

import re
from datetime import date, datetime
from typing import Optional, Tuple

# List of USA states codes.
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

#gender list
VALID_SEX_VALUES = {"Male", "Female", "Other", "Decline to Answer"}


# regex for extract details
NAME_RE = re.compile(r"^[A-Za-z]+([\-' ][A-Za-z]+)*$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")


def normalize_phone(raw: str) -> Optional[str]:
    """Strip everything but digits; drop a leading US country code '1'."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else None


def validate_name(value: str) -> Tuple[bool, Optional[str]]:
    if not value or not (1 <= len(value) <= 50):
        return False, "must be 1-50 characters"
    if not NAME_RE.match(value):
        return False, "must contain only letters, hyphens, or apostrophes"
    return True, None


def validate_dob(value) -> Tuple[bool, Optional[str], Optional[date]]:
    """Accepts a date object or a string in MM/DD/YYYY or YYYY-MM-DD."""
    parsed: Optional[date] = None
    if isinstance(value, date):
        parsed = value
    elif isinstance(value, str):
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(value.strip(), fmt).date()
                break
            except ValueError:
                continue
    if parsed is None:
        return False, "must be a valid date (MM/DD/YYYY)", None
    if parsed > date.today():
        return False, "date of birth cannot be in the future", None
    if parsed.year < 1900:
        return False, "date of birth is implausibly far in the past", None
    return True, None, parsed


def validate_sex(value: str) -> Tuple[bool, Optional[str]]:
    if value not in VALID_SEX_VALUES:
        return False, f"must be one of {', '.join(sorted(VALID_SEX_VALUES))}"
    return True, None


def validate_phone(value: str) -> Tuple[bool, Optional[str], Optional[str]]:
    normalized = normalize_phone(value or "")
    if not normalized:
        return False, "must be a valid 10-digit U.S. phone number", None
    return True, None, normalized


def validate_email(value: Optional[str]) -> Tuple[bool, Optional[str]]:
    if value in (None, ""):
        return True, None  # optional
    if not EMAIL_RE.match(value):
        return False, "must be a valid email address"
    return True, None


def validate_required_string(value: Optional[str], field_label: str, max_len: int = 255) -> Tuple[bool, Optional[str]]:
    if not value or not (1 <= len(value.strip()) <= max_len):
        return False, f"{field_label} is required (1-{max_len} characters)"
    return True, None


def validate_state(value: str) -> Tuple[bool, Optional[str], Optional[str]]:
    if not value:
        return False, "must be a valid 2-letter U.S. state abbreviation", None
    v = value.strip().upper()
    if v not in US_STATES:
        return False, "must be a valid 2-letter U.S. state abbreviation", None
    return True, None, v


def validate_zip(value: str) -> Tuple[bool, Optional[str]]:
    if not value or not ZIP_RE.match(value.strip()):
        return False, "must be a 5-digit or ZIP+4 U.S. zip code"
    return True, None
