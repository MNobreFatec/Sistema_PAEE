from pydantic import BaseModel, EmailStr, Field

#classse utilizada para criar alunos
class AlunoCreate(BaseModel):
    rm: str
    nome: str
    endereco: str
    tel: str
    email: EmailStr
    senha: str = Field(..., min_length=8)  # Adicionando validação de tamanho da senha