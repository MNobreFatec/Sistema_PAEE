from pydantic import BaseModel, EmailStr, Field

#classse utilizada para criar alunos
class AlunoCreate(BaseModel):
    rm: str
    nome: str
    endereco: str
    tel_aluno: str
    email: EmailStr