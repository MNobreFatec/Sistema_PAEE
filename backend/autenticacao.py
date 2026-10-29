"""Dependências de autenticação compatíveis com a API PostgreSQL versionada."""
from fastapi import Depends, HTTPException

from backend.api.router import obter_usuario_atual as _obter_usuario_atual


def obter_usuario_atual(usuario: dict = Depends(_obter_usuario_atual)):
    return usuario


def _verificar_tipo(usuario: dict, tipo: str, nome: str):
    if str(usuario.get("nivel_usuario", "")).upper() != tipo:
        raise HTTPException(
            status_code=403,
            detail=f"Acesso permitido apenas para {nome}.",
        )
    return usuario


def verificar_coordenador(usuario=Depends(obter_usuario_atual)):
    return _verificar_tipo(usuario, "COORDENADOR", "coordenadores")


def verificar_professor(usuario=Depends(obter_usuario_atual)):
    return _verificar_tipo(usuario, "PROFESSOR", "professores")


def verificar_assistente(usuario=Depends(obter_usuario_atual)):
    return _verificar_tipo(usuario, "ASSISTENTE", "assistentes")


def verificar_aluno(usuario=Depends(obter_usuario_atual)):
    return _verificar_tipo(usuario, "ALUNO", "alunos")


def verificar_administrador(usuario=Depends(obter_usuario_atual)):
    return _verificar_tipo(usuario, "ADMINISTRADOR", "administradores")
