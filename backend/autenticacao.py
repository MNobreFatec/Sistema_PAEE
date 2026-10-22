from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from dotenv import load_dotenv
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from backend.usuario import buscar_usuario_por_email

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
SECRET_KEY = os.getenv("SECRET_KEY", "chave-local-apenas-para-testes-troque-no-env")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def criar_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

async def obter_usuario_atual(token: str = Depends(oauth2_scheme)):
    erro = HTTPException(status_code=401, detail="Não foi possível validar as credenciais", headers={"WWW-Authenticate":"Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise erro
        resultado = buscar_usuario_por_email(email)
        if not resultado.get("success") or not resultado.get("usuario"):
            raise erro
        usuario = resultado["usuario"]
        if not usuario.get("ativo", True):
            raise HTTPException(status_code=403, detail="Usuário inativo")
        return usuario
    except JWTError:
        raise erro

def _verificar_tipo(usuario, tipo, nome):
    if usuario.get("nivel_usuario") != tipo:
        raise HTTPException(status_code=403, detail=f"Acesso permitido apenas para {nome}")
    return usuario

def verificar_coordenador(usuario=Depends(obter_usuario_atual)): return _verificar_tipo(usuario, 4, "coordenadores")
def verificar_professor(usuario=Depends(obter_usuario_atual)): return _verificar_tipo(usuario, 2, "professores")
def verificar_assistente(usuario=Depends(obter_usuario_atual)): return _verificar_tipo(usuario, 3, "assistentes")
def verificar_aluno(usuario=Depends(obter_usuario_atual)): return _verificar_tipo(usuario, 1, "alunos")
def verificar_administrador(usuario=Depends(obter_usuario_atual)):
    if usuario.get("nivel_usuario") != 4:
        raise HTTPException(status_code=403, detail="Você não possui permissão para executar esta operação.")
    return usuario
