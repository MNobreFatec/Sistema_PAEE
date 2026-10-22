"""Testes de integração das funções principais com armazenamento JSON isolado."""
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.routes import app
from backend import armazenamento_json

class TestIntegracaoJSON(unittest.TestCase):
    def setUp(self):
        self.original = armazenamento_json.DATA_FILE
        self.temp_dir = tempfile.TemporaryDirectory()
        armazenamento_json.DATA_FILE = Path(self.temp_dir.name) / 'paee.json'
        self.client = TestClient(app)

    def tearDown(self):
        armazenamento_json.DATA_FILE = self.original
        self.temp_dir.cleanup()

    def test_raiz_redireciona_para_tela_de_login(self):
        response = self.client.get('/', follow_redirects=False)
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers['location'], '/frontend/paginas/login/tela_login.html')

    def test_login_form_e_json_sem_expor_senha(self):
        user = self.client.post('/usuario', json={
            'email': 'aluno@example.com',
            'senha': 'senha-segura-123',
            'nome': 'Aluno Teste',
            'nivel_usuario': 'ALUNO',
        })
        self.assertEqual(user.status_code, 201, user.text)
        self.assertNotIn('senha', user.json())

        with open(armazenamento_json.DATA_FILE, encoding='utf-8') as data_file:
            persisted = data_file.read()
        self.assertNotIn('senha-segura-123', persisted)

        login = self.client.post('/login', data={
            'username': 'aluno@example.com',
            'password': 'senha-segura-123',
        })
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.json()['usuario']['nivel_usuario'], 'ALUNO')
        self.assertEqual(
            self.client.post('/login', data={
                'username': 'aluno@example.com',
                'password': 'senha-incorreta',
            }).status_code,
            401,
        )
        self.assertEqual(self.client.post('/login', json={
            'email': 'aluno@example.com',
            'senha': 'senha-segura-123',
        }).status_code, 200)
        for endpoint in ('alunos', 'professores', 'assistentes', 'coordenadores'):
            response = self.client.get(f'/api/{endpoint}')
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('senha_hash', str(response.json()))
            self.assertNotIn('senha', str(response.json()))

    def test_criacao_de_solicitacao_e_formulario_persistida_em_conjunto(self):
        response = self.client.post('/api/solicitacoes', json={
            'matricula': 456,
            'motivo': 'Solicitação com formulário vinculado',
        })
        self.assertEqual(response.status_code, 201, response.text)
        data = response.json()
        formulario = self.client.get(f'/api/formularios/{data["id_formulario"]}')
        self.assertEqual(formulario.status_code, 200)
        self.assertEqual(formulario.json()['id_solicitacao'], data['id_solicitacao'])

        rows = self.client.get('/api/formularios').json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id_solicitacao'], data['id_solicitacao'])

    def test_favicon_usa_logo_existente(self):
        response = self.client.get('/favicon.ico')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['content-type'], 'image/png')

    def test_login_migra_senha_legada_para_hash(self):
        armazenamento_json.create('usuarios', {
            'email': 'legado@example.com',
            'senha': 'senha-legada-123',
            'nome': 'Usuário legado',
            'nivel_usuario': 'ALUNO',
            'ativo': True,
        }, 'id_usuario')

        response = self.client.post('/login', data={
            'username': 'legado@example.com',
            'password': 'senha-legada-123',
        })
        self.assertEqual(response.status_code, 200, response.text)
        with open(armazenamento_json.DATA_FILE, encoding='utf-8') as data_file:
            persisted = data_file.read()
        self.assertNotIn('"senha":', persisted)
        self.assertIn('"senha_hash":', persisted)

    def test_fluxo_solicitacao_formulario_assinaturas_aprovacao(self):
        self.assertEqual(self.client.get('/api/solicitacoes').json(), [])
        response = self.client.post('/api/solicitacoes', json={'matricula': 123, 'motivo': 'Acompanhamento solicitado'})
        self.assertEqual(response.status_code, 201, response.text)
        data = response.json(); sid=data['id_solicitacao']; fid=data['id_formulario']
        self.assertEqual(self.client.get(f'/api/solicitacoes/{sid}').status_code, 200)
        self.assertEqual(self.client.put(f'/api/formularios/{fid}/secoes/objetivo', json={'conteudo':'Plano de acompanhamento'}).status_code, 200)
        for role in ('ALUNO','PROFESSOR','COORDENADOR'):
            self.assertEqual(self.client.post(f'/api/formularios/{fid}/assinar', json={'papel':role}).status_code, 201)
        form = self.client.get(f'/api/formularios/{fid}').json()
        self.assertEqual(form['status'], 'AGUARDANDO_ASSINATURAS')
        self.assertEqual(len(form['assinaturas']), 3)
        self.assertEqual(self.client.post(f'/api/formularios/{fid}/aprovar').status_code, 200)
        self.assertEqual(self.client.get(f'/api/formularios/{fid}').json()['status'], 'APROVADO')
        self.assertEqual(self.client.post(f'/api/formularios/{fid}/aprovar').status_code, 409)
        self.assertEqual(
            self.client.put(f'/api/formularios/{fid}/secoes/objetivo', json={'conteudo':'Alteração após aprovação'}).status_code,
            409,
        )
        self.assertEqual(
            self.client.post(f'/api/formularios/{fid}/assinar', json={'papel':'ASSISTENTE'}).status_code,
            409,
        )
        self.assertEqual(self.client.patch(f'/api/solicitacoes/{sid}/status', json={'status':'EM_ANALISE'}).status_code, 200)
        self.assertEqual(len(self.client.get('/api/historico/123').json()), 1)

    def test_feedback_relatorio_usuario_designacao(self):
        self.assertEqual(self.client.post('/api/feedback', json={'nome':'Teste','email':'teste@example.com','assunto':'Sugestão','avaliacao':5,'comentario':'Comentário'}).status_code, 201)
        self.assertEqual(self.client.post('/api/relatorios', json={'id_aluno':123,'data_relatorio':'2026-10-21','descricao':'Relatório de teste','observacao':'Observação'}).status_code, 201)
        user=self.client.post('/usuario', json={'email':'assistente@example.com','senha':'senha1234','nome':'Assistente','nivel_usuario':'ASSISTENTE'})
        self.assertEqual(user.status_code, 201, user.text)
        response=self.client.post('/api/designacoes', json={'matricula':123,'id_assistente':user.json()['id_usuario'],'data_inicio':'2026-10-21','data_fim':None})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(len(self.client.get('/api/relatorios').json()), 1)
        self.assertEqual(len(self.client.get('/api/designacoes').json()), 1)

    def test_designacao_recusa_usuario_que_nao_seja_assistente(self):
        user = self.client.post('/usuario', json={
            'email': 'professor@example.com',
            'senha': 'senha-segura-123',
            'nome': 'Professor Teste',
            'nivel_usuario': 'PROFESSOR',
        })
        self.assertEqual(user.status_code, 201, user.text)
        response = self.client.post('/api/designacoes', json={
            'matricula': 123,
            'id_assistente': user.json()['id_usuario'],
            'data_inicio': '2026-10-21',
        })
        self.assertEqual(response.status_code, 422, response.text)

if __name__ == '__main__': unittest.main(verbosity=2)
