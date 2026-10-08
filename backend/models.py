# models.py
from typing import Literal, Union, Annotated
from pydantic import BaseModel, EmailStr, Field, field_validator


def texto_obrigatorio(valor: str, nome_campo: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"O campo '{nome_campo}' não pode ser vazio ou conter apenas espaços")
    return valor.strip()


class UsuarioBase(BaseModel):
    email: EmailStr
    senha: str = Field(..., min_length=8)


class AlunoCreate(UsuarioBase):
    id_tipo_usuario: Literal[1] = 1
    matricula: int = Field(..., gt=0)
    nome: str
    curso: str
    periodo: int = Field(..., gt=0)
    tel_num: str

    @field_validator("nome", "curso", "tel_num")
    @classmethod
    def _valida_textos(cls, v, info):
        return texto_obrigatorio(v, info.field_name)


class ProfessorCreate(UsuarioBase):
    id_tipo_usuario: Literal[2] = 2
    nome: str

    @field_validator("nome")
    @classmethod
    def _valida_textos(cls, v, info):
        return texto_obrigatorio(v, info.field_name)


class AssistenteCreate(UsuarioBase):
    id_tipo_usuario: Literal[3] = 3
    cnpj_emp: int = Field(..., gt=0)
    nome_emp: str
    nome: str
    especialidade: str
    tel_num: str

    @field_validator("nome_emp", "nome", "especialidade", "tel_num")
    @classmethod
    def _valida_textos(cls, v, info):
        return texto_obrigatorio(v, info.field_name)


class CoordenadorCreate(UsuarioBase):
    id_tipo_usuario: Literal[4] = 4
    nome: str
    curso: str

    @field_validator("nome", "curso")
    @classmethod
    def _valida_textos(cls, v, info):
        return texto_obrigatorio(v, info.field_name)


UsuarioCreate = Annotated[
    Union[AlunoCreate, ProfessorCreate, AssistenteCreate, CoordenadorCreate],
    Field(discriminator="id_tipo_usuario")
]