from datetime import date

STATUS_VALIDOS = {"ABERTA", "EM_ANALISE", "EM_PREENCHIMENTO", "AGUARDANDO_ASSINATURAS", "APROVADA", "CONCLUIDA", "INDEFERIDA"}
TRANSICOES = {
    "ABERTA": {"EM_ANALISE", "INDEFERIDA"},
    "EM_ANALISE": {"EM_PREENCHIMENTO", "INDEFERIDA"},
    "EM_PREENCHIMENTO": {"AGUARDANDO_ASSINATURAS", "EM_ANALISE"},
    "AGUARDANDO_ASSINATURAS": {"APROVADA", "EM_PREENCHIMENTO"},
    "APROVADA": {"CONCLUIDA"}, "CONCLUIDA": set(), "INDEFERIDA": set()
}

def validar_transicao_status(atual: str, novo: str) -> bool:
    atual, novo = atual.upper(), novo.upper()
    if atual not in STATUS_VALIDOS or novo not in STATUS_VALIDOS: raise ValueError("Status inválido")
    if novo not in TRANSICOES[atual]: raise ValueError(f"Transição de status não permitida: {atual} -> {novo}")
    return True

def validar_designacao(data_inicio, data_fim=None) -> bool:
    if not data_inicio: raise ValueError("Data inicial é obrigatória")
    inicio = date.fromisoformat(str(data_inicio)) if isinstance(data_inicio, str) else data_inicio
    fim = date.fromisoformat(str(data_fim)) if isinstance(data_fim, str) and data_fim else data_fim
    if fim and fim < inicio: raise ValueError("Data final não pode ser anterior à inicial")
    return True

def validar_assinatura(papel: str) -> bool:
    if papel not in {"ALUNO", "PROFESSOR", "COORDENADOR", "ASSISTENTE"}: raise ValueError("Papel de assinatura inválido")
    return True

def validar_secao(nome: str, conteudo) -> bool:
    if not nome or not nome.strip(): raise ValueError("Nome da seção é obrigatório")
    if conteudo is None or (isinstance(conteudo, str) and not conteudo.strip()): raise ValueError("Conteúdo da seção não pode ficar vazio")
    return True
