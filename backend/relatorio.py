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

            return {"success": False, "message": "Assistente não encontrado"}

    except Exception as error:
        return {"success": False,
                "type": type(error).__name__,
                "message": f"Erro ao buscar assistente: {error}"}

def buscar_dados_aluno(matricula: str):
    conexao = None

    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id_aluno, nome, curso, periodo
                    FROM aluno
                    WHERE matricula = %s
                    """,
                    (matricula,)
                )

            resultado = cursor.fetchone()

            if(resultado):
                return {
                    "success": True,
                    "aluno": {
                        "id_aluno": resultado[0],
                        "nome": resultado[1],
                        "curso": resultado[2],
                        "periodo": resultado[3]
                    }
                }

            return {"success": False, "message": "Aluno não encontrado"}

    except Exception as error:
        return {"success": False,
                "type": type(error).__name__,
                "message": f"Erro ao buscar aluno: {error}"}      

def criar_relatorio(
        relatorio: RelatorioCreate,
        usuario):
    conexao = None

    id_assistente = buscar_id_assistente(
        usuario['id_usuario']
    )
    
    dados_aluno = buscar_dados_aluno(
        relatorio.matricula
    )

    if id_assistente is None:
        return{
            "success": False,
            "message": "Assistente não encontrado"
        }
        
    if not dados_aluno['success']:
        return dados_aluno
    
    curso = dados_aluno['aluno']['curso']
    periodo = dados_aluno['aluno']['periodo']

    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
               cursor.execute(
                """
                    INSERT INTO relatorio (
                    matricula,
                    id_assistente,
                    aluno_curso,
                    aluno_periodo,
                    semana_inicio,
                    segunda,
                    terca,
                    quarta,
                    quinta,
                    sexta,
                    observacoes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    (
                    relatorio.matricula,
                    id_assistente,
                    curso,
                    periodo,
                    relatorio.semana_inicio,
                    relatorio.segunda,
                    relatorio.terca,
                    relatorio.quarta,
                    relatorio.quinta,
                    relatorio.sexta,
                    relatorio.observacoes
            )
                )
)

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