from datetime import datetime, timedelta, timezone #datetime é para colocar uma validade no token, timedelta é para definir o tempo de expiração do token e timezone é para definir o fuso horário.
from jose import JWTError, jwt  # type: ignore[reportMissingModuleSource]  # importa a biblioteca que cria e lê tokens e verifica a assinatura
from fastapi.security import OAuth2PasswordBearer #importa a classe que cria o esquema de autenticação OAuth2 com senha e token.
from fastapi import Depends, HTTPException, status

from backend.routes.aluno import buscar_aluno_por_email

SECRET_KEY = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6" #chave secreta para assinar o token, deve ser mantida em segredo e não compartilhada publicamente.

ALGORITHM = "HS256" #algoritmo de assinatura do token, neste caso é o HMAC com SHA-256.

ACCESS_TOKEN_EXPIRE_MINUTES = 60 #tempo de expiração do token em minutos, neste caso é 60 minutos.

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login") #cria o esquema de autenticação OAuth2 com senha e token, onde o token é obtido através do endpoint /login.

# Função para criar um token de acesso (access token) com base nos dados fornecidos.
def criar_access_token(data: dict) -> str: #Type hint

    dados_token = data.copy() #copia os dados do dicionário para não alterar o original.
    expiracao = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES) #define a data de expiração do token, somando o tempo de expiração definido com a data atual.
    dados_token.update({"exp": expiracao}) #adiciona a data de expiração ao dicionário de dados do token.

    token = jwt.encode(dados_token, SECRET_KEY, algorithm=ALGORITHM) #gera o token usando a função encode da biblioteca jose, passando os dados do token, a chave secreta e o algoritmo de assinatura.
    return token #retorna o token gerado.

# Função para obter o usuário atual a partir do token de acesso fornecido.
async def obter_usuario_atual(token: str = Depends(oauth2_scheme)):

    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"}
    )

    try:
        print("\n--- INÍCIO DA AUTENTICAÇÃO ---")
        print("Token recebido:", token)

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        print("Token decodificado com sucesso.")
        print("Payload:", payload)

        email = payload.get("sub")

        print("Email extraído do token:", email)

        if email is None:
            print("ERRO: O campo 'sub' não existe no token.")
            raise credenciais_invalidas

        aluno = buscar_aluno_por_email(email)

        print("Resultado da busca do aluno:", aluno)

        if not aluno["success"]:
            print("ERRO: Aluno não encontrado ou consulta retornou erro.")
            raise credenciais_invalidas

        print("Aluno autenticado com sucesso.")
        print("Dados do aluno:", aluno["aluno"])
        print("--- FIM DA AUTENTICAÇÃO ---\n")

        return aluno["aluno"]

    except JWTError as error:
        print("ERRO JWT:", error)
        print("--- FIM DA AUTENTICAÇÃO ---\n")
        raise credenciais_invalidas

def verificar_administrador(aluno = Depends(obter_usuario_atual)):
    if aluno["nivel"] != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não possui permissão para executar esta operação."
        )
    return aluno