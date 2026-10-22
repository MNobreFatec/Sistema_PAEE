"""Executa testes automatizados do PAEE sem conectar ao banco real."""
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Permite testar imports e regras sem instalar/abrir um banco PostgreSQL.
try:
    import psycopg2  # noqa: F401
except ModuleNotFoundError:
    import types
    fake_db = types.ModuleType('psycopg2')
    fake_db.connect = lambda **kwargs: (_ for _ in ()).throw(RuntimeError('Banco não utilizado no teste offline'))
    sys.modules['psycopg2'] = fake_db

try:
    import bcrypt  # noqa: F401
except ModuleNotFoundError:
    import types
    fake_bcrypt = types.ModuleType('bcrypt')
    fake_bcrypt.hashpw = lambda senha, salt: b'teste'
    fake_bcrypt.gensalt = lambda: b'teste'
    fake_bcrypt.checkpw = lambda senha, hash_: False
    sys.modules['bcrypt'] = fake_bcrypt
try:
    from jose import jwt  # noqa: F401
except ModuleNotFoundError:
    import types
    fake_jose = types.ModuleType('jose')
    class JWTError(Exception): pass
    fake_jose.JWTError = JWTError
    fake_jose.jwt = types.SimpleNamespace(encode=lambda payload, key, algorithm: 'token-teste', decode=lambda token, key, algorithms: {})
    sys.modules['jose'] = fake_jose

class TestFuncoesPAEE(unittest.TestCase):
    def test_imports_backend(self):
        import backend.routes, backend.usuario, backend.relatorio, backend.paee_service
        self.assertTrue(backend.routes.app)

    def test_endpoint_health_registrado(self):
        from backend.routes import app
        paths = {r.path for r in app.routes}
        self.assertIn('/', paths)
        self.assertIn('/favicon.ico', paths)
        self.assertIn('/health', paths)
        self.assertIn('/login', paths)
        self.assertIn('/api/solicitacoes', paths)
        self.assertIn('/api/professores', paths)
        self.assertIn('/api/designacoes', paths)
        self.assertIn('/api/formularios/{id_formulario}/assinar', paths)

    def test_transicao_status_permitida(self):
        from backend.paee_service import validar_transicao_status
        self.assertTrue(validar_transicao_status('ABERTA', 'EM_ANALISE'))

    def test_transicao_status_bloqueada(self):
        from backend.paee_service import validar_transicao_status
        with self.assertRaises(ValueError):
            validar_transicao_status('CONCLUIDA', 'ABERTA')

    def test_status_inexistente(self):
        from backend.paee_service import validar_transicao_status
        with self.assertRaises(ValueError):
            validar_transicao_status('NAO_EXISTE', 'ABERTA')

    def test_designacao_datas_validas(self):
        from backend.paee_service import validar_designacao
        self.assertTrue(validar_designacao('2026-01-01', '2026-12-31'))

    def test_designacao_data_invertida(self):
        from backend.paee_service import validar_designacao
        with self.assertRaises(ValueError):
            validar_designacao('2026-12-31', '2026-01-01')

    def test_assinatura_papel_valido(self):
        from backend.paee_service import validar_assinatura
        self.assertTrue(validar_assinatura('COORDENADOR'))

    def test_assinatura_papel_invalido(self):
        from backend.paee_service import validar_assinatura
        with self.assertRaises(ValueError):
            validar_assinatura('VISITANTE')

    def test_secao_obrigatoria(self):
        from backend.paee_service import validar_secao
        with self.assertRaises(ValueError):
            validar_secao('objetivo', '  ')

    def test_secao_preenchida(self):
        from backend.paee_service import validar_secao
        self.assertTrue(validar_secao('objetivo', {'texto': 'Plano de apoio'}))

    def test_paginas_originais_e_novas(self):
        nomes = ['tela_inicial.html', 'dashboard.html', 'lista_chamados.html', 'criar_relatorio.html', 'feedback.html', 'solicitacao_paee.html', 'historico.html', 'designacao_assistente.html', 'assinaturas.html']
        for name in nomes:
            self.assertTrue((ROOT / 'frontend' / 'paginas' / name).is_file(), name)

    def test_links_locais_css_js_imagens(self):
        import re
        for html in (ROOT / 'frontend' / 'paginas').rglob('*.html'):
            source = html.read_text(encoding='utf-8', errors='ignore')
            paths = re.findall(r'''(?:href|src)=["']([^"']+)["']''', source)
            for path in paths:
                if path.startswith(('http://', 'https://', '#', 'data:', 'mailto:', 'javascript:')):
                    continue
                if path.endswith(('.css', '.js', '.png', '.jpg', '.svg')):
                    self.assertTrue((html.parent / path).exists(), f'{html.name}: {path}')

    def test_migration_nao_apaga_tabelas(self):
        sql = (ROOT / 'database/migrations/001_fluxo_paee.sql').read_text(encoding='utf-8').upper()
        self.assertIn('CREATE TABLE IF NOT EXISTS SOLICITACAO_PAEE', sql)
        self.assertNotIn('DROP TABLE', sql)
        formulario = sql.split('CREATE TABLE IF NOT EXISTS FORMULARIO_PAEE', 1)[1].split('CREATE TABLE IF NOT EXISTS', 1)[0]
        self.assertIn("'EM_PREENCHIMENTO'", formulario)

    def test_pagina_inicial_encaminha_para_login(self):
        index = (ROOT / 'frontend/index.html').read_text(encoding='utf-8')
        self.assertIn('paginas/login/tela_login.html', index)

    def test_mensagens_de_login_usam_o_mesmo_painel(self):
        page = (ROOT / 'frontend/paginas/login/tela_login.html').read_text(encoding='utf-8')
        script = (ROOT / 'frontend/paginas/login/script.js').read_text(encoding='utf-8')
        self.assertIn('id="statusText"', page)
        self.assertIn('id="statusMessage"', page)
        self.assertNotIn('id="loginMessage"', page)
        self.assertIn("document.getElementById('statusText').textContent = message", script)
        self.assertIn("document.getElementById('statusMessage').classList.add('hidden')", script)

    def test_dashboard_resumo_visual_tem_dados_dinamicos(self):
        page = (ROOT / 'frontend/paginas/dashboard.html').read_text(encoding='utf-8')
        script = (ROOT / 'frontend/js/dashboard.js').read_text(encoding='utf-8')
        self.assertIn('id="chamadosPorMes"', page)
        self.assertIn('id="statusResumo"', page)
        self.assertIn('<script src="../js/dashboard.js">', page)
        self.assertIn("fetch(`${window.PAEE_API_URL || window.location.origin}/api/solicitacoes`)", script)
        self.assertIn('dashboardChart.innerHTML', script)
        self.assertIn('statusSummary.innerHTML', script)
        self.assertIn('window.carregarResumoVisual = carregarResumoVisual', script)

    def test_dashboard_usa_uma_unica_funcao_de_carregamento(self):
        source = (ROOT / 'frontend/js/telas.js').read_text(encoding='utf-8')
        self.assertNotIn('carregarDashboard', source)
        self.assertIn('window.carregarResumoVisual?.()', source)

    def test_logout_limpa_sessao_da_interface(self):
        source = (ROOT / 'frontend/js/telas.js').read_text(encoding='utf-8')
        self.assertIn("sessionStorage.removeItem('paee_token')", source)
        self.assertIn("sessionStorage.removeItem('paee_usuario')", source)

    def test_formularios_api_impedem_envio_duplicado(self):
        source = (ROOT / 'frontend/js/telas.js').read_text(encoding='utf-8')
        self.assertIn("form.dataset.enviando==='true'", source)
        self.assertEqual(source.count('void executarEnvioUnico('), 6)

    def test_dashboard_nao_exibe_dados_ficticios(self):
        for page in ('tela_inicial.html', 'dashboard.html'):
            content = (ROOT / 'frontend/paginas' / page).read_text(encoding='utf-8')
            self.assertNotIn('Chamado #1042', content)
            self.assertNotIn('44', content)

    def test_fluxos_relatorio_e_formulario_atualizam_interface(self):
        source = (ROOT / 'frontend/js/telas.js').read_text(encoding='utf-8')
        self.assertNotIn('Designa??o registrada.', source)
        self.assertNotIn('Se??o salva.', source)
        self.assertNotIn('Formul?rio aprovado.', source)
        approval = source[source.index("document.getElementById('aprovarFormulario')"):source.index('// Histórico do aluno.')]
        self.assertIn('await carregarFormularios()', approval)
        printing = source[source.index("const imprimirRelatorio="):source.index("document.getElementById('exportarRelatorios')")]
        self.assertLess(printing.index("window.open('','_blank')"), printing.index('await obterRelatorios()'))
        self.assertIn('O navegador bloqueou a janela de impress\\u00e3o.', printing)
        self.assertIn('</script></body></html>', printing)

    def test_status_mostrados_com_rotulos_legiveis(self):
        source = (ROOT / 'frontend/js/telas.js').read_text(encoding='utf-8')
        dashboard = (ROOT / 'frontend/js/dashboard.js').read_text(encoding='utf-8')
        history = source[source.index("// Histórico do aluno."):source.index("// Chamados:")]
        self.assertIn('escapeHtml(statusLabel(r.status))', history)
        self.assertIn("RASCUNHO:'Rascunho'", source)
        self.assertIn("APROVADO:'Aprovado'", source)
        self.assertIn('escapeHtml(statusLabel(f.status))', source)
        self.assertIn("CONCLUIDA: 'Concluída'", dashboard)
        self.assertIn('dashboardEscape(dashboardStatus(row.status))', dashboard)
        self.assertIn('Não foi possível conectar ao servidor.', dashboard)

if __name__ == '__main__':
    unittest.main(verbosity=2)
