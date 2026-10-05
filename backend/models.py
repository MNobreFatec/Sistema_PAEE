from pydantic import BaseModel, EmailStr, Field

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
    

