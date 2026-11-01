"""Central configuration loaded from the environment (.env).

Keeps credentials out of the source code and makes every dependency
(database, model files, upload folder) overridable via environment variables.
"""

import os

from dotenv import load_dotenv

# Load variables from .env in the project root (no-op if the file is absent).
load_dotenv()


def _get_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    # --- Flask ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-key-change-me")
    DEBUG = _get_bool("FLASK_DEBUG", True)

    # --- PostgreSQL ---
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "soilmate_db")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    # --- Files ---
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join("static", "uploads"))
    MODEL_PATH = os.getenv("MODEL_PATH", "soil_model.pth")
    CLASSES_PATH = os.getenv("CLASSES_PATH", "classes.json")

    # --- Model inference ---
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))
