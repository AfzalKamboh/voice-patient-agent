"""
Twilio webhooks — the telephony <-> voice-agent bridge.
"""
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from twilio.twiml.voice_response import VoiceResponse, Gather

from app.database import get_db
from app.voice_agent.session_store import get_or_create_session, get_session, end_session
from app.voice_agent import conversation
from app.voice_agent.tts_client import synthesize_speech, audio_url, TTSError
from app.logging_config import logger
from app.models import CallLog
from app.config import settings

router = APIRouter(prefix="/voice", tags=["voice"])

GATHER_KWARGS = dict(
    input="speech",
    action="/voice/gather",
    method="POST",
    speech_timeout="auto",
    timeout=6,
    language="en-US",
)


def _speak(vr: VoiceResponse, text: str):
    """
    Tries ElevenLabs for natural speech; falls back to Twilio's built-in
    <Say> if TTS fails for any reason, so the caller never gets dead air
    (Edge Cases & Resilience requirement).
    """
    try:
        filename = synthesize_speech(text)
        vr.play(audio_url(filename))
    except TTSError as e:
        logger.warning(f"TTS failed, falling back to Twilio <Say>: {e}")
        vr.say(text, voice="Polly.Joanna")


@router.post("/incoming")
async def incoming_call(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    call_sid = form.get("CallSid")
    caller = form.get("From")

    from app.validators import normalize_phone
    session = get_or_create_session(call_sid, normalize_phone(caller or ""))

    greeting = conversation.start_call(session, db)

    vr = VoiceResponse()
    gather = Gather(**GATHER_KWARGS)
    _speak(gather, greeting)
    vr.append(gather)
    # if Gather times out completely with no input at all, retry once
    vr.redirect("/voice/incoming_retry", method="POST")
    return Response(content=str(vr), media_type="application/xml")


@router.post("/incoming_retry")
async def incoming_retry(request: Request):
    """Reached only if the caller never said anything after the greeting."""
    vr = VoiceResponse()
    gather = Gather(**GATHER_KWARGS)
    _speak(gather, "Are you still there? Please go ahead whenever you're ready.")
    vr.append(gather)
    _speak(vr, conversation.NO_INPUT_GOODBYE)
    vr.hangup()
    return Response(content=str(vr), media_type="application/xml")


@router.post("/gather")
async def gather(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    call_sid = form.get("CallSid")
    speech_result = form.get("SpeechResult")

    session = get_session(call_sid)
    if session is None:
        # e.g. server restarted mid-call — recover gracefully instead of erroring
        from app.validators import normalize_phone
        session = get_or_create_session(call_sid, normalize_phone(form.get("From") or ""))
        session.stage = "collecting"

    reply_text, should_hangup = conversation.handle_turn(session, speech_result, db)

    vr = VoiceResponse()
    if should_hangup:
        _speak(vr, reply_text)
        vr.hangup()
        _persist_call_log(db, session)
        end_session(call_sid)
    else:
        gather_el = Gather(**GATHER_KWARGS)
        _speak(gather_el, reply_text)
        vr.append(gather_el)
        vr.redirect("/voice/gather_retry", method="POST")

    return Response(content=str(vr), media_type="application/xml")


@router.post("/gather_retry")
async def gather_retry(request: Request, db: Session = Depends(get_db)):
    """Reached if a <Gather> inside a mid-call turn times out with no speech."""
    form = await request.form()
    call_sid = form.get("CallSid")
    session = get_session(call_sid)

    reply_text, should_hangup = conversation.handle_turn(session, None, db)

    vr = VoiceResponse()
    if should_hangup:
        _speak(vr, reply_text)
        vr.hangup()
        if session:
            _persist_call_log(db, session)
            end_session(call_sid)
    else:
        gather_el = Gather(**GATHER_KWARGS)
        _speak(gather_el, reply_text)
        vr.append(gather_el)
        vr.redirect("/voice/gather_retry", method="POST")
    return Response(content=str(vr), media_type="application/xml")


@router.post("/status")
async def call_status(request: Request, db: Session = Depends(get_db)):
    """
    Twilio status callback — fires on ringing/answered/completed/failed.
    Used to log dropped/incomplete calls (Edge Cases requirement: what
    happens if the telephony connection drops mid-call).
    """
    form = await request.form()
    call_sid = form.get("CallSid")
    call_status_value = form.get("CallStatus")
    session = get_session(call_sid)

    if call_status_value in ("completed", "failed", "busy", "no-answer", "canceled"):
        if session and session.stage != "done":
            logger.warning(
                f"Call {call_sid} ended ({call_status_value}) before registration "
                f"completed. Partial data collected: {session.collected_json()}"
            )
            _persist_call_log(db, session)
        end_session(call_sid)
    return Response(status_code=204)


def _persist_call_log(db: Session, session):
    try:
        log = CallLog(
            call_sid=session.call_sid,
            patient_id=session.existing_patient_id if session.stage == "done" else None,
            transcript="\n".join(session.transcript),
            final_payload=session.collected_json(),
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to persist call log for {session.call_sid}: {e}")
