from pydantic import BaseModel, EmailStr, Field, field_validator

class UsuarioCreate(BaseModel):
    id_tipo_usuario: int
    email: EmailStr
    senha: str = Field(..., min_length=8)  # Adicionando validação de tamanho da senha
    matricula: int
    nome: str
    curso: str
    periodo: int
    cnpj_emp: int
    nome_emp: str
    especialidade: str
    tel_num: str

    @field_validator("nome", "curso", "nome_emp", "especialidade", "tel_num", mode="before")
    @classmethod
    def campos_texto_nao_podem_ser_vazios(cls, valor, info):
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError(f"O campo '{info.field_name}' não pode ser vazio ou conter apenas espaços")
        return valor.strip()

    @field_validator("matricula", "periodo", "cnpj_emp")
    @classmethod
    def campos_numericos_devem_ser_positivos(cls, valor, info):
        if valor <= 0:
            raise ValueError(f"O campo '{info.field_name}' deve ser maior que zero")
        return valor

    @field_validator("id_tipo_usuario")
    @classmethod
    def tipo_usuario_valido(cls, valor):
        if valor not in (1, 2, 3, 4):
            raise ValueError("id_tipo_usuario deve ser 1 (aluno), 2 (professor), 3 (assistente) ou 4 (coordenador)")
        return valor
    

