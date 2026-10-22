# PAEE — execução e testes

## 1. Preparar ambiente
1. Use Python 3.11 ou versão compatível com `requirements.txt`.
2. No terminal, na pasta do projeto, execute `python -m venv .venv`.
3. Ative o ambiente e execute `pip install -r requirements.txt` (inclui a dependência usada pelo cliente de testes HTTP).
4. Para o modo temporário com JSON, não configure banco nem `.env`: o sistema cria `backend/data/paee.json` automaticamente e começa vazio.
5. O modo JSON é para testes locais. Não use dados reais/sensíveis e não exponha o servidor à internet.

## 2. Rodar o teste automático
Na pasta raiz, execute `python testar_funcoes.py` e `python testar_integracao_json.py`. O primeiro verifica imports, rotas, regras de status, validações, páginas, caminhos locais e ausência de dados demonstrativos no painel. O segundo executa operações HTTP contra um arquivo JSON temporário isolado, incluindo login, criação de solicitações, formulário, assinaturas, designações, relatórios e feedback. Nenhum teste usa ou apaga o arquivo JSON de desenvolvimento.

Esses testes comprovam o comportamento do modo JSON local, mas não verificam a migration PostgreSQL/Supabase, permissões de produção ou integrações externas.

## 3. Iniciar API e telas
1. Na raiz do projeto, execute `uvicorn backend.routes:app --reload`.
2. Abra `http://127.0.0.1:8000/frontend/`; o endereço redireciona para a tela de login. Também é possível abrir `http://127.0.0.1:8000/frontend/paginas/login/tela_login.html`.
3. API interativa: `http://127.0.0.1:8000/docs`; saúde e modo de armazenamento: `http://127.0.0.1:8000/health` e `http://127.0.0.1:8000/api/status`.
4. Os registros são salvos em `backend/data/paee.json`, compartilhados entre telas e preservados ao reiniciar a API. Faça cópia desse arquivo antes de apagá-lo.

## 4. Limitações conhecidas
- Para entrar no modo JSON, crie um usuário de demonstração em `POST /usuario` pelo `/docs` e use o e-mail e a senha cadastrados na tela de login.
- O banco precisa receber a migration complementar antes de usar solicitação, formulário, designação, assinatura e relatório.
- O arquivo de testes não altera dados do banco e não simula uma conexão remota real.
- Os documentos oficiais das Waves não estão presentes neste repositório; os requisitos detalhados da migration precisam ser comparados com eles antes da integração PostgreSQL.


### Frontend reorganizado

As páginas do fluxo PAEE ficam em `frontend/paginas/`, os estilos em `frontend/css/`, as imagens em `frontend/img/` e o JavaScript compartilhado em `frontend/js/`. Os nomes originais dos arquivos foram mantidos. Depois de iniciar a API, acesse `http://127.0.0.1:8000/frontend/paginas/login/tela_login.html`; após o login, o fluxo abre `frontend/paginas/tela_inicial.html`.

## Armazenamento JSON temporário

O backend usa `backend/armazenamento_json.py` para guardar solicitações, formulários, seções, assinaturas, designações, relatórios, feedbacks e usuários em um único arquivo JSON. O arquivo é criado vazio na primeira execução; não há contas, chamados, métricas ou registros de exemplo pré-carregados. Todas as telas consultam a API e não há fallback silencioso para `localStorage`: se o servidor estiver parado, a interface mostra erro de conexão.

O modo local é destinado exclusivamente a desenvolvimento. Novas senhas são armazenadas com hash bcrypt; senhas em texto puro de arquivos JSON legados são migradas para hash no primeiro login válido. Apesar disso, o token retornado é apenas um identificador local: as rotas não o validam nem impõem autorização por perfil. O cadastro de usuários também não exige autenticação. Portanto, não exponha o servidor à internet e não use dados pessoais reais. Antes de produção, conecte as rotas ao banco relacional e implemente autenticação, autorização e auditoria reais.

## 5. Roteiro rápido de teste ponta a ponta
1. Inicie o servidor e abra `http://127.0.0.1:8000/frontend/`.
2. Entre em Solicitação PAEE e cadastre matrícula e motivo. A mensagem informa os IDs da solicitação e do formulário.
3. Abra Chamados e confirme que o registro apareceu. Consulte Detalhes e avance o status pelas opções disponíveis.
4. Abra Dashboard e Histórico para conferir os mesmos registros.
5. Em Assinaturas e aprovação, selecione o formulário na tabela. Salve uma seção, registre uma assinatura por papel (ALUNO, PROFESSOR e COORDENADOR) e aprove.
6. Em Criar relatório, salve um relatório e confira a tabela de relatórios salvos. Em Feedback, envie uma avaliação.
7. Para testar designação, cadastre primeiro um usuário com `nivel_usuario` igual a `ASSISTENTE` pela API `POST /usuario` em `/docs`; depois use o ID retornado na página Designação de assistente.
8. Execute `python testar_funcoes.py` e `python testar_integracao_json.py` para validar estrutura e operações de API.

O arquivo `backend/data/paee.json` só é criado na primeira chamada à API e começa vazio. Para zerar os dados de teste, pare o servidor, faça backup se necessário e apague esse arquivo; ele será recriado vazio na próxima execução.
