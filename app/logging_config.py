"""
file that is used to manage and saving the whole project flow their logs .
"""
import logging
import os
from app.config import settings


def setup_logging() -> logging.Logger:
    os.makedirs(os.path.dirname(settings.LOG_FILE) or ".", exist_ok=True)

    logger = logging.getLogger("voice_agent")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger  # avoid duplicate handlers on reload

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(settings.LOG_FILE)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()
