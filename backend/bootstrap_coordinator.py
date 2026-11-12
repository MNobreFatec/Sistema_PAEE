"""Provisiona a primeira conta de coordenação no JSON local, por prompt seguro."""
import getpass
import os
import re
import sys
from pathlib import Path

from backend import armazenamento_json as db
from backend.core.config import ConfigurationError, get_secret_key
from backend.core.security import gerar_hash


def main():
    if os.getenv("PAEE_ALLOW_LOCAL_BOOTSTRAP") != "1":
        print("Bloqueado: defina PAEE_ALLOW_LOCAL_BOOTSTRAP=1 para provisionamento local.")
        return 2
    environment = os.getenv("PAEE_ENVIRONMENT", "").strip().lower()
    if environment not in {"development", "local", "test"}:
        print("Bloqueado: este procedimento só funciona em ambiente local/de desenvolvimento.")
        return 2
    declared_environment = (
        os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or ""
    ).strip().lower()
    if declared_environment in {"production", "prod"}:
        print("Bloqueado: o ambiente está marcado como produção.")
        return 2
    local_data = (Path(__file__).resolve().parent / "data").resolve()
    if not db.DATA_FILE.resolve().is_relative_to(local_data):
        print("Bloqueado: o bootstrap só pode gravar em backend/data local.")
        return 2
    try:
        get_secret_key()
    except ConfigurationError:
        print("Configure SECRET_KEY no ambiente local antes do provisionamento.")
        return 2
    if any(user.get("nivel_usuario") == "COORDENADOR" for user in db.all_rows("usuarios")):
        print("Já existe uma conta de coordenação; use o gerenciamento de usuários autenticado.")
        return 2

    email = input("E-mail da conta de coordenação local: ").strip().lower()
    nome = input("Nome: ").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or not nome:
        print("E-mail ou nome inválido.")
        return 2
    senha = getpass.getpass("Senha local (mínimo 12 caracteres): ")
    confirmacao = getpass.getpass("Confirme a senha: ")
    if senha != confirmacao or len(senha) < 12 or len(senha.encode("utf-8")) > 72:
        print("A confirmação não corresponde ou a senha não atende aos requisitos.")
        return 2
    if db.get("usuarios", "email", email):
        print("Esse e-mail já está cadastrado.")
        return 2

    db.create("usuarios", {
        "email": email,
        "nome": nome,
        "nivel_usuario": "COORDENADOR",
        "senha_hash": gerar_hash(senha),
        "ativo": True,
        "bootstrap_local": True,
    }, "id_usuario")
    print("Conta local criada. Guarde a senha em um gerenciador; ela não foi gravada em texto puro.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
