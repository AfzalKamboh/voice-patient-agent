# Voice AI Patient Registration System

This project is a phone-based AI patient registration system. The idea is simple: a patient calls a Twilio number, talks to the agent, provides the required registration details, and the system validates and saves the information in the database.

I built the backend with FastAPI and kept the voice/conversation logic separate from the REST API and database layer. The LLM is used for understanding what the caller said and deciding the next response, but I do not use the LLM as the final authority for patient data. The extracted values are always checked by Python validators before they are saved.

### Stack

- Python
- FastAPI
- SQLAlchemy
- SQLite (Postgres can be used through `DATABASE_URL`)
- Twilio for calls and speech-to-text
- `gpt-oss` through Ollama Cloud
- ElevenLabs for text-to-speech


---

## 1. How the system works

The overall flow is:

```text
Caller
   │
   │ calls Twilio number
   ▼
┌─────────────────────────┐
│ Twilio                  │
│ Voice + <Gather speech> │
└───────────┬─────────────┘
            │
            │ POST webhooks
            ▼
┌─────────────────────────────────────────────────────────┐
│ FastAPI                                                  │
│                                                          │
│ /voice/* ──► conversation.py (conversation state)       │
│                    │                                     │
│                    ├──► llm_client.py ──► Ollama Cloud  │
│                    │       gpt-oss + JSON output         │
│                    │                                     │
│                    ├──► validators.py                   │
│                    │       server-side validation        │
│                    │                                     │
│                    └──► tts_client.py ──► ElevenLabs    │
│                            fallback to Twilio <Say>      │
│                                                          │
│ /patients ──► patients.py ──► crud.py ──► database      │
└───────────────────────────┬─────────────────────────────┘
                            ▼
                     SQLite / Postgres
                     patients, call_logs
```

I kept the main parts separated so that the voice layer does not become responsible for database operations, and the REST API does not need to know anything about Twilio or the LLM.

### Project responsibilities

**Telephony**

`app/routers/voice.py` handles the Twilio webhooks and TwiML responses. It receives the call, gets the speech input, and passes the conversation work to the voice agent.

**Conversation and LLM**

The conversation logic is under `app/voice_agent/`.

`conversation.py` manages the conversation state. On each turn it calls the LLM through `llm_client.py`, but the result from the model is treated as a proposal rather than trusted data.

`validators.py` checks the extracted values before they are accepted.

This separation is important because an LLM can misunderstand speech or return something that looks valid but is not actually valid for the application.

**Database**

`models.py`, `crud.py`, and `database.py` contain the database layer.

Both the REST API and the voice agent use the same CRUD/database code. This means a patient created through the API and a patient registered through a phone call follow the same persistence path.

**REST API**

`app/routers/patients.py` contains the patient endpoints. It talks to the CRUD layer and does not contain Twilio, LLM, or TTS logic.


---

## 2. Why I used this stack

| Part | Choice | Reason |
|---|---|---|
| Telephony + STT | Twilio + `<Gather input="speech">` | Twilio gives me a real phone number and handles speech-to-text, so I did not need to build an STT service for this project. |
| LLM | `gpt-oss` via Ollama Cloud | I wanted to use an open-source model without requiring a local GPU. Ollama Cloud also exposes the API in a way that works with the same basic interface as Ollama. |
| TTS | ElevenLabs | It gives the agent more natural voice output. I also added Twilio `<Say>` as a fallback so a TTS failure does not leave the caller with silence. |
| Backend | FastAPI | It works well for the REST API as well as Twilio webhook endpoints, and Pydantic makes request validation straightforward. |
| Database | SQLite + SQLAlchemy | SQLite keeps the setup simple for this project. The database URL is configurable, so it can be changed to Postgres later without changing the application logic. |


---

## 3. Setup

### 3.1 What is required

Before running the project, I need:

- Python 3.11+
- A Twilio account with a purchased phone number
- An Ollama Cloud API key for the `gpt-oss` model
- An ElevenLabs API key
- ngrok (or another HTTPS tunnel) when running locally

Twilio needs to reach the FastAPI application over HTTPS, which is why I use ngrok during local testing.

### 3.2 Install

```bash
git clone <this-repo>

cd voice-patient-agent

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
```

Then I fill the required values in `.env`.

### 3.3 Run locally

```bash
./run.sh
```

This starts FastAPI on port `8000`.

In another terminal:

```bash
ngrok http 8000
```

ngrok gives me a public HTTPS URL such as:

```text
https://xxxx.ngrok-free.app
```

I put that URL in `.env` as `PUBLIC_BASE_URL`.

This is also used when generating the public ElevenLabs audio URLs that Twilio needs to play back.

After changing the environment variable, I restart the application.

### 3.4 Configure the Twilio number

In the Twilio Console, I configure the phone number like this:

**A call comes in**

```text
POST https://<your-public-url>/voice/incoming
```

**Call status changes**

```text
POST https://<your-public-url>/voice/status
```

After that, calling the Twilio number starts the registration flow.

### 3.5 Environment variables

The complete list is in `.env.example`.

The important variables are:

| Variable | Purpose |
|---|---|
| `PUBLIC_BASE_URL` | Public HTTPS URL used by Twilio and for ElevenLabs audio URLs |
| `DATABASE_URL` | SQLAlchemy database connection string; defaults to local SQLite |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_PHONE_NUMBER` | Twilio configuration |
| `OLLAMA_BASE_URL` / `OLLAMA_API_KEY` / `OLLAMA_MODEL` | Ollama Cloud connection and model configuration |
| `ELEVENLABS_API_KEY` / `ELEVENLABS_VOICE_ID` / `ELEVENLABS_MODEL_ID` | ElevenLabs configuration |

I do not keep these credentials in the source code. They are loaded through `app/config.py`.

### 3.6 Tests

```bash
pytest tests/ -v
```

The tests cover the main patient API operations, including:

- patient creation
- invalid phone numbers
- invalid states
- future dates of birth
- filtering
- retrieving a patient
- partial updates
- soft deletion


---

## 4. REST API

The API uses a simple response structure:

```json
{
  "data": "...",
  "error": null
}
```

The main endpoints are:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/patients` | List patients. Supports `last_name`, `date_of_birth`, and `phone_number` filters. |
| `GET` | `/patients/{id}` | Get a single patient |
| `POST` | `/patients` | Create a patient |
| `PUT` | `/patients/{id}` | Partially update a patient |
| `DELETE` | `/patients/{id}` | Soft-delete a patient by setting `deleted_at` |

When the server is running, FastAPI's Swagger UI is available at:

```text
/docs
```


---

## 5. Voice agent

### 5.1 Conversation flow

The conversation is handled as a state machine:

```text
greeting
   ↓
duplicate_check (if returning caller)
   ↓
collecting required fields
   ↓
offer optional fields
   ↓
collecting optional fields
   ↓
confirming
   ↓
saving
   ↓
done
```

The caller can also ask to start over during the collection stages.

During confirmation, the caller can correct a value. For example, if the caller says:

> "Actually my last name is spelled D-A-V-I-S, not D-A-V-I-E-S."

the LLM extracts the correction, the value goes through the normal validation process, and the confirmation summary is generated again.

### 5.2 The LLM does not directly control the data

One of the main decisions I made in this project was to keep validation outside the LLM.

For every turn, `gpt-oss` is asked to return JSON containing:

```json
{
  "extracted": {},
  "intent": "...",
  "reply": "..."
}
```

`extracted` contains any patient fields the model thinks it heard.

`intent` describes what the caller is trying to do.

`reply` is the response that can be spoken to the caller.

However, I do not directly save the values returned by `extracted`.

Every extracted value is passed through `app/validators.py`. These are the same validation rules used by the REST API.

For example, if the model extracts an invalid phone number, future date of birth, or unknown state, the application rejects that value and asks the caller specifically for that field again.

This gives me two separate responsibilities:

```text
LLM
 └── understand the caller and suggest a response

Python validation
 └── decide whether the extracted patient data is acceptable
```

This also means the confirmation step only reads back values that have already passed validation.

The system prompt used by the model is in:

```text
app/voice_agent/prompts.py
```

### 5.3 Returning callers

I also added duplicate detection.

When a call comes in, the caller's phone number from Twilio (`From`) is checked against existing patients.

If the number already exists, the agent greets the caller by name and offers to update the existing record instead of creating another patient.

### 5.4 Call logging

I keep a transcript of the conversation in memory while the call is active.

When the call ends, the available information is written to the `call_logs` table. This includes the conversation and a JSON snapshot of the information collected during the call.

The final payload is also logged to:

```text
stdout
logs/agent.log
```

The logging setup is in:

```text
app/logging_config.py
```


---

## 6. Error handling and edge cases

I handled the main failure cases that can happen during a phone conversation.

| Situation | What happens |
|---|---|
| Invalid patient data | The specific field is rejected by `validators.py` and the caller is asked for that field again. |
| Caller is silent | Twilio `<Gather>` times out and the agent retries up to `MAX_NO_INPUT_RETRIES`. After that, the call ends politely. |
| Call drops | The Twilio status callback logs the partial information collected so far and clears the in-memory session. |
| Database save fails | The caller gets an apology and is asked to call back instead of the call ending silently. |
| ElevenLabs fails | The system falls back to Twilio `<Say>`. |
| LLM call fails | `LLMError` is handled and the caller is asked to repeat instead of the application crashing. |
| Caller wants to start again | The current fields are cleared and the registration starts again from the first name. |
| Existing phone number | The existing patient is offered for update instead of creating a duplicate. |
| Server restarts during a call | A new session is created for the `CallSid`. The current call can continue, but progress from before the restart is lost. |


---

## 7. Current limitations

There are a few things I would change before treating this as a full production system.

### In-memory call sessions

The current conversation sessions are stored in:

```text
app/voice_agent/session_store.py
```

This is fine for a single application instance, but it would not be the right approach for multiple application instances.

For a multi-instance deployment, I would move the session state to Redis so that any instance can handle the next webhook for the same `CallSid`.

### SQLite

SQLite is being used because it keeps the project easy to run.

For production I would normally use Postgres. The application already uses `DATABASE_URL`, so changing the database connection does not require changing the patient CRUD logic.

### Twilio request validation

Twilio request signature validation is disabled by default:

```text
VALIDATE_TWILIO_SIGNATURE=false
```

I kept it this way to make local/ngrok testing easier.

For a real deployment, I would enable it:

```text
VALIDATE_TWILIO_SIGNATURE=true
```

### English-only conversation

The current prompts are written for English.

I have not implemented automatic language detection or language switching. This could be added later by detecting the language from the first caller response and changing the LLM prompt and ElevenLabs voice accordingly.

### No true barge-in

The current implementation uses Twilio `<Gather>`, so it waits for the caller's speech input rather than supporting true mid-sentence interruption.

### TTS files

ElevenLabs audio files are stored under:

```text
static/audio/
```

These files currently accumulate. A production version should have a cleanup process, for example a TTL-based job that removes old files.


---

## 8. What I would add next

If I continue working on this project, my next changes would be:

1. Move call sessions to Redis.
2. Add multilingual support, starting with language detection on the first turn.
3. Add a small dashboard for viewing registered patients through the existing API.
4. Add appointment scheduling after patient registration.
5. Enable and verify Twilio webhook signatures in production.

The current implementation is intentionally focused on the core flow: receiving a call, understanding the caller, validating the information, confirming it, and saving the patient record reliably.
