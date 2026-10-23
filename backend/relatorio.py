from backend.database import conectar
from backend.models import RelatorioCreate

def buscar_id_assistente(id_usuario: int):
    conexao = None

    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                 cursor.execute(
                    """
                    SELECT id_assistente
                    FROM assistente
                    WHERE id_usuario = %s
                    """,
                    (id_usuario,)
                 )
          
            resultado = cursor.fetchone()

            if(resultado):
                return resultado[0]

            return None

    except Exception as error:
        print(error)
        return None

def buscar_dados_aluno(matricula: str):
    pass      

def criar_relatorio(
        relatorio: RelatorioCreate,
        usuario):
    conexao = None

    id_assistente = buscar_id_assistente(
        usuario['id_usuario']
    )

    if id_assistente is None:
        return{
            "sucess": False,
            "message": "Assistente não encontrado"
        }

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