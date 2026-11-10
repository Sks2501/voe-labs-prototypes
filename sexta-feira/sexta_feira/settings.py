"""Configurações de baixo consumo para computadores sem GPU dedicada."""
from __future__ import annotations
import os
from pathlib import Path

MODELS = {
    "small": "openai-community/gpt2",
    "medium": "openai-community/gpt2-medium",
    "large": "openai-community/gpt2-large",
}
DEFAULT_MODEL = "small"
MAX_NEW_TOKENS = 64
MAX_INPUT_TOKENS = 720
MAX_TEXT_LENGTH = 2400
DATA_DIR = Path(os.environ.get("SEXTA_DATA_DIR") or (
    Path(os.environ["LOCALAPPDATA"]) / "SextaFeira"
    if os.name == "nt" and os.environ.get("LOCALAPPDATA")
    else Path.home() / ".sexta-feira"
))
DB_PATH = DATA_DIR / "memory.sqlite3"
