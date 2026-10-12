from backend.database import conectar
from backend.models import RelatorioCreate

def criar_relatorio(relatorio: RelatorioCreate):
    conexao = None

    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                #INSERT SERA COLOCADO AQUI FUTURAMENTE
                pass

            conexao.commit()

            return{
                "success": True,
                "message": "Relatório criado com sucesso",
                "relatorio":{
                    "id_aluno": relatorio.id_aluno,
                    "data_relatorio": relatorio.data_relatorio,
                    "descricao": relatorio.descricao,
                    "observacao": relatorio.observacao
                }
            }

    except Exception as error:
        if(conexao is not None):
            conexao.rollback()

            return{
                "success": False,
                "message": f"Erro ao cadastrar relatório: {error}",
                "type": type(error).__name__
            }


        return{
            "success": False,
            "message": f"Erro ao conectar ao banco de dados: {error}",
            "type": type(error).__name__
        }