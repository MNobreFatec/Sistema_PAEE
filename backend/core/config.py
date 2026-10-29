"""Configuração carregada do ambiente, sem valores secretos padrão."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")


class ConfigurationError(RuntimeError):
    """Configuração necessária para uma operação está ausente."""


def get_secret_key() -> str:
    secret_key = os.getenv("SECRET_KEY", "").strip()
    if not secret_key:
        raise ConfigurationError("Configure SECRET_KEY no ambiente do backend.")
    return secret_key
