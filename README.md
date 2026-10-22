# Sistema de Apoio ao PAEE (Plataforma Digital de Inclusão)

Plataforma web desenvolvida no âmbito do Projeto Interdisciplinar da FATEC Indaiatuba para digitalizar, organizar e otimizar o fluxo de processamento e acompanhamento dos Planos de Atendimento Educacional Especializado (PAEE) para estudantes com deficiência (PcD).

## Sobre o Projeto

O sistema substitui o modelo tradicional e manual baseado em formulários de papel e assinaturas presenciais. O objetivo principal é atuar na orquestração do fluxo de trabalho interno, controlando preenchimentos distribuídos por docentes, validações por parte da coordenação e a geração automatizada do documento final em formato PDF para encaminhamento institucional.

## Atores e Perfis do Sistema

* **Coordenador**: Vincular disciplinas e professores, revisar as seções preenchidas, realizar a validação digital e consolidar o PAEE.
* **Professores**: Responsáveis por preencher de forma restrita e isolada as seções correspondentes às suas respectivas disciplinas.
* **Assistentes de Apoio (AME)**: Realizam os registros de acompanhamento dos alunos por meio de interfaces ágeis com filtros dinâmicos e caixas de seleção.
* **Direção**: Pelo encaminhamento formal da solicitação consolidada para as instâncias externas.
* **Aluno**: Responsável por abrir os processos e enviar informações e documentos sobre a situação do mesmo.

## Arquitetura e Estrutura do Repositório

- `backend/`: API FastAPI, validações do fluxo e armazenamento JSON local.
- `frontend/`: páginas HTML, estilos e scripts que consomem a API.
- `database/`: SQL de referência para a estrutura relacional e a migration complementar.
- `testar_funcoes.py`: verificações de estrutura, imports e regras de domínio.
- `testar_integracao_json.py`: testes HTTP integrados usando arquivo JSON temporário.

O caminho executável atual é a API FastAPI em `backend/routes.py`, que também serve os arquivos de `frontend/`. A configuração documentada para demonstração usa JSON local; a migration PostgreSQL ainda não está conectada às rotas do fluxo PAEE.

## Requisitos e Regras Principais

Os itens abaixo são objetivos funcionais do produto. O modo JSON implementado nesta versão não oferece todas as garantias de autorização e rastreabilidade descritas.

* **Fluxo Sem Papel (Zero Híbrido)**: A ferramenta foi concebida para substituir definitivamente o uso de fichas impressas, eliminando a sobrecarga de redigitação e o consumo de insumos materiais.
* **Segurança e Rastreabilidade**: Controle estrito de acesso baseado em papéis (RBAC) e registro de auditoria (timestamp) para aprovações e assinaturas digitais.
* **Filtros Dinâmicos**: Exibição inteligente de formulários segmentados de acordo com a especificidade e o tipo de deficiência do aluno cadastrado.

## Como Executar o Projeto

Consulte [README_EXECUCAO.md](README_EXECUCAO.md) para instalação, inicialização, login local e execução dos testes.

> **Limitação importante:** o armazenamento JSON e o token de login local são apenas para desenvolvimento/demonstração. A API não aplica autorização por perfil nem deve ser exposta à internet ou usada com dados pessoais reais. Consulte as limitações e os passos exatos no guia de execução antes de usar.

## DER do banco de dados

![alt text](image.png)

## Tabelas e campos

**usuario:**
id_usuario PK
email
senha_hash
id_tipo_usuario FK
ativo

**tipo_usuario:**
id_tipo_usuario PK
descricao

**aluno:**
matricula PK
id_usuario FK
nome
curso
periodo

**professor:**
id_professor PK
id_usuario FK
nome

**assistente:**
id_assistente PK
id_usuario FK
cnpj_emp
nome_emp
nome_assist
especialidade

**coordenador:**
id_coordenador PK
nome
id_usuario FK
curso

**telefone:**
id_tel PK
id_usuario FK
numero_tel