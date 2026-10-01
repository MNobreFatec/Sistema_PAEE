from backend.core.database import conectar
from backend.models.models import AlunoCreate
from backend.core.seguranca import gerar_hash

def criar_aluno(aluno: AlunoCreate):
    aluno.senha = gerar_hash(aluno.senha)  # Gera o hash da senha antes de cadastrá-la
    conexao = None
    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO aluno (rm, nome, endereco, tel, email, senha_hash) VALUES (%s, %s, %s, %s, %s, %s)""",
                    (aluno.rm, aluno.nome, aluno.endereco, aluno.tel, aluno.email, aluno.senha)
                )
                conexao.commit()
                return {
                    "success": True,
                    "message": "Aluno cadastrado com sucesso",
                    "data": {
                        "message": f"Aluno {aluno.nome} foi cadastrado com sucesso {aluno.rm}"
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

def buscar_aluno_por_email(email: str):
    conexao = None
    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(
                    """SELECT * FROM aluno WHERE email = %s""",
                    (email,)
                )
                resultado = cursor.fetchone()
                if resultado:
                    return {
                        "success": True,
                        "message": "Aluno encontrado com sucesso",
                        "aluno": {
                            "rm": resultado[0],
                            "nome": resultado[1],
                            "endereco": resultado[2],
                            "tel": resultado[3],
                            "email": resultado[4],
                            "senha_hash": resultado[5]
                        }
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Aluno com email {email} não encontrado"
                    }
    except Exception as error:
        if conexao is not None:
            conexao.rollback()
            return {
                "success": False,
                "message": f"Erro ao buscar aluno: {error}",
                "type": type(error).__name__
            }
        return {
            "success": False,
            "message": f"Erro ao conectar ao banco de dados: {error}",
            "type": type(error).__name__
        }