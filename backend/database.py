import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def conectar():
    """
    Cria e retorna uma conexão com o banco de dados PostgreSQL
    utilizando as credenciais definidas no arquivo .env.
    """
    return psycopg2.connect(
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )