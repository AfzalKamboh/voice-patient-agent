"""
The conversation engine: a deterministic state machine that leans on the LLM
for natural-language understanding/generation at each step, but never trusts
it blindly for validation or for the final confirmation read-back.

States:
  greeting          -> initial hello, or duplicate-caller check
  duplicate_check    -> caller confirms whether to update existing record
  collecting         -> walking REQUIRED_FIELDS one at a time (LLM can fill
                         several at once / correct earlier ones)
  offer_optional     -> ask if caller wants to provide optional info
  collecting_optional-> walking OPTIONAL_FIELDS
  confirming          -> deterministic read-back + yes/no/correction
  correcting          -> re-collecting one field named during confirmation
  saving              -> write to DB via crud layer
  done                -> call ends
"""
from datetime import date
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app import crud
from app.voice_agent.session_store import (
    CallSession, REQUIRED_FIELDS, OPTIONAL_FIELDS, FIELD_LABELS,
)
from app.voice_agent import prompts
from app.voice_agent.llm_client import chat_json, LLMError
from app.logging_config import logger
from app.validators import (
    validate_name, validate_dob, validate_sex, validate_phone, validate_email,
    validate_required_string, validate_state, validate_zip,
)

MAX_NO_INPUT_RETRIES = 3

GREETING = (
    "Hi, thanks for calling! I'm Ava, and I can help you register as a new "
    "patient today. It'll just take a couple of minutes. Could I start "
    "with your first name?"
)

NO_INPUT_REPROMPT = "Sorry, I didn't catch that — could you say that again?"
NO_INPUT_GOODBYE = (
    "I'm having trouble hearing you, so I'll let you go for now. Please "
    "call back when you're in a quieter spot. Goodbye!"
)
GOODBYE_TECH_ISSUE = (
    "I'm really sorry — we hit a technical issue saving your information. "
    "Please call back in a few minutes and we'll try again. Goodbye."
)


def _validate_field(field: str, raw_value):
    """
    Runs the right validator for a given field.
    Returns (ok, error_message, normalized_value).
    """
    if field in ("first_name", "last_name"):
        ok, err = validate_name(raw_value)
        return ok, err, raw_value.strip().title() if ok else None
    if field == "date_of_birth":
        ok, err, parsed = validate_dob(raw_value)
        return ok, err, parsed
    if field == "sex":
        ok, err = validate_sex(raw_value)
        return ok, err, raw_value if ok else None
    if field in ("phone_number", "emergency_contact_phone"):
        ok, err, normalized = validate_phone(raw_value)
        return ok, err, normalized
    if field == "email":
        ok, err = validate_email(raw_value)
        return ok, err, raw_value if ok else None
    if field == "state":
        ok, err, normalized = validate_state(raw_value)
        return ok, err, normalized
    if field == "zip_code":
        ok, err = validate_zip(raw_value)
        return ok, err, raw_value if ok else None
    if field in ("address_line_1", "city"):
        ok, err = validate_required_string(raw_value, FIELD_LABELS[field])
        return ok, err, raw_value if ok else None
    # free-text optional fields: address_line_2, insurance_*, preferred_language,
    # emergency_contact_name — accept as-is (non-empty)
    if raw_value and str(raw_value).strip():
        return True, None, str(raw_value).strip()
    return False, "was empty", None


def _current_target_field(session: CallSession) -> Optional[str]:
    if session.correction_target:
        return session.correction_target
    if session.stage == "collecting" and session.field_queue:
        return session.field_queue[0]
    if session.stage == "collecting_optional" and session.optional_queue:
        return session.optional_queue[0]
    return None


def _confirmation_summary(session: CallSession) -> str:
    parts = []
    order = REQUIRED_FIELDS + [f for f in OPTIONAL_FIELDS if f in session.collected]
    for f in order:
        if f in session.collected:
            val = session.collected[f]
            if isinstance(val, date):
                val = val.strftime("%m/%d/%Y")
            parts.append(f"{FIELD_LABELS[f]}: {val}")
    return "; ".join(parts)


def _llm_turn(session: CallSession, task_instruction: str, user_utterance: Optional[str]) -> dict:
    messages = prompts.build_messages(
        history=session.history,
        collected={k: (v.strftime("%m/%d/%Y") if isinstance(v, date) else v) for k, v in session.collected.items()},
        task_instruction=task_instruction,
        user_utterance=user_utterance,
    )
    result = chat_json(messages)
    # keep a trimmed rolling history for context in later turns
    if user_utterance is not None:
        session.history.append({"role": "user", "content": user_utterance})
    if result.get("reply"):
        session.history.append({"role": "assistant", "content": result["reply"]})
    return result


def _apply_extracted(session: CallSession, extracted: dict) -> Tuple[list, list]:
    """Validates every proposed field. Returns (accepted_fields, rejected: [(field, err)])."""
    accepted, rejected = [], []
    for field, raw_value in (extracted or {}).items():
        if field not in FIELD_LABELS:
            continue
        ok, err, normalized = _validate_field(field, raw_value)
        if ok:
            session.collected[field] = normalized
            accepted.append(field)
            if field in session.field_queue:
                session.field_queue.remove(field)
            if field in session.optional_queue:
                session.optional_queue.remove(field)
        else:
            rejected.append((field, err))
    return accepted, rejected


