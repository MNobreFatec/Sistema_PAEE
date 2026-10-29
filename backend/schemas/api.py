"""Schemas HTTP para autenticação e recursos do schema PostgreSQL existente."""
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1, max_length=72)


class UsuarioPublico(BaseModel):
    id_usuario: int
    email: EmailStr
    nivel_usuario: str
    ativo: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioPublico


class TelefoneCreate(BaseModel):
    numero_tel: int = Field(gt=0)


class TelefoneResponse(BaseModel):
    id_tel: int
    id_usuario: int
    numero_tel: int


class RelatorioCreate(BaseModel):
    id_aluno: int = Field(gt=0)
    data_relatorio: str
    descricao: str = Field(min_length=1)
    observacao: str = ""


class PerfilResponse(BaseModel):
    tipo: str
    dados: dict[str, Any]
