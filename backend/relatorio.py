from backend.database import conectar
from backend.models import RelatorioCreate

def criar_relatorio(relatorio: RelatorioCreate):
    conexao = None

    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                pass

    except Exception as error:
        if(conexao is not None):
            conexao.rollback()

            return{
                "success": False,
                "message": f"Erro ao conectar ao banco de dados: {error}",
                "type": type(error).__name__
            }