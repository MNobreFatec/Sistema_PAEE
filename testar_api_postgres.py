"""Testes offline dos contratos da API PostgreSQL, sem conexão remota."""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api import router as api
from backend.repositories import postgres as repository
from backend.repositories.postgres import DatabaseUnavailable
from backend.routes import app
from backend.services import postgres_api
import bcrypt


class FakeCursor:
    def __init__(self):
        self.query = None
        self.params = None
        self.rowcount = 1
        self.description = [("matricula",), ("nome",), ("curso",), ("periodo",)]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=()):
        self.query = query
        self.params = params

    def fetchone(self):
        return (123, "Aluno", "Curso", "1º")

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.fake_cursor

    def close(self):
        self.closed = True


class TestApiPostgres(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.usuario = {
            "id_usuario": 17,
            "email": "aluno@example.com",
            "nivel_usuario": "ALUNO",
            "ativo": True,
            "senha_hash": "hash-privado",
        }
        app.dependency_overrides[api.obter_usuario_atual] = lambda: self.usuario

    def tearDown(self):
        app.dependency_overrides.pop(api.obter_usuario_atual, None)

    def test_usuario_logado_nao_retorna_hash_da_senha(self):
        response = self.client.get("/api/v1/usuarios/me")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {
            "id_usuario": 17,
            "email": "aluno@example.com",
            "nivel_usuario": "ALUNO",
            "ativo": True,
        })
        self.assertNotIn("senha_hash", response.text)

    def test_telefone_e_criado_para_usuario_autenticado(self):
        with patch.object(
            api.postgres,
            "criar_telefone",
            return_value={"id_tel": 8, "id_usuario": 17, "numero_tel": 55119999},
        ) as create_phone:
            response = self.client.post(
                "/api/v1/telefones",
                json={"numero_tel": 55119999, "id_usuario": 999},
            )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["id_usuario"], 17)
        create_phone.assert_called_once_with(17, 55119999)

    def test_numero_de_telefone_invalido_e_rejeitado(self):
        with patch.object(api.postgres, "criar_telefone") as create_phone:
            response = self.client.post(
                "/api/v1/telefones",
                json={"numero_tel": 0},
            )

        self.assertEqual(response.status_code, 422)
        create_phone.assert_not_called()

    def test_rota_de_tipos_mapeia_indisponibilidade_sem_detalhes_do_banco(self):
        with patch.object(
            api.postgres,
            "listar_tipos_usuario",
            side_effect=DatabaseUnavailable("detalhe interno não deve ser exposto"),
        ):
            response = self.client.get("/api/v1/tipos-usuario")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Banco de dados indisponível.")
        self.assertNotIn("detalhe interno", response.text)

    def test_rotas_protegidas_exigem_token(self):
        app.dependency_overrides.pop(api.obter_usuario_atual, None)
        response = self.client.get("/api/v1/usuarios/me")

        self.assertEqual(response.status_code, 401)

    def test_login_autentica_hash_e_nao_devolve_senha(self):
        stored_user = {
            **self.usuario,
            "senha_hash": bcrypt.hashpw(
                b"local-test-password",
                bcrypt.gensalt(),
            ).decode("utf-8"),
        }
        with (
            patch.object(
                postgres_api.postgres,
                "obter_usuario_por_email",
                return_value=stored_user,
            ),
            patch.object(postgres_api, "criar_access_token", return_value="token-teste"),
        ):
            response = self.client.post(
                "/api/v1/auth/login",
                json={"email": "aluno@example.com", "senha": "local-test-password"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["access_token"], "token-teste")
        self.assertNotIn("senha_hash", response.text)

    def test_login_invalido_nao_emite_token(self):
        stored_user = {
            **self.usuario,
            "senha_hash": bcrypt.hashpw(
                b"local-test-password",
                bcrypt.gensalt(),
            ).decode("utf-8"),
        }
        with patch.object(
            postgres_api.postgres,
            "obter_usuario_por_email",
            return_value=stored_user,
        ):
            response = self.client.post(
                "/api/v1/auth/login",
                json={"email": "aluno@example.com", "senha": "wrong-password"},
            )

        self.assertEqual(response.status_code, 401)

    def test_repositorio_usa_tabela_de_perfil_fixa_e_parametriza_usuario(self):
        connection = FakeConnection()
        with patch.object(repository, "conectar", return_value=connection):
            profile = repository.obter_perfil_usuario(17, "ALUNO")

        self.assertEqual(profile, {
            "matricula": 123,
            "nome": "Aluno",
            "curso": "Curso",
            "periodo": "1º",
        })
        self.assertIn("FROM aluno WHERE id_usuario = %s", connection.fake_cursor.query)
        self.assertEqual(connection.fake_cursor.params, (17,))
        self.assertTrue(connection.closed)

    def test_exclusao_de_telefone_e_limitada_ao_proprietario(self):
        connection = FakeConnection()
        with patch.object(repository, "conectar", return_value=connection):
            deleted = repository.remover_telefone(17, 8)

        self.assertTrue(deleted)
        self.assertIn("WHERE id_usuario = %s AND id_tel = %s", connection.fake_cursor.query)
        self.assertEqual(connection.fake_cursor.params, (17, 8))
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
