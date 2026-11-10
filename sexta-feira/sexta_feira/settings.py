"""Configurações de baixo consumo para computadores sem GPU dedicada."""
from __future__ import annotations
import os
from pathlib import Path

MODELS = {"small": "124M", "medium": "355M"}
DEFAULT_MODEL = "small"
MAX_NEW_TOKENS = 64
MAX_INPUT_TOKENS = 512
MAX_TEXT_LENGTH = 2400
DATA_DIR = Path(os.environ.get("SEXTA_DATA_DIR") or (
    Path(os.environ["LOCALAPPDATA"]) / "SextaFeira"
    if os.name == "nt" and os.environ.get("LOCALAPPDATA")
    else Path.home() / ".sexta-feira"
))
DB_PATH = DATA_DIR / "memory.sqlite3"
MODEL_DIR = Path(os.environ.get("SEXTA_MODEL_DIR") or DATA_DIR / "models")
TOKEN_FILE = Path(os.environ.get("SEXTA_TOKEN_FILE") or DATA_DIR / "access.token")
MAX_REQUEST_BYTES = 8192
MAX_HTTP_CONNECTIONS = 16
SESSION_TTL_SECONDS = 12 * 60 * 60
RATE_LIMIT_REQUESTS = 60
RATE_LIMIT_SECONDS = 60
