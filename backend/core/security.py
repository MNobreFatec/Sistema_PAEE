"""Funções de hash de senha e tokens usados pelas APIs."""
import bcrypt
from jose import JWTError, jwt

from backend.core.config import get_secret_key

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def gerar_hash(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except (ValueError, TypeError, UnicodeError):
        return False


def criar_access_token(subject: str) -> str:
    from datetime import datetime, timedelta, timezone

    payload = {
        "sub": subject,
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, get_secret_key(), algorithm=ALGORITHM)


def decodificar_access_token(token: str) -> dict:
    return jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])


__all__ = [
    "ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "JWTError",
    "criar_access_token",
    "decodificar_access_token",
    "gerar_hash",
    "verificar_senha",
]
