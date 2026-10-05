from backend.database import conectar
from backend.models import UsuarioCreate
from backend.seguranca import gerar_hash


#Função base para criar usuário, independente do tipo de usuário
def criar_usuario_base(usuario: UsuarioCreate):
    senha_hash = gerar_hash(usuario.senha)
    conexao = None
    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO usuario (email, senha_hash, id_tipo_usuario)
                       VALUES (%s, %s, %s)
                       RETURNING id_usuario, id_tipo_usuario""",
                    (usuario.email, senha_hash, usuario.id_tipo_usuario)
                )

                resultado = cursor.fetchone()
                if resultado is None:
                    raise RuntimeError("Não foi possível recuperar os dados do usuário cadastrado")
                id_usuario, id_tipo_usuario = resultado

            conexao.commit()
            return {
                "success": True,
                "message": "Usuário cadastrado com sucesso",
                "usuario": {
                    "id_usuario": id_usuario,
                    "id_tipo_usuario": id_tipo_usuario
                }
            }
    except Exception as error:
        if conexao is not None:
            conexao.rollback()
            return {
                "success": False,
                "message": f"Erro ao cadastrar usuário: {error}",
                "type": type(error).__name__
            }
        return {
            "success": False,
            "message": f"Erro ao conectar ao banco de dados: {error}",
            "type": type(error).__name__
        }

#Função para criar usuário, verificando o tipo de usuário e chamando a função base
def criar_usuario(usuario: UsuarioCreate):
    if usuario.id_tipo_usuario == 1: #Caso aluno 
        usuario_base = criar_usuario_base(usuario)
        conection = None
        try:
            with conectar() as conection:
                with conection.cursor() as cursor:
                    cursor.execute(
                        """INSERT INTO aluno (id_usuario, matricula, nome, curso, periodo) VALUES (%s, %s, %s, %s, %s)""",
                        (usuario_base["usuario"]["id_usuario"], usuario.matricula, usuario.nome, usuario.curso, usuario.periodo)
                    )
                    cursor.execute(
                        """INSERT INTO telefone (id_usuario, numero_tel) VALUES (%s, %s)""",
                        (usuario_base["usuario"]["id_usuario"], usuario.tel_num)
                    )
                conection.commit()
                return {
                    "success": True,
                    "message": "Aluno cadastrado com sucesso",
                    "usuario": {
                        "nome_aluno": usuario.nome,
                        "id_tipo_usuario": usuario_base["usuario"]["id_tipo_usuario"]
                    }
                }
        except Exception as error:
            if conection is not None:
                conection.rollback()
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
    elif usuario.id_tipo_usuario == 2: #Caso professor
        usuario_base = criar_usuario_base(usuario)
        conection = None 
        try:
            with conectar() as conection:
                with conection.cursor() as cursor:
                    cursor.execute(
                        """INSERT INTO professor (id_usuario, nome) VALUES (%s, %s)""",
                        (usuario_base["usuario"]["id_usuario"], usuario.nome)
                    )
                conection.commit()
                return {
                    "success": True,
                    "message": f"Professor {usuario.nome} cadastrado com sucesso",
                    "usuario": {
                        "id_tipo_usuario": usuario_base["usuario"]["id_tipo_usuario"]
                    }
                }
        except Exception as error:
            if conection is not None:
                conection.rollback()
                return {
                    "success": False,
                    "message": f"Erro ao cadastrar professor: {error}",
                    "type": type(error).__name__
                }
            return {
                "success": False,
                "message": f"Erro ao conectar ao banco de dados: {error}",
                "type": type(error).__name__
            }
    elif usuario.id_tipo_usuario == 3: #Caso assistente
        usuario_base = criar_usuario_base(usuario)
        conection = None
        try:
            with conectar() as conection:
                with conection.cursor() as cursor:
                    cursor.execute(
                        """INSERT INTO assistente (id_usuario, cnpj_emp, nome_emp, nome, especialidade) VALUES (%s, %s, %s, %s, %s)""",
                        (usuario_base["usuario"]["id_usuario"], usuario.cnpj_emp, usuario.nome_emp, usuario.nome, usuario.especialidade)
                    )
                    cursor.execute(
                        """INSERT INTO telefone (id_usuario, numero_tel) VALUES (%s, %s)""",
                        (usuario_base["usuario"]["id_usuario"], usuario.tel_num)
                    )
                conection.commit()
                return {
                    "success": True,
                    "message": f"Assistente {usuario.nome} cadastrado com sucesso",
                    "usuario": {
                        "id_tipo_usuario": usuario_base["usuario"]["id_tipo_usuario"]
                    }
                }
        except Exception as error:
            if conection is not None:
                conection.rollback()
                return {
                    "success": False,
                    "message": f"Erro ao cadastrar assistente: {error}",
                    "type": type(error).__name__
                }
            return {
                "success": False,
                "message": f"Erro ao conectar ao banco de dados: {error}",
                "type": type(error).__name__
            }
    elif usuario.id_tipo_usuario == 4: #Caso coordenador
        usuario_base = criar_usuario_base(usuario)
        conection = None
        try:
            with conectar() as conection:
                with conection.cursor() as cursor:
                    cursor.execute(
                        """INSERT INTO coordenador (id_usuario, nome, curso) VALUES (%s, %s, %s)""",
                        (usuario_base["usuario"]["id_usuario"], usuario.nome, usuario.curso)
                    )
                conection.commit()
                return {
                    "success": True,
                    "message": f"Coordenador {usuario.nome} cadastrado com sucesso",
                    "usuario": {
                        "id_tipo_usuario": usuario_base["usuario"]["id_tipo_usuario"]
                    }
                }
        except Exception as error:
            if conection is not None:
                conection.rollback()
                return {
                    "success": False,
                    "message": f"Erro ao cadastrar coordenador: {error}",
                    "type": type(error).__name__
                }
            return {
                "success": False,
                "message": f"Erro ao conectar ao banco de dados: {error}",
                "type": type(error).__name__
            }
    else:
        return {
            "success": False,
            "message": f"Tipo de usuário inválido: {usuario.id_tipo_usuario}"
        }

#Função utilizada no login
def buscar_usuario_por_email(email: str):
    conexao = None
    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(
                    """SELECT u.id_usuario, u.email, u.senha_hash, u.id_tipo_usuario, u.ativo,
                              tu.descricao
                       FROM usuario AS u
                       INNER JOIN tipo_usuario AS tu
                           ON u.id_tipo_usuario = tu.id_tipo_usuario
                       WHERE u.email = %s""",
                    (email,)
                )
                resultado = cursor.fetchone()
                if resultado:
                    return {
                        "success": True,
                        "message": "Usuario encontrado com sucesso",
                        "aluno": {
                            "id_usuario": resultado[0],
                            "email": resultado[1],
                            "senha_hash": resultado[2],
                            "ativo": resultado[3],
                            "descricao_tipo_usuario": resultado[4]
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