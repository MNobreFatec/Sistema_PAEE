"""Consultas parametrizadas para as tabelas presentes no DER atual."""
from contextlib import closing

from backend.database import conectar


class DatabaseUnavailable(RuntimeError):
    """O banco não pôde atender uma operação da API."""


def _as_dict(cursor, row):
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    return {
        description[0]: value
        for description, value in zip(cursor.description, row)
    }


def _fetch_one(query: str, params: tuple = ()):
    try:
        with closing(conectar()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return _as_dict(cursor, cursor.fetchone())
    except Exception as exc:
        raise DatabaseUnavailable("Banco de dados indisponível.") from exc


def _fetch_all(query: str, params: tuple = ()):
    try:
        with closing(conectar()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return [_as_dict(cursor, row) for row in cursor.fetchall()]
    except Exception as exc:
        raise DatabaseUnavailable("Banco de dados indisponível.") from exc


def _execute_returning(query: str, params: tuple = ()):
    try:
        with closing(conectar()) as connection:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, params)
                    return _as_dict(cursor, cursor.fetchone())
    except Exception as exc:
        raise DatabaseUnavailable("Banco de dados indisponível.") from exc


def _execute(query: str, params: tuple = ()) -> bool:
    try:
        with closing(conectar()) as connection:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, params)
                    return cursor.rowcount > 0
    except Exception as exc:
        raise DatabaseUnavailable("Banco de dados indisponível.") from exc


_USUARIO_QUERY = """
    SELECT u.id_usuario, u.email, u.senha_hash, u.id_tipo_usuario, u.ativo,
           t.descricao AS nivel_usuario
    FROM usuario AS u
    JOIN tipo_usuario AS t ON t.id_tipo_usuario = u.id_tipo_usuario
"""


def obter_usuario_por_email(email: str):
    return _fetch_one(
        _USUARIO_QUERY + " WHERE LOWER(u.email) = LOWER(%s)",
        (email,),
    )


def obter_usuario_por_id(id_usuario: int):
    return _fetch_one(_USUARIO_QUERY + " WHERE u.id_usuario = %s", (id_usuario,))


def listar_tipos_usuario():
    return _fetch_all(
        "SELECT id_tipo_usuario, descricao FROM tipo_usuario "
        "ORDER BY id_tipo_usuario"
    )


_PERFIL_QUERIES = {
    "ALUNO": (
        "SELECT matricula, nome, curso, periodo FROM aluno WHERE id_usuario = %s"
    ),
    "PROFESSOR": (
        "SELECT id_professor, nome FROM professor WHERE id_usuario = %s"
    ),
    "ASSISTENTE": (
        "SELECT id_assistente, cnpj_emp, nome_emp, nome_assist, especialidade "
        "FROM assistente WHERE id_usuario = %s"
    ),
    "COORDENADOR": (
        "SELECT id_coordenador, nome, curso FROM coordenador WHERE id_usuario = %s"
    ),
}


def obter_perfil_usuario(id_usuario: int, nivel_usuario: str):
    query = _PERFIL_QUERIES.get(nivel_usuario.upper())
    if query is None:
        return None
    return _fetch_one(query, (id_usuario,))


def listar_telefones(id_usuario: int):
    return _fetch_all(
        "SELECT id_tel, id_usuario, numero_tel FROM telefone "
        "WHERE id_usuario = %s ORDER BY id_tel",
        (id_usuario,),
    )


def criar_telefone(id_usuario: int, numero_tel: int):
    return _execute_returning(
        """
        INSERT INTO telefone (id_usuario, numero_tel)
        VALUES (%s, %s)
        RETURNING id_tel, id_usuario, numero_tel
        """,
        (id_usuario, numero_tel),
    )


def remover_telefone(id_usuario: int, id_tel: int) -> bool:
    return _execute(
        "DELETE FROM telefone WHERE id_usuario = %s AND id_tel = %s",
        (id_usuario, id_tel),
    )