def start_call(session: CallSession, db: Session) -> str:
    """Handles the very first turn of a call (no caller speech yet)."""
    session.log_turn("agent", GREETING)
    existing = None
    if session.caller_number:
        existing = crud.get_patient_by_phone(db, session.caller_number)
    if existing:
        session.stage = "duplicate_check"
        session.existing_patient_id = existing.patient_id
        msg = (
            f"Hi, thanks for calling! It looks like we already have a record "
            f"for {existing.first_name} {existing.last_name}. Would you like "
            f"to update your information instead of starting a new "
            f"registration?"
        )
        session.log_turn("agent", msg)
        return msg
    session.stage = "collecting"
    return GREETING


def handle_turn(session: CallSession, user_text: Optional[str], db: Session) -> Tuple[str, bool]:
    """
    Main entry point called by the voice router for every subsequent turn.
    Returns (reply_text, should_hangup).
    """
    if not user_text or not user_text.strip():
        session.no_input_count += 1
        if session.no_input_count >= MAX_NO_INPUT_RETRIES:
            session.log_turn("agent", NO_INPUT_GOODBYE)
            return NO_INPUT_GOODBYE, True
        session.log_turn("agent", NO_INPUT_REPROMPT)
        return NO_INPUT_REPROMPT, False
    session.no_input_count = 0
    session.log_turn("caller", user_text)

    try:
        if session.stage == "duplicate_check":
            return _handle_duplicate_check(session, user_text)
        if session.stage in ("collecting", "collecting_optional"):
            return _handle_collecting(session, user_text)
        if session.stage == "offer_optional":
            return _handle_offer_optional(session, user_text)
        if session.stage == "confirming":
            return _handle_confirming(session, user_text, db)
        if session.stage == "correcting":
            return _handle_correcting(session, user_text)
    except LLMError as e:
        logger.error(f"LLM error mid-call {session.call_sid}: {e}")
        msg = (
            "Sorry, I'm having a little trouble understanding right now — "
            "could you repeat that one more time?"
        )
        session.log_turn("agent", msg)
        return msg, False

    # Fallback — shouldn't normally be reached
    msg = "Sorry, could you say that again?"
    return msg, False


def _handle_duplicate_check(session: CallSession, user_text: str) -> Tuple[str, bool]:
    result = _llm_turn(
        session,
        "Determine whether the caller wants to UPDATE their existing record "
        "(intent=confirm_yes) or start a NEW registration instead "
        "(intent=confirm_no). Reply briefly acknowledging their choice and, "
        "if updating, ask for the first field to change or confirm nothing "
        "has changed; if starting fresh, ask for their first name.",
        user_text,
    )
    intent = result.get("intent")
    if intent == "confirm_yes":
        session.is_update = True
        session.stage = "collecting"
        # Pre-seed field_queue with only fields still worth asking about;
        # simplest robust approach: re-collect required fields, prefilled
        # answers will be accepted instantly if caller repeats them.
    else:
        session.is_update = False
        session.existing_patient_id = None
        session.stage = "collecting"
    reply = result.get("reply") or "Got it — let's continue. What's your first name?"
    session.log_turn("agent", reply)
    return reply, False


def _handle_collecting(session: CallSession, user_text: str) -> Tuple[str, bool]:
    target_field = _current_target_field(session)
    task = (
        f"You still need the caller's {FIELD_LABELS.get(target_field, target_field)}. "
        f"Extract it (and any other fields they mention) from their message, "
        f"then ask for the next missing field in a natural way. If they "
        f"seem to want to start over, set intent=restart."
    )
    result = _llm_turn(session, task, user_text)

    if result.get("intent") == "restart":
        _reset_collection(session)
        msg = "No problem, let's start over. What's your first name?"
        session.log_turn("agent", msg)
        return msg, False

    accepted, rejected = _apply_extracted(session, result.get("extracted", {}))

    if rejected:
        field, err = rejected[0]
        label = FIELD_LABELS.get(field, field)
        msg = f"Hmm, I didn't get a valid {label} — {err}. Could you tell me your {label} again?"
        session.log_turn("agent", msg)
        return msg, False

    next_field = _current_target_field(session)
    if next_field:
        # LLM's own reply already asks a natural next question; trust it if
        # it actually collected something this turn, otherwise use a safe
        # deterministic fallback so we never stall.
        reply = result.get("reply") or f"Thanks. And what's your {FIELD_LABELS[next_field]}?"
        session.log_turn("agent", reply)
        return reply, False

    # queue exhausted -> move to next stage
    if session.stage == "collecting":
        session.stage = "offer_optional"
        msg = (
            "Great, that's everything I need. I can also collect your "
            "insurance information, an emergency contact, your email, or "
            "your preferred language if you'd like — want to add any of "
            "that now, or should I go ahead and read back what I have?"
        )
        session.log_turn("agent", msg)
        return msg, False
    else:  # collecting_optional queue exhausted
        return _move_to_confirming(session)


def _handle_offer_optional(session: CallSession, user_text: str) -> Tuple[str, bool]:
    result = _llm_turn(
        session,
        "The caller is responding to whether they want to add optional "
        "info (insurance, emergency contact, email, preferred language). "
        "Set intent=opt_in_optional or opt_out_optional accordingly. If "
        "opting in, also extract any optional fields they already mentioned.",
        user_text,
    )
    accepted, rejected = _apply_extracted(session, result.get("extracted", {}))
    intent = result.get("intent")

    if intent == "opt_in_optional":
        session.optional_queue = [f for f in OPTIONAL_FIELDS if f not in session.collected]
        session.stage = "collecting_optional"
        if not session.optional_queue:
            return _move_to_confirming(session)
        reply = result.get("reply") or f"Sure — what's your {FIELD_LABELS[session.optional_queue[0]]}?"
        session.log_turn("agent", reply)
        return reply, False

    # default / opt_out -> go straight to confirmation
    return _move_to_confirming(session)


def _move_to_confirming(session: CallSession) -> Tuple[str, bool]:
    session.stage = "confirming"
    summary = _confirmation_summary(session)
    msg = (
        f"Okay, let me read that back to you: {summary}. Does everything "
        f"sound correct, or is there anything you'd like to change?"
    )
    session.log_turn("agent", msg)
    return msg, False


def _handle_confirming(session: CallSession, user_text: str, db: Session) -> Tuple[str, bool]:
    result = _llm_turn(
        session,
        "The caller is responding to the confirmation read-back. If they "
        "confirm everything is correct, set intent=confirm_yes. If they "
        "want to change something, set intent=confirm_no AND include the "
        "corrected value(s) in 'extracted' if they stated them directly "
        "(e.g. 'actually my last name is Davis'), OR if they only named "
        "the field without a new value, just note it in your reply asking "
        "them for the corrected value.",
        user_text,
    )
    intent = result.get("intent")
    accepted, rejected = _apply_extracted(session, result.get("extracted", {}))

    if rejected:
        field, err = rejected[0]
        label = FIELD_LABELS.get(field, field)
        msg = f"Sorry, that {label} doesn't look right — {err}. Could you repeat it?"
        session.log_turn("agent", msg)
        return msg, False

    if intent == "confirm_yes" and not accepted:
        return _save_patient(session, db)

    if accepted:
        # they corrected something with a value included — re-confirm
        return _move_to_confirming(session)

    if intent == "confirm_no":
        # they flagged a problem but didn't give a new value yet
        reply = result.get("reply") or "Sure — what would you like to correct, and what should it be?"
        session.stage = "correcting"
        session.log_turn("agent", reply)
        return reply, False

    # unclear -> ask again
    reply = result.get("reply") or "Sorry, should I go ahead and save this, or is something incorrect?"
    session.log_turn("agent", reply)
    return reply, False


def _handle_correcting(session: CallSession, user_text: str) -> Tuple[str, bool]:
    result = _llm_turn(
        session,
        "The caller is telling you which field to correct and its new "
        "value. Extract it into 'extracted'.",
        user_text,
    )
    accepted, rejected = _apply_extracted(session, result.get("extracted", {}))
    if rejected:
        field, err = rejected[0]
        label = FIELD_LABELS.get(field, field)
        msg = f"That {label} still doesn't look valid — {err}. Could you say it again?"
        session.log_turn("agent", msg)
        return msg, False
    if accepted:
        return _move_to_confirming(session)
    reply = result.get("reply") or "Sorry, I didn't catch the correction — could you repeat it?"
    session.log_turn("agent", reply)
    return reply, False


def _reset_collection(session: CallSession):
    session.collected = {}
    session.field_queue = list(REQUIRED_FIELDS)
    session.optional_queue = []
    session.stage = "collecting"
    session.correction_target = None


def _save_patient(session: CallSession, db: Session) -> Tuple[str, bool]:
    session.stage = "saving"
    try:
        if session.is_update and session.existing_patient_id:
            patient = crud.get_patient(db, session.existing_patient_id)
            patient = crud.update_patient(db, patient, session.collected)
        else:
            patient = crud.create_patient(db, session.collected)
        session.existing_patient_id = patient.patient_id
        logger.info(
            f"Call {session.call_sid} saved patient {patient.patient_id}: "
            f"{session.collected_json()}"
        )
        session.stage = "done"
        msg = f"You're all set, {patient.first_name}! Thanks for calling, and have a great day."
        session.log_turn("agent", msg)
        return msg, True
    except Exception as e:
        logger.error(f"Call {session.call_sid} failed to save patient: {e}")
        session.log_turn("agent", GOODBYE_TECH_ISSUE)
        session.stage = "done"
        return GOODBYE_TECH_ISSUE, True
