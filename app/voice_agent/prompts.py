"""
Prompt engineering for the intake agent.
"""
from typing import Dict, List, Optional

from app.voice_agent.session_store import FIELD_LABELS

AGENT_PERSONA = (
    "You are Ava, a warm, efficient patient intake coordinator for a "
    "primary care clinic, speaking with a caller on the phone. You are not "
    "reading a rigid script — you have a natural, brief, friendly "
    "conversational style, like a real front-desk coordinator. Keep replies "
    "short (1-3 sentences) since this is a phone call, not a chat window. "
    "Never invent patient information. Only report what the caller actually "
    "said."
)

RESPONSE_FORMAT_INSTRUCTIONS = """
You MUST respond with ONLY a single valid JSON object (no markdown, no
commentary), with exactly these keys:

{
  "extracted": {"<field_name>": "<value the caller stated>", ...},
  "intent": "provide_info | confirm_yes | confirm_no | restart | opt_in_optional | opt_out_optional | unclear",
  "reply": "<what you will say out loud next>"
}

Rules for "extracted":
- Only include a field if the caller actually stated a value for it in
  their latest message (or clearly corrected an earlier value).
- Use the exact field_name keys given to you in the task context.
- For date_of_birth, output it as MM/DD/YYYY.
- For sex, output exactly one of: Male, Female, Other, Decline to Answer.
- For phone numbers, output digits only (no spaces or punctuation).
- Do not guess or fabricate values the caller didn't say.

Rules for "reply":
- Speak naturally and warmly, as if on a phone call.
- If instructed below to ask for a specific field, ask for exactly that field.
- If instructed to read back a confirmation summary, read back every field
  and value you were given, then ask the caller to confirm or correct it.
- If told there was a problem with a field, explain briefly what was wrong
  and ask again for just that field.
"""


def build_messages(
    history: List[Dict[str, str]],
    collected: Dict[str, str],
    task_instruction: str,
    user_utterance: Optional[str],
) -> List[Dict[str, str]]:
    """Assembles the message list sent to the LLM for one turn."""
    collected_desc = (
        ", ".join(f"{k}={v}" for k, v in collected.items()) or "(nothing yet)"
    )
    field_glossary = "\n".join(f"- {k}: {v}" for k, v in FIELD_LABELS.items())

    system = (
        AGENT_PERSONA
        + "\n\nField glossary (field_name: what it means):\n"
        + field_glossary
        + f"\n\nInformation collected so far: {collected_desc}"
        + f"\n\nYour task this turn: {task_instruction}"
        + RESPONSE_FORMAT_INSTRUCTIONS
    )

    messages = [{"role": "system", "content": system}]
    # keep only the last few turns of history to bound token usage
    messages.extend(history[-6:])
    if user_utterance is not None:
        messages.append({"role": "user", "content": user_utterance})
    return messages
