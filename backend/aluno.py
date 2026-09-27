from database import conectar
from models import AlunoCreate

def criar_aluno(aluno: AlunoCreate):
    conexao = None
    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO aluno (rm, nome, endereco, tel_aluno, email) VALUES (%s, %s, %s, %s, %s)""",
                    (aluno.rm, aluno.nome, aluno.endereco, aluno.tel_aluno, aluno.email)
                )
                conexao.commit()
                return {
                    "success": True,
                    "message": "Aluno cadastrado com sucesso",
                    "data": {
                        "rm": aluno.rm,
                        "nome": aluno.nome
                    }
                }
    except Exception as error:
        if conexao is not None:
            conexao.rollback()
            return {
                "success": False,
                "message": f"Erro ao cadastrar aluno: {error}",
                "type": type(error).__name__
            }
        return {
            "success": False,
            "message": f"Erro ao conectar ao banco de dados: {error}",
            "type": type(error).__name__
        }