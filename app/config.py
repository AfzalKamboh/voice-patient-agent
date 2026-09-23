import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- General ---
    APP_ENV: str = os.getenv("APP_ENV", "development")
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/agent.log")

    # --- Database ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./patients.db")

    # --- Twilio (telephony) ---
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")
    # If true, incoming Twilio webhook signatures are validated (recommended in production)
    VALIDATE_TWILIO_SIGNATURE: bool = os.getenv("VALIDATE_TWILIO_SIGNATURE", "false").lower() == "true"

    # --- LLM: Ollama Cloud (open-source gpt-oss model) ---
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "https://ollama.com").rstrip("/")
    OLLAMA_API_KEY: str = os.getenv("OLLAMA_API_KEY", "")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")

    # --- TTS: ElevenLabs ---
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # "Rachel" default
    ELEVENLABS_MODEL_ID: str = os.getenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")

    # --- Audio ---
    AUDIO_DIR: str = os.getenv("AUDIO_DIR", "static/audio")


settings = Settings()
