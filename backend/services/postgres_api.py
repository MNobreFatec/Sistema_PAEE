"""Casos de uso da API PostgreSQL, sem dependência de HTTP."""
from backend.repositories import postgres
from backend.core.config import ConfigurationError
from backend.core.security import (
    JWTError,
    criar_access_token,
    decodificar_access_token,
    verificar_senha,
)


class InvalidCredentials(Exception):
    """Login inválido ou conta inativa."""


class InvalidToken(Exception):
    """Token ausente, inválido ou expirado."""


class AuthenticationUnavailable(Exception):
    """Chave de assinatura não configurada."""


def usuario_publico(usuario: dict) -> dict:
    return {
        "id_usuario": usuario["id_usuario"],
        "email": usuario["email"],
        "nivel_usuario": usuario["nivel_usuario"],
        "ativo": usuario["ativo"],
    }


def autenticar(email: str, senha: str) -> dict:
    usuario = postgres.obter_usuario_por_email(email)
    if (
        not usuario
        or not usuario.get("ativo")
        or not verificar_senha(senha, usuario.get("senha_hash") or "")
    ):
        raise InvalidCredentials
    try:
        token = criar_access_token(str(usuario["id_usuario"]))
    except ConfigurationError as exc:
        raise AuthenticationUnavailable from exc
    return {"access_token": token, "token_type": "bearer", "usuario": usuario_publico(usuario)}


def usuario_do_token(token: str) -> dict:
    try:
        payload = decodificar_access_token(token)
        id_usuario = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise InvalidToken from exc
    except ConfigurationError as exc:
        raise AuthenticationUnavailable from exc

    usuario = postgres.obter_usuario_por_id(id_usuario)
    if not usuario or not usuario.get("ativo"):
        raise InvalidToken
    return usuario


def perfil_do_usuario(usuario: dict):
    return postgres.obter_perfil_usuario(
        usuario["id_usuario"], usuario["nivel_usuario"]
    )
