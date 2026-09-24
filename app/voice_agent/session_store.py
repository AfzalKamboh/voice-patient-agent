"""
file for In-memory store of active call sessions.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any


REQUIRED_FIELDS = [
    "first_name", "last_name", "date_of_birth", "sex", "phone_number",
    "address_line_1", "city", "state", "zip_code",
]


OPTIONAL_FIELDS = [
    "address_line_2", "email", "insurance_provider", "insurance_member_id",
    "preferred_language", "emergency_contact_name", "emergency_contact_phone",
]

FIELD_LABELS = {
    "first_name": "first name",
    "last_name": "last name",
    "date_of_birth": "date of birth",
    "sex": "sex (Male, Female, Other, or Decline to Answer)",
    "phone_number": "10-digit phone number",
    "address_line_1": "street address",
    "address_line_2": "apartment, suite, or unit number",
    "city": "city",
    "state": "state",
    "zip_code": "zip code",
    "email": "email address",
    "insurance_provider": "insurance provider",
    "insurance_member_id": "insurance member ID",
    "preferred_language": "preferred language",
    "emergency_contact_name": "emergency contact's name",
    "emergency_contact_phone": "emergency contact's phone number",
}


@dataclass
class CallSession:
    call_sid: str
    caller_number: Optional[str] = None
    stage: str = "greeting"  
    collected: Dict[str, Any] = field(default_factory=dict)
    existing_patient_id: Optional[str] = None  # set if updating a returning caller
    is_update: bool = False
    field_queue: List[str] = field(default_factory=lambda: list(REQUIRED_FIELDS))
    optional_queue: List[str] = field(default_factory=list)
    last_error_field: Optional[str] = None
    no_input_count: int = 0
    correction_target: Optional[str] = None  # set when re-collecting a single field post-confirmation
    transcript: List[str] = field(default_factory=list)
    history: List[Dict[str, str]] = field(default_factory=list)  # LLM chat history (trimmed)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def log_turn(self, speaker: str, text: str):
        self.transcript.append(f"[{datetime.utcnow().isoformat()}] {speaker}: {text}")

    def collected_json(self) -> str:
        return json.dumps(self.collected, default=str)


# call_sid -> CallSession
_SESSIONS: Dict[str, CallSession] = {}


def get_or_create_session(call_sid: str, caller_number: Optional[str] = None) -> CallSession:
    if call_sid not in _SESSIONS:
        _SESSIONS[call_sid] = CallSession(call_sid=call_sid, caller_number=caller_number)
    return _SESSIONS[call_sid]


def get_session(call_sid: str) -> Optional[CallSession]:
    return _SESSIONS.get(call_sid)


def end_session(call_sid: str):
    _SESSIONS.pop(call_sid, None)
