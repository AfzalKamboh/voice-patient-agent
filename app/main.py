"""
FastAPI application main core entrypoint.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import Base, engine
from app.routers import patients, voice
from app.config import settings
from app.logging_config import logger

app = FastAPI(
    title="Voice AI Patient Registration System",
    description="Conversational voice agent + REST API for U.S. patient intake.",
    version="1.0.0",
)

# Create tables if they don't exist yet (SQLite/Postgres/etc — dialect agnostic)
Base.metadata.create_all(bind=engine)

app.mount("/audio", StaticFiles(directory=settings.AUDIO_DIR), name="audio")

app.include_router(patients.router)
app.include_router(voice.router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    # keep the required {"data": ..., "error": ...} envelope even for errors
    return JSONResponse(status_code=exc.status_code, content={"data": None, "error": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(status_code=422, content={"data": None, "error": exc.errors()})


@app.on_event("startup")
def on_startup():
    from app.seed_data import seed_if_empty
    seed_if_empty()
    logger.info(f"Voice AI Patient Registration System started (env={settings.APP_ENV})")


@app.get("/", tags=["health"])
def health_check():
    return {"data": {"status": "ok", "service": "voice-patient-agent"}, "error": None}
