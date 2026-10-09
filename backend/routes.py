from pathlib import Path

from backend.usuario import buscar_usuario_por_email, criar_usuario
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from backend.autenticacao import criar_access_token
from backend.seguranca import verificar_senha
from backend.models import UsuarioCreate
from backend.autenticacao import verificar_coordenador

app = FastAPI()

@app.post("/usuario")
def criar_usuario_endpoint(usuario: UsuarioCreate):
    resultado = criar_usuario(usuario)
    if resultado["success"]:
        return resultado
    else:
        raise HTTPException(status_code=400, detail=resultado["message"])

# Endpoint para login de usuario
@app.post("/login", status_code=status.HTTP_200_OK, responses={ #Lista de respostas possíveis para o endpoint, com seus respectivos códigos de status e descrições.
        401: {"description": "E-mail ou senha inválidos."},
        403: {"description": "Usuário inativo."},
        422: {"description": "Dados de login inválidos ou ausentes."},
        500: {"description": "Erro interno inesperado."}
    })

@app.get("/teste-coordenador")
def teste_coordenador(
    usuario=Depends(verificar_coordenador)):
    return {
        "mensagem": "Você é coordenador"
    }

async def login_route(formulario: OAuth2PasswordRequestForm = Depends()):
    email = formulario.username
    senha = formulario.password

    usuario_banco = buscar_usuario_por_email(email)
    if not usuario_banco["success"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"}
        )

    dados_usuario = usuario_banco["usuario"]
    senha_valida = verificar_senha(senha, dados_usuario["senha_hash"])

    if not senha_valida:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not dados_usuario["ativo"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo. Entre em contato com o suporte."
        )

    token = criar_access_token({"sub": dados_usuario["email"]})
    return {
        "access_token": token,
        "token_type": "bearer"
    }


