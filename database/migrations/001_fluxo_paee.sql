-- Novas tabelas das waves 3 a 6. Não altera nem recria as tabelas existentes.
-- Executar uma vez no banco PostgreSQL/Supabase depois de conferir os nomes de chave do DER.
CREATE TABLE IF NOT EXISTS solicitacao_paee (
 id_solicitacao BIGSERIAL PRIMARY KEY,
 matricula BIGINT NOT NULL REFERENCES aluno(matricula),
 criado_por BIGINT NOT NULL REFERENCES usuario(id_usuario),
 motivo TEXT NOT NULL,
 status VARCHAR(32) NOT NULL DEFAULT 'ABERTA' CHECK (status IN ('ABERTA','EM_ANALISE','EM_PREENCHIMENTO','AGUARDANDO_ASSINATURAS','APROVADA','CONCLUIDA','INDEFERIDA')),
 criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(), atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS formulario_paee (
 id_formulario BIGSERIAL PRIMARY KEY,
 id_solicitacao BIGINT NOT NULL UNIQUE REFERENCES solicitacao_paee(id_solicitacao) ON DELETE CASCADE,
 status VARCHAR(32) NOT NULL DEFAULT 'RASCUNHO' CHECK (status IN ('RASCUNHO','EM_PREENCHIMENTO','AGUARDANDO_ASSINATURAS','APROVADO')),
 aprovado_por BIGINT REFERENCES usuario(id_usuario), aprovado_em TIMESTAMPTZ, criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS secao_formulario (
 id_secao BIGSERIAL PRIMARY KEY,
 id_formulario BIGINT NOT NULL REFERENCES formulario_paee(id_formulario) ON DELETE CASCADE,
 nome_secao VARCHAR(120) NOT NULL, conteudo JSONB NOT NULL,
 atualizado_por BIGINT NOT NULL REFERENCES usuario(id_usuario), atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 UNIQUE(id_formulario,nome_secao)
);
CREATE TABLE IF NOT EXISTS designacao_assistente (
 id_designacao BIGSERIAL PRIMARY KEY,
 matricula BIGINT NOT NULL REFERENCES aluno(matricula),
 id_assistente BIGINT NOT NULL REFERENCES assistente(id_assistente),
 data_inicio DATE NOT NULL, data_fim DATE,
 criado_por BIGINT NOT NULL REFERENCES usuario(id_usuario), criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CHECK(data_fim IS NULL OR data_fim >= data_inicio)
);
CREATE INDEX IF NOT EXISTS idx_designacao_aluno_periodo ON designacao_assistente(matricula,data_inicio,data_fim);
CREATE TABLE IF NOT EXISTS assinatura_formulario (
 id_assinatura BIGSERIAL PRIMARY KEY,
 id_formulario BIGINT NOT NULL REFERENCES formulario_paee(id_formulario) ON DELETE CASCADE,
 id_usuario BIGINT NOT NULL REFERENCES usuario(id_usuario), papel VARCHAR(20) NOT NULL CHECK (papel IN ('ALUNO','PROFESSOR','COORDENADOR','ASSISTENTE')),
 assinado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(id_formulario,id_usuario)
);
CREATE TABLE IF NOT EXISTS relatorio_paee (
 id_relatorio BIGSERIAL PRIMARY KEY,
 matricula BIGINT NOT NULL REFERENCES aluno(matricula),
 data_relatorio DATE NOT NULL, descricao TEXT NOT NULL, observacao TEXT NOT NULL DEFAULT '', criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS feedback_paee (
 id_feedback BIGSERIAL PRIMARY KEY, nome VARCHAR(160) NOT NULL, email VARCHAR(254) NOT NULL, assunto VARCHAR(80) NOT NULL, avaliacao SMALLINT NOT NULL CHECK (avaliacao BETWEEN 1 AND 5), comentario TEXT NOT NULL, criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
