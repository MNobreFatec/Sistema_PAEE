"""Endpoints versionados para autenticação e tabelas existentes."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.repositories import postgres
from backend.repositories.postgres import DatabaseUnavailable
from backend.schemas.api import (
    LoginRequest,
    LoginResponse,
    PerfilResponse,
    TelefoneCreate,
    TelefoneResponse,
    UsuarioPublico,
)
from backend.services import postgres_api
from backend.services.postgres_api import (
    AuthenticationUnavailable,
    InvalidCredentials,
    InvalidToken,
)

api_router = APIRouter()
bearer = HTTPBearer(auto_error=False)


def obter_usuario_atual(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return postgres_api.usuario_do_token(credentials.credentials)
    except InvalidToken:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AuthenticationUnavailable:
        raise HTTPException(status_code=503, detail="Autenticação indisponível.")
    except DatabaseUnavailable:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.")


@api_router.get("/tipos-usuario")
def listar_tipos_usuario():
    try:
        return postgres.listar_tipos_usuario()
    except DatabaseUnavailable:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.")


@api_router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    try:
        return postgres_api.autenticar(payload.email, payload.senha)
    except InvalidCredentials:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
    except AuthenticationUnavailable:
        raise HTTPException(status_code=503, detail="Autenticação indisponível.")
    except DatabaseUnavailable:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.")


@api_router.get("/usuarios/me", response_model=UsuarioPublico)
def obter_usuario_logado(usuario: dict = Depends(obter_usuario_atual)):
    return postgres_api.usuario_publico(usuario)


@api_router.get("/perfil/me", response_model=PerfilResponse)
def obter_perfil_logado(usuario: dict = Depends(obter_usuario_atual)):
    try:
        perfil = postgres_api.perfil_do_usuario(usuario)
    except DatabaseUnavailable:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.")
    if perfil is None:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    return {"tipo": usuario["nivel_usuario"], "dados": perfil}


@api_router.get("/telefones", response_model=list[TelefoneResponse])
def listar_telefones(usuario: dict = Depends(obter_usuario_atual)):
    try:
        return postgres.listar_telefones(usuario["id_usuario"])
    except DatabaseUnavailable:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.")


@api_router.post(
    "/telefones",
    response_model=TelefoneResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_telefone(
    payload: TelefoneCreate,
    usuario: dict = Depends(obter_usuario_atual),
):
    try:
        return postgres.criar_telefone(usuario["id_usuario"], payload.numero_tel)
    except DatabaseUnavailable:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.")


@api_router.delete("/telefones/{id_tel}", status_code=status.HTTP_204_NO_CONTENT)
def remover_telefone(
    id_tel: int,
    usuario: dict = Depends(obter_usuario_atual),
):
    try:
        removido = postgres.remover_telefone(usuario["id_usuario"], id_tel)
    except DatabaseUnavailable:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.")
    if not removido:
        raise HTTPException(status_code=404, detail="Telefone não encontrado.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
