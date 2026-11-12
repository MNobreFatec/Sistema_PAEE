"""Testes HTTP offline: JSON temporário, credenciais sintéticas e sem PostgreSQL."""
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

import bcrypt
from fastapi.testclient import TestClient

from backend import armazenamento_json
from backend.core.security import gerar_hash
from backend.routes import app
import backend.routes as routes


SAFE_TEST_PASSWORD = "Local-Test-Password-Only-2026!"
FIXTURE_PASSWORD = "LocalTestOnly-Placeholder-2026!"


class TestIntegracaoJSON(unittest.TestCase):
    def setUp(self):
        self.original_data = armazenamento_json.DATA_FILE
        self.original_storage = routes.PRIVATE_STORAGE
        self.original_secret = os.environ.get("SECRET_KEY")
        self.original_paee_environment = os.environ.get("PAEE_ENVIRONMENT")
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        armazenamento_json.DATA_FILE = base / "paee-test.json"
        routes.PRIVATE_STORAGE = base / "private"
        os.environ["SECRET_KEY"] = "offline-test-key-not-for-production-2026"
        os.environ["PAEE_ENVIRONMENT"] = "test"
        self.client = TestClient(app)
        self.users = {
            "coord": self.create_user("coordenacao.teste@example.invalid", "COORDENADOR"),
            "assistant": self.create_user(
                "assistente.teste@example.invalid", "ASSISTENTE"
            ),
            "student": self.create_user(
                "aluno.um@example.invalid", "ALUNO", matricula="TEST-001"
            ),
            "other_student": self.create_user(
                "aluno.dois@example.invalid", "ALUNO", matricula="TEST-002"
            ),
            "other_assistant": self.create_user(
                "assistente.dois@example.invalid", "ASSISTENTE"
            ),
        }
        self.tokens = {}
        for key, user in self.users.items():
            response = self.client.post("/login", json={
                "email": user["email"],
                "senha": SAFE_TEST_PASSWORD,
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.tokens[key] = response.json()["access_token"]

    def tearDown(self):
        self.client.close()
        armazenamento_json.DATA_FILE = self.original_data
        routes.PRIVATE_STORAGE = self.original_storage
        if self.original_secret is None:
            os.environ.pop("SECRET_KEY", None)
        else:
            os.environ["SECRET_KEY"] = self.original_secret
        if self.original_paee_environment is None:
            os.environ.pop("PAEE_ENVIRONMENT", None)
        else:
            os.environ["PAEE_ENVIRONMENT"] = self.original_paee_environment
        self.temp_dir.cleanup()

    def create_user(self, email, role, **profile):
        if role == "ALUNO":
            profile.setdefault("categoria_deficiencia", "CEGO")
        return armazenamento_json.create("usuarios", {
            "email": email,
            "nome": f"Usuário sintético {role}",
            "nivel_usuario": role,
            "senha_hash": gerar_hash(SAFE_TEST_PASSWORD),
            "ativo": True,
            **profile,
        }, "id_usuario")

    def auth(self, key):
        return {"Authorization": f"Bearer {self.tokens[key]}"}

    def assign_student(self, student_key="student", assistant_key="assistant"):
        response = self.client.post("/api/designacoes", headers=self.auth("coord"), json={
            "matricula": self.users[student_key]["matricula"],
            "id_assistente": self.users[assistant_key]["id_usuario"],
            "data_inicio": date.today().isoformat(),
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def create_request(self, student_key="student"):
        response = self.client.post(
            "/api/solicitacoes",
            headers=self.auth(student_key),
            json={
                "matricula": "TENTATIVA-DE-ALTERAR",
                "motivo": "Solicitação sintética de teste",
                "categoria_deficiencia": "AUTISMO",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_api_exige_login_e_login_usa_hash(self):
        self.assertEqual(self.client.get("/api/usuarios").status_code, 401)
        self.assertEqual(
            self.client.get("/login", follow_redirects=False).headers["location"],
            "/frontend/paginas/login/tela_login.html",
        )
        self.assertEqual(
            self.client.get("/menu", follow_redirects=False).headers["location"],
            "/frontend/paginas/tela_inicial.html",
        )
        wrong = self.client.post("/login", json={
            "email": self.users["student"]["email"],
            "senha": "Senha-incorreta-sintetica",
        })
        self.assertEqual(wrong.status_code, 401)
        response = self.client.get("/api/me", headers=self.auth("student"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["nivel_usuario"], "ALUNO")
        self.assertNotIn("senha_hash", response.json())
        raw = armazenamento_json.DATA_FILE.read_text(encoding="utf-8")
        self.assertNotIn(SAFE_TEST_PASSWORD, raw)
        self.assertIn('"senha_hash"', raw)

    def test_senha_legada_sintetica_e_trocada_por_hash_no_primeiro_login(self):
        user = armazenamento_json.create("usuarios", {
            "email": "legado.sintetico@example.invalid",
            "nome": "Conta legada sintética",
            "nivel_usuario": "ALUNO",
            "matricula": "LEG-001",
            "senha": SAFE_TEST_PASSWORD,
            "ativo": True,
        }, "id_usuario")
        response = self.client.post("/login", json={
            "email": user["email"],
            "senha": SAFE_TEST_PASSWORD,
        })
        self.assertEqual(response.status_code, 200)
        stored = armazenamento_json.get("usuarios", "id_usuario", user["id_usuario"])
        self.assertNotIn("senha", stored)
        self.assertTrue(stored["senha_hash"].startswith("$2b$"))
        self.assertNotIn(SAFE_TEST_PASSWORD, armazenamento_json.DATA_FILE.read_text(encoding="utf-8"))

    def test_aluno_cria_chamado_proprio_e_nao_acessa_outro(self):
        own = self.create_request()
        self.assertEqual(own["matricula"], "TEST-001")
        self.assertEqual(own["categoria_deficiencia"], "CEGO")
        self.assertEqual(own["criado_por"], self.users["student"]["id_usuario"])
        self.assertEqual(
            self.client.get("/api/solicitacoes", headers=self.auth("other_student")).json(),
            [],
        )
        self.assertEqual(
            self.client.get(
                "/api/historico/TEST-002", headers=self.auth("student")
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                "/api/historico/TEST-001", headers=self.auth("student")
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                f"/api/solicitacoes/{own['id_solicitacao']}",
                headers=self.auth("other_student"),
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/solicitacoes/{own['id_solicitacao']}/status",
                headers=self.auth("student"),
                json={"status": "EM_ANALISE"},
            ).status_code,
            403,
        )
        coordinator_rows = self.client.get(
            "/api/solicitacoes", headers=self.auth("coord")
        ).json()
        self.assertEqual(len(coordinator_rows), 1)

    def test_designacao_periodo_e_visibilidade_do_assistente(self):
        self.assign_student()
        request = self.create_request()
        assigned = self.client.get(
            "/api/alunos-designados", headers=self.auth("assistant")
        )
        self.assertEqual(
            [row["matricula"] for row in assigned.json()],
            ["TEST-001"],
        )
        self.assertEqual(
            self.client.get(
                "/api/alunos-designados", headers=self.auth("coord")
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                "/api/solicitacoes", headers=self.auth("assistant")
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                f"/api/solicitacoes/{request['id_solicitacao']}",
                headers=self.auth("assistant"),
            ).status_code,
            403,
        )
        self.assertEqual(
            len(self.client.get("/api/formularios", headers=self.auth("assistant")).json()),
            1,
        )
        self.assertEqual(
            self.client.get("/api/designacoes", headers=self.auth("assistant")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get("/api/formularios", headers=self.auth("student")).status_code,
            403,
        )
        conflict = self.client.post("/api/designacoes", headers=self.auth("coord"), json={
            "matricula": self.users["student"]["matricula"],
            "id_assistente": self.users["other_assistant"]["id_usuario"],
            "data_inicio": date.today().isoformat(),
        })
        self.assertEqual(conflict.status_code, 409)

    def test_gestao_de_usuarios_e_auditoria_somente_coordenacao(self):
        payload = {
            "nome": "Conta sintética criada",
            "email": "novo.usuario@example.invalid",
            "nivel_usuario": "ALUNO",
            "senha": "Outra-Senha-Sintetica-2026!",
            "matricula": "TEST-003",
            "categoria_deficiencia": "INTELECTUAL",
            "tel_num": "5550100004",
        }
        missing_category = {**payload, "categoria_deficiencia": ""}
        self.assertEqual(
            self.client.post(
                "/api/usuarios", headers=self.auth("coord"), json=missing_category
            ).status_code,
            422,
        )
        denied = self.client.post(
            "/api/usuarios", headers=self.auth("student"), json=payload
        )
        self.assertEqual(denied.status_code, 403)
        created = self.client.post(
            "/api/usuarios", headers=self.auth("coord"), json=payload
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertNotIn("senha_hash", created.json())
        self.assertEqual(created.json()["id_tipo_usuario"], 1)
        self.assertEqual(created.json()["categoria_deficiencia"], "INTELECTUAL")
        self.assertEqual(created.json()["tel_num"], payload["tel_num"])
        user_id = created.json()["id_usuario"]
        edited = self.client.patch(
            f"/api/usuarios/{user_id}",
            headers=self.auth("coord"),
            json={"nome": "Nome atualizado", "nivel_usuario": "ASSISTENTE"},
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["nivel_usuario"], "ASSISTENTE")
        self.assertEqual(edited.json()["id_tipo_usuario"], 3)
        self.assertIsNone(edited.json()["categoria_deficiencia"])
        self.assertEqual(
            self.client.post(
                f"/api/usuarios/{user_id}/desativar",
                headers=self.auth("coord"),
            ).status_code,
            200,
        )
        disabled_login = self.client.post("/login", json={
            "email": payload["email"],
            "senha": payload["senha"],
        })
        self.assertEqual(disabled_login.status_code, 401)
        self.assertEqual(
            self.client.post(
                f"/api/usuarios/{user_id}/reativar",
                headers=self.auth("coord"),
            ).status_code,
            200,
        )
        audit = self.client.get("/api/auditoria", headers=self.auth("coord"))
        self.assertEqual(audit.status_code, 200)
        self.assertGreaterEqual(len(audit.json()), 4)
        self.assertEqual(
            self.client.get("/api/auditoria", headers=self.auth("assistant")).status_code,
            403,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/usuarios/{self.users['coord']['id_usuario']}",
                headers=self.auth("coord"),
                json={"nivel_usuario": "ASSISTENTE"},
            ).status_code,
            409,
        )
        raw = armazenamento_json.DATA_FILE.read_text(encoding="utf-8")
        self.assertNotIn(payload["senha"], raw)

    def test_deficiencia_obrigatoria_e_unica_no_cadastro_de_aluno(self):
        payload = {
            "nome": "Aluno sintético",
            "email": "aluno.categoria@example.invalid",
            "nivel_usuario": "ALUNO",
            "senha": "Senha-Sintetica-Categoria-2026!",
            "matricula": "TEST-004",
            "categoria_deficiencia": "AUTISMO",
        }
        created = self.client.post(
            "/api/usuarios", headers=self.auth("coord"), json=payload
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["categoria_deficiencia"], "AUTISMO")
        duplicate = self.client.post(
            "/api/usuarios",
            headers=self.auth("coord"),
            json={**payload, "email": "aluno.duplicado@example.invalid"},
        )
        self.assertEqual(duplicate.status_code, 409)
        invalid = self.client.patch(
            f"/api/usuarios/{created.json()['id_usuario']}",
            headers=self.auth("coord"),
            json={"categoria_deficiencia": "OUTRA"},
        )
        self.assertEqual(invalid.status_code, 422)

    def test_fluxo_de_preenchimento_assinaturas_em_ordem_e_aprovacao(self):
        self.assign_student()
        request = self.create_request()
        form_id = request["id_formulario"]
        section = self.client.put(
            f"/api/formularios/{form_id}/secoes/apoios",
            headers=self.auth("assistant"),
            json={"conteudo": {"estrategias": "apoio sintético"}},
        )
        self.assertEqual(section.status_code, 200, section.text)
        self.assertEqual(
            self.client.get(
                f"/api/formularios/{form_id}/assinaturas",
                headers=self.auth("student"),
            ).status_code,
            403,
        )
        early_signature = self.client.post(
            f"/api/formularios/{form_id}/assinar", headers=self.auth("assistant")
        )
        self.assertEqual(early_signature.status_code, 409)
        coordinator_signature = self.client.post(
            f"/api/formularios/{form_id}/assinar", headers=self.auth("coord")
        )
        self.assertEqual(coordinator_signature.status_code, 201, coordinator_signature.text)
        locked_section = self.client.put(
            f"/api/formularios/{form_id}/secoes/apoios",
            headers=self.auth("assistant"),
            json={"conteudo": "não deve alterar após assinatura"},
        )
        self.assertEqual(locked_section.status_code, 409)
        wrong_assistant = self.client.post(
            f"/api/formularios/{form_id}/assinar",
            headers=self.auth("other_assistant"),
        )
        self.assertEqual(wrong_assistant.status_code, 403)
        assistant_signature = self.client.post(
            f"/api/formularios/{form_id}/assinar",
            headers=self.auth("assistant"),
        )
        self.assertEqual(assistant_signature.status_code, 201)
        self.assertEqual(
            assistant_signature.json()["formulario"]["status"],
            "AGUARDANDO_APROVACAO",
        )
        approval = self.client.post(
            f"/api/formularios/{form_id}/aprovar", headers=self.auth("coord")
        )
        self.assertEqual(approval.status_code, 200)
        self.assertEqual(approval.json()["status"], "APROVADO")
        self.assertEqual(
            self.client.patch(
                f"/api/solicitacoes/{request['id_solicitacao']}/status",
                headers=self.auth("coord"),
                json={"status": "INDEFERIDA"},
            ).status_code,
            422,
        )

    def test_anexo_pdf_privado_pode_ser_substituido_e_baixado_com_autorizacao(self):
        self.assign_student()
        request = self.create_request()
        form_id = request["id_formulario"]
        self.client.put(
            f"/api/formularios/{form_id}/secoes/apoios",
            headers=self.auth("assistant"),
            json={"conteudo": "conteúdo sintético"},
        )
        first = self.client.post(
            f"/api/formularios/{form_id}/anexo",
            headers=self.auth("assistant"),
            files={"arquivo": ("primeiro.pdf", b"%PDF-1.4\nprimeiro", "application/pdf")},
        )
        self.assertEqual(first.status_code, 200, first.text)
        second = self.client.post(
            f"/api/formularios/{form_id}/anexo",
            headers=self.auth("coord"),
            files={"arquivo": ("substituto.pdf", b"%PDF-1.4\nsubstituto", "application/pdf")},
        )
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(len(list(routes.PRIVATE_STORAGE.glob("*.pdf"))), 1)
        download = self.client.get(
            f"/api/formularios/{form_id}/anexo",
            headers=self.auth("student"),
        )
        self.assertEqual(download.status_code, 403)
        coordinator_download = self.client.get(
            f"/api/formularios/{form_id}/anexo",
            headers=self.auth("coord"),
        )
        self.assertEqual(coordinator_download.status_code, 200)
        self.assertEqual(coordinator_download.content, b"%PDF-1.4\nsubstituto")
        self.assertEqual(
            self.client.get(
                f"/api/formularios/{form_id}/anexo",
                headers=self.auth("other_student"),
            ).status_code,
            403,
        )
        invalid = self.client.post(
            f"/api/formularios/{form_id}/anexo",
            headers=self.auth("coord"),
            files={"arquivo": ("not-pdf.pdf", b"nope", "application/pdf")},
        )
        self.assertEqual(invalid.status_code, 422)

    def test_relatorio_exige_assistente_designado_e_campos_da_categoria(self):
        self.assign_student()
        payload = {
            "id_aluno": "TEST-001",
            "data_relatorio": date.today().isoformat(),
            "descricao": "Relatório sintético",
            "materia": "Matemática",
            "avaliacoes": {
                "adaptacao_ambiente": {"nota": 4, "comentario": "ajuste sintético"},
                "ferramentas_auxilio": {"nota": 3, "comentario": ""},
            },
        }
        created = self.client.post(
            "/api/relatorios", headers=self.auth("assistant"), json=payload
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["criado_por"], self.users["assistant"]["id_usuario"])
        self.assertEqual(created.json()["categoria_deficiencia"], "CEGO")
        self.assertEqual(
            self.client.get("/api/relatorios", headers=self.auth("coord")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get("/api/relatorios", headers=self.auth("assistant")).json()[0][
                "categoria_deficiencia"
            ],
            "CEGO",
        )
        categories = {
            "SURDO": {
                "adaptacao_ambiente": {"nota": 5, "comentario": ""},
                "ferramentas_auxilio": {"nota": 4, "comentario": "comentário opcional"},
            },
            "AUTISMO": {
                "socializacao": {"nota": 3, "comentario": ""},
                "integracao_ambiente": {"nota": 2, "comentario": ""},
            },
            "INTELECTUAL": {
                "compreensao_conteudo": {"nota": 2, "comentario": "registro sintético"},
                "comportamento_sala": {"nota": 4, "comentario": ""},
            },
        }
        for category, fields in categories.items():
            student_key = f"student_{category.lower()}"
            matricula = f"TEST-{category[:3]}"
            self.users[student_key] = self.create_user(
                f"aluno.{category.lower()}@example.invalid",
                "ALUNO",
                matricula=matricula,
                categoria_deficiencia=category,
            )
            self.assign_student(student_key=student_key)
            response = self.client.post(
                "/api/relatorios",
                headers=self.auth("assistant"),
                json={
                    **payload,
                    "id_aluno": matricula,
                    "categoria_deficiencia": "CEGO",
                    "avaliacoes": fields,
                    "materia": "Matemática",
                },
            )
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()["categoria_deficiencia"], category)
        invalid = {
            **payload,
            "avaliacoes": {
                "adaptacao_ambiente": {"nota": 6, "comentario": ""},
                "ferramentas_auxilio": {"nota": 3, "comentario": ""},
            },
        }
        self.assertEqual(
            self.client.post(
                "/api/relatorios", headers=self.auth("assistant"), json=invalid
            ).status_code,
            422,
        )
        missing_aspect = {
            **payload,
            "avaliacoes": {
                "adaptacao_ambiente": {"nota": 4, "comentario": ""}
            },
        }
        self.assertEqual(
            self.client.post(
                "/api/relatorios", headers=self.auth("assistant"), json=missing_aspect
            ).status_code,
            422,
        )
        missing_subject = {key: value for key, value in payload.items() if key != "materia"}
        self.assertEqual(
            self.client.post(
                "/api/relatorios", headers=self.auth("assistant"), json=missing_subject
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.get("/api/relatorios", headers=self.auth("student")).status_code,
            403,
        )

    def test_estatisticas_mensais_por_aluno_e_materia_somente_coordenacao(self):
        self.assign_student()
        for subject, scores in (
            ("Matemática", (4, 3)),
            ("Português", (5, 5)),
        ):
            response = self.client.post(
                "/api/relatorios",
                headers=self.auth("assistant"),
                json={
                    "id_aluno": "TEST-001",
                    "data_relatorio": date.today().isoformat(),
                    "materia": subject,
                    "descricao": "Relatório estatístico sintético",
                    "avaliacoes": {
                        "adaptacao_ambiente": {"nota": scores[0], "comentario": ""},
                        "ferramentas_auxilio": {"nota": scores[1], "comentario": ""},
                    },
                },
            )
            self.assertEqual(response.status_code, 201, response.text)

        base = "/api/alunos/TEST-001/estatisticas"
        result = self.client.get(base, headers=self.auth("coord"))
        self.assertEqual(result.status_code, 200, result.text)
        body = result.json()
        self.assertEqual(body["aluno"]["matricula"], "TEST-001")
        self.assertEqual(set(body["materias"]), {"Matemática", "Português"})
        self.assertEqual(len(body["estatisticas_mensais"]), 1)
        monthly = body["estatisticas_mensais"][0]
        self.assertEqual(monthly["quantidade_relatorios"], 2)
        self.assertEqual(monthly["media"], 4.25)
        self.assertEqual(monthly["medias_aspectos"]["adaptacao_ambiente"], 4.5)
        self.assertEqual(monthly["medias_aspectos"]["ferramentas_auxilio"], 4.0)
        filtered = self.client.get(
            f"{base}?materia=Matem%C3%A1tica", headers=self.auth("coord")
        )
        self.assertEqual(filtered.json()["estatisticas_mensais"][0]["media"], 3.5)

        global_stats = self.client.get(
            "/api/relatorios/estatisticas?materia=Portugu%C3%AAs",
            headers=self.auth("coord"),
        )
        self.assertEqual(global_stats.status_code, 200)
        self.assertEqual(global_stats.json()["estatisticas_mensais"][0]["media"], 5.0)
        self.assertEqual(
            self.client.get(base, headers=self.auth("assistant")).status_code, 403
        )
        self.assertEqual(
            self.client.get("/api/relatorios/estatisticas", headers=self.auth("student")).status_code,
            403,
        )
        self.assertEqual(self.client.get(base, headers=self.auth("student")).status_code, 403)
        self.assertEqual(
            self.client.get(
                "/api/alunos/MATRICULA-INEXISTENTE/estatisticas",
                headers=self.auth("coord"),
            ).status_code,
            404,
        )

    def test_feedback_usuarios_podem_enviar_coordenador_so_pode_consultar(self):
        response = self.client.post(
            "/api/feedback",
            headers=self.auth("student"),
            json={
                "nome": "Nome falsificado",
                "email": "nao-e-o-usuario@example.invalid",
                "assunto": "Acessibilidade",
                "avaliacao": 5,
                "comentario": "Comentário de teste sintético",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["email"], self.users["student"]["email"])
        self.assertNotEqual(response.json()["nome"], "Nome falsificado")
        self.assertEqual(
            self.client.get("/api/feedback", headers=self.auth("student")).status_code,
            403,
        )
        self.assertEqual(
            len(self.client.get("/api/feedback", headers=self.auth("coord")).json()), 1
        )
        self.assertEqual(
            self.client.post(
                "/api/feedback",
                headers=self.auth("coord"),
                json={
                    "assunto": "Acessibilidade",
                    "avaliacao": 5,
                    "comentario": "Feedback não deve ser enviado pela coordenação",
                },
            ).status_code,
            403,
        )

    def test_somente_aluno_pode_criar_chamado(self):
        response = self.client.post(
            "/api/solicitacoes",
            headers=self.auth("coord"),
            json={"motivo": "Tentativa de chamado pela coordenação"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self.client.get("/api/solicitacoes", headers=self.auth("coord")).json(),
            [],
        )

    def test_fixture_somente_teste_usa_sinteticos_e_hashes(self):
        fixture_path = Path(__file__).parent / "backend/data/usuarios_teste.local.example.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assertTrue(fixture["_somente_teste_local"])
        self.assertFalse(fixture["_carregado_automaticamente"])
        self.assertTrue(all(user["email"].endswith("@example.invalid") for user in fixture["usuarios"]))
        expected_fields = {
            "email", "senha_hash", "id_tipo_usuario", "matricula", "nome",
            "curso", "periodo", "tel_num",
        }
        self.assertTrue(all(
            expected_fields <= user.keys() for user in fixture["usuarios"]
        ))
        role_ids = {"ALUNO": 1, "PROFESSOR": 2, "ASSISTENTE": 3, "COORDENADOR": 4}
        self.assertTrue(all(
            user["id_tipo_usuario"] == role_ids[user["nivel_usuario"]]
            for user in fixture["usuarios"]
        ))
        self.assertTrue(all(user["senha_hash"].startswith("$2b$") for user in fixture["usuarios"]))
        self.assertTrue(all(user["somente_teste"] is True for user in fixture["usuarios"]))
        self.assertIn("categoria_deficiencia", next(
            user for user in fixture["usuarios"] if user["nivel_usuario"] == "ALUNO"
        ))
        self.assertIn("CEGO", {
            user["categoria_deficiencia"]
            for user in fixture["usuarios"]
            if user["nivel_usuario"] == "ALUNO"
        })
        self.assertTrue(all("senha" not in user for user in fixture["usuarios"]))
        self.assertTrue(all(
            bcrypt.checkpw(FIXTURE_PASSWORD.encode("utf-8"), user["senha_hash"].encode("utf-8"))
            for user in fixture["usuarios"]
        ))

    def test_lista_de_contas_demo_so_existe_em_base_local_sintetica(self):
        fixture_path = Path(__file__).parent / "backend/data/usuarios_teste.local.example.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        armazenamento_json.mutate(
            lambda data: data.update({"usuarios": fixture["usuarios"]})
        )
        response = self.client.get("/api/demo-users")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {user["perfil"] for user in response.json()["usuarios"]},
            {"ALUNO", "ASSISTENTE", "COORDENADOR"},
        )
        self.assertEqual(response.json()["senha_compartilhada"], FIXTURE_PASSWORD)
        self.assertTrue(all("senha_hash" not in user for user in response.json()["usuarios"]))
        os.environ["PAEE_ENVIRONMENT"] = "production"
        self.assertEqual(self.client.get("/api/demo-users").status_code, 404)
        self.assertEqual(
            self.client.get("/api/demo-users").status_code,
            404,
        )

    def test_usuario_marcado_como_fixture_e_rejeitado_fora_do_modo_local(self):
        fixture_path = Path(__file__).parent / "backend/data/usuarios_teste.local.example.json"
        fixture_user = json.loads(fixture_path.read_text(encoding="utf-8"))["usuarios"][0]
        fixture_user["email"] = "loaded-fixture@example.invalid"
        user = armazenamento_json.create("usuarios", fixture_user, "id_usuario")
        os.environ["PAEE_ENVIRONMENT"] = "production"
        denied = self.client.post("/login", json={
            "email": user["email"],
            "senha": FIXTURE_PASSWORD,
        })
        self.assertEqual(denied.status_code, 401)
        os.environ["PAEE_ENVIRONMENT"] = "test"
        permitted = self.client.post("/login", json={
            "email": user["email"],
            "senha": FIXTURE_PASSWORD,
        })
        self.assertEqual(permitted.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
