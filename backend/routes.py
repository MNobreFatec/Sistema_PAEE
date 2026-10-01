from pathlib import Path

from backend.routes.aluno import buscar_aluno_por_email, criar_aluno
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from backend.routes.autenticacao import criar_access_token
from backend.core.seguranca import verificar_senha
from backend.models.models import AlunoCreate

app = FastAPI()

@app.post("/aluno")
def criar_aluno_endpoint(aluno: AlunoCreate):
    resultado = criar_aluno(aluno)
    if resultado["success"]:
        return resultado
    else:
        raise HTTPException(status_code=400, detail=resultado["message"])

# Endpoint para login de usuario
@app.post("/login", status_code=status.HTTP_200_OK, responses={ #Lista de respostas possíveis para o endpoint, com seus respectivos códigos de status e descrições.
        401: {"description": "E-mail ou senha inválidos."},
        422: {"description": "Dados de login inválidos ou ausentes."},
        500: {"description": "Erro interno inesperado."}
    })
async def login_route(formulario: OAuth2PasswordRequestForm = Depends()):
    email = formulario.username
    senha = formulario.password

    aluno_banco = buscar_aluno_por_email(email)
    if not aluno_banco["success"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"}
        )

    dados_aluno = aluno_banco["aluno"]
    senha_valida = verificar_senha(senha, dados_aluno["senha_hash"])

    if not senha_valida:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = criar_access_token({"sub": dados_aluno["email"]})
    return {
        "access_token": token,
        "token_type": "bearer"
    }


