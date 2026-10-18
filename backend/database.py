import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Mantemos a leitura do .env para as outras variáveis (como a SECRET_KEY)
env_path = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path, encoding="utf-8", errors="ignore") as f:
        load_dotenv(stream=f, override=True)


def conectar():
    """
    Cria e retorna uma conexão com o banco de dados PostgreSQL do Supabase.
    Injeta a URL diretamente por segurança contra erros de encoding do arquivo .env.
    """
    # Colocamos a URL diretamente aqui como uma string pura do Python.
    # Isso ignora qualquer erro de codificação ou caractere invisível do arquivo .env!
    database_url = os.getenv("DATABASE_URL")
        
    return psycopg2.connect(dsn=database_url)
