/* Interface PAEE. A API, e não esta camada visual, aplica a autorização. */
const API = window.PAEE_API_URL || '';
const token = () => sessionStorage.getItem('paee_token') || '';
let currentUser = null;
let cachedReports = [];
const allowedTransitions = {
  ABERTA: ['EM_ANALISE', 'INDEFERIDA'],
  EM_ANALISE: ['EM_PREENCHIMENTO', 'INDEFERIDA'],
  EM_PREENCHIMENTO: ['AGUARDANDO_ASSINATURAS', 'EM_ANALISE'],
  AGUARDANDO_ASSINATURAS: ['APROVADA', 'EM_PREENCHIMENTO'],
  APROVADA: ['CONCLUIDA'],
  CONCLUIDA: [],
  INDEFERIDA: [],
};
const labels = {
  ABERTA: 'Aberta',
  EM_ANALISE: 'Em análise',
  EM_PREENCHIMENTO: 'Em preenchimento',
  AGUARDANDO_ASSINATURAS: 'Aguardando assinaturas',
  AGUARDANDO_ASSINATURA_ASSISTENTE: 'Aguardando assinatura do assistente',
  AGUARDANDO_APROVACAO: 'Aguardando aprovação final',
  APROVADA: 'Aprovada',
  CONCLUIDA: 'Concluída',
  INDEFERIDA: 'Indeferida',
  RASCUNHO: 'Rascunho',
  APROVADO: 'Aprovado',
};
const categoryFields = {
  CEGO: [
    ['adaptacao_ambiente', 'Adaptação ao ambiente'],
    ['ferramentas_auxilio', 'Ferramentas de auxílio'],
  ],
  SURDO: [
    ['adaptacao_ambiente', 'Adaptação ao ambiente'],
    ['ferramentas_auxilio', 'Ferramentas de auxílio'],
  ],
  AUTISMO: [
    ['socializacao', 'Socialização'],
    ['integracao_ambiente', 'Integração ao ambiente'],
  ],
  INTELECTUAL: [
    ['compreensao_conteudo', 'Compreensão do conteúdo'],
    ['comportamento_sala', 'Comportamento em sala'],
  ],
};
const categoryLabels = {
  CEGO: 'Cego',
  SURDO: 'Surdo',
  INTELECTUAL: 'Intelectual',
  AUTISMO: 'Autismo',
};

function authHeaders(extra = {}) {
  return { ...extra, ...(token() ? { Authorization: `Bearer ${token()}` } : {}) };
}
async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API}${path}`, {
      ...options,
      headers: authHeaders({ ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(options.headers || {}) }),
    });
  } catch {
    throw new Error('Não foi possível conectar ao servidor. Inicie o backend conforme o README_EXECUCAO.md.');
  }
  const result = await response.json().catch(() => ({}));
  if (response.status === 401) {
    sessionStorage.removeItem('paee_token');
    sessionStorage.removeItem('paee_usuario');
    window.location.assign('/frontend/paginas/login/tela_login.html');
    throw new Error('Sessão encerrada. Entre novamente.');
  }
  if (!response.ok) throw new Error(result.detail || result.message || `Erro HTTP ${response.status}`);
  return result;
}
function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
}
function dateText(value) {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? esc(value) : parsed.toLocaleString('pt-BR');
}
function statusLabel(status) { return labels[status] || status || '—'; }
function formMessage(form, text) {
  const target = form?.querySelector('.message');
  if (target) target.textContent = text;
}
async function once(form, action) {
  if (form.dataset.enviando === 'true' || !form.reportValidity()) return;
  form.dataset.enviando = 'true';
  const buttons = [...form.querySelectorAll('button[type="submit"]')];
  buttons.forEach(button => { button.disabled = true; });
  try { await action(); } finally {
    delete form.dataset.enviando;
    buttons.forEach(button => { button.disabled = false; });
  }
}
function can(role, roles) { return roles.includes(role); }

const dateElement = document.getElementById('date');
if (dateElement) dateElement.textContent = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'full' }).format(new Date());

function setupRoleUI(user) {
  const role = user.nivel_usuario;
  const routeRoles = {
    'solicitacao_paee.html': ['ALUNO'],
    'lista_chamados.html': ['ALUNO', 'COORDENADOR'],
    'dashboard.html': ['COORDENADOR'],
    'estatisticas_aluno.html': ['COORDENADOR'],
    'historico.html': ['COORDENADOR'],
    'designacao_assistente.html': ['COORDENADOR'],
    'assinaturas.html': ['COORDENADOR', 'ASSISTENTE'],
    'criar_relatorio.html': ['ASSISTENTE'],
    'usuarios.html': ['COORDENADOR'],
  };
  const page = location.pathname.split('/').pop();
  const navRoles = { ...routeRoles, 'feedback.html': ['ALUNO', 'COORDENADOR', 'ASSISTENTE', 'PROFESSOR'] };
  document.querySelectorAll('a[href]').forEach(link => {
    const target = link.getAttribute('href')?.split('/').pop();
    if (navRoles[target]) link.hidden = !can(role, navRoles[target]);
  });
  if (role === 'COORDENADOR' && !document.querySelector('.side-links a[href="usuarios.html"]')) {
    const link = document.createElement('a');
    link.href = 'usuarios.html';
    link.textContent = 'Usuários e auditoria';
    document.querySelector('.side-links')?.appendChild(link);
  }
  document.querySelectorAll('[data-role-only]').forEach(element => {
    element.hidden = !can(role, element.dataset.roleOnly.split(','));
  });
  document.querySelectorAll('[data-role-hide]').forEach(element => {
    if (can(role, element.dataset.roleHide.split(','))) element.hidden = true;
  });
  if (routeRoles[page] && !can(role, routeRoles[page])) {
    document.querySelector('.content')?.replaceChildren(Object.assign(document.createElement('section'), {
      className: 'panel',
      textContent: 'Seu perfil não tem acesso a esta tela.',
    }));
    return false;
  }
  if (role === 'ALUNO') {
    const matricula = document.getElementById('matricula');
    if (matricula) {
      matricula.value = user.matricula || '';
      matricula.readOnly = true;
    }
  }
  const footer = document.querySelector('.sidebar-footer');
  if (footer) {
    const identity = document.createElement('p');
    identity.textContent = `${user.nome || user.email} · ${role}`;
    footer.prepend(identity);
    const logout = document.createElement('button');
    logout.type = 'button';
    logout.className = 'btn secondary';
    logout.textContent = 'Sair';
    logout.addEventListener('click', () => {
      sessionStorage.removeItem('paee_token');
      sessionStorage.removeItem('paee_usuario');
      location.assign('/frontend/paginas/login/tela_login.html');
    });
    footer.appendChild(logout);
  }
  return true;
}

async function iniciarSessao() {
  if (!token()) {
    location.assign('/frontend/paginas/login/tela_login.html');
    return;
  }
  try {
    currentUser = await api('/api/me');
    if (!setupRoleUI(currentUser)) return;
    initializePage();
    document.dispatchEvent(new Event('paee:session-ready'));
  } catch (error) {
    const content = document.querySelector('.content');
    if (content) content.textContent = error.message;
  }
}

function initializePage() {
  setupRequestForm();
  setupDesignations();
  setupReports();
  setupFeedback();
  setupFormsAndSignatures();
  setupHistory();
  setupTickets();
  setupUsers();
  setupStudentStatistics();
  loadDesignations();
  loadReports();
  loadForms();
  loadTickets();
  loadUsers();
  if (currentUser.nivel_usuario === 'COORDENADOR') loadAudit();
  if (currentUser.nivel_usuario === 'COORDENADOR') loadFeedback();
}

function setupRequestForm() {
  const form = document.getElementById('solicitacaoForm');
  form?.addEventListener('submit', event => {
    event.preventDefault();
    void once(form, async () => {
      try {
        const data = await api('/api/solicitacoes', {
          method: 'POST',
          body: JSON.stringify({
            motivo: document.getElementById('motivo').value.trim(),
          }),
        });
        formMessage(form, `Chamado #${data.id_solicitacao} criado. Status: ${statusLabel(data.status)}.`);
        form.reset();
        if (currentUser?.matricula) document.getElementById('matricula').value = currentUser.matricula;
        await loadTickets();
        await window.carregarResumoVisual?.();
      } catch (error) { formMessage(form, error.message); }
    });
  });
}

function setupDesignations() {
  const form = document.getElementById('designacaoForm');
  form?.addEventListener('submit', event => {
    event.preventDefault();
    void once(form, async () => {
      const read = id => document.getElementById(id)?.value;
      try {
        await api('/api/designacoes', {
          method: 'POST',
          body: JSON.stringify({
            matricula: read('matricula'),
            id_assistente: Number(read('assistente') || read('id_assistente')),
            data_inicio: read('inicio') || read('data_inicio'),
            data_fim: read('fim') || read('data_fim') || null,
          }),
        });
        formMessage(form, 'Designação registrada.');
        form.reset();
        await loadDesignations();
      } catch (error) { formMessage(form, error.message); }
    });
  });
}
async function loadDesignations() {
  const out = document.getElementById('designacoesResultado');
  if (!out) return;
  try {
    const rows = await api('/api/designacoes');
    out.innerHTML = rows.length
      ? `<div class="table-wrap"><table><thead><tr><th>ID</th><th>Matrícula</th><th>Assistente</th><th>Início</th><th>Fim</th></tr></thead><tbody>${rows.map(row => `<tr><td>${row.id_designacao}</td><td>${esc(row.matricula)}</td><td>${esc(row.id_assistente)}</td><td>${esc(row.data_inicio)}</td><td>${esc(row.data_fim || 'Em andamento')}</td></tr>`).join('')}</tbody></table></div>`
      : '<p class="muted">Nenhuma designação registrada.</p>';
  } catch (error) { out.textContent = error.message; }
}

function renderCategoryFields() {
  const category = document.getElementById('matricula')?.selectedOptions[0]?.dataset.category;
  const container = document.getElementById('camposEspecificos');
  if (!container) return;
  const fields = categoryFields[category] || [];
  container.innerHTML = fields.map(([name, label]) => (
    `<fieldset class="field"><legend>${esc(label)}</legend><span id="nota-label-${name}" class="evaluation-prompt">Avaliação obrigatória — selecione uma nota de 1 a 5</span><div class="evaluation-options" role="radiogroup" aria-labelledby="nota-label-${name}">${[1, 2, 3, 4, 5].map(score => `<label for="nota-${name}-${score}"><input id="nota-${name}-${score}" name="nota-${name}" type="radio" value="${score}" data-evaluation-score="${name}" required><span>${score}</span></label>`).join('')}</div><label for="comentario-${name}">Comentário (opcional)</label><textarea id="comentario-${name}" data-evaluation-comment="${name}" maxlength="2000"></textarea></fieldset>`
  )).join('');
}
async function loadDesignatedReportStudents() {
  const select = document.getElementById('matricula');
  if (!select) return;
  try {
    const students = await api('/api/alunos-designados');
    select.replaceChildren(new Option('Selecione o aluno', ''));
    students.forEach(student => {
      const option = new Option(`${student.matricula} — ${student.nome}`, student.matricula);
      option.dataset.category = student.categoria_deficiencia || '';
      select.add(option);
    });
    if (!students.length) select.replaceChildren(new Option('Nenhum aluno designado', ''));
    select.dispatchEvent(new Event('change'));
  } catch (error) {
    select.replaceChildren(new Option('Não foi possível carregar os alunos', ''));
    formMessage(document.getElementById('relatorioForm'), error.message);
  }
}
function setupReports() {
  const studentSelect = document.getElementById('matricula');
  const reportDate = document.getElementById('dataRelatorio');
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  if (reportDate && !reportDate.value) reportDate.value = today;
  studentSelect?.addEventListener('change', () => {
    const category = studentSelect.selectedOptions[0]?.dataset.category || '';
    const categoryField = document.getElementById('categoriaDeficienciaRelatorio');
    if (categoryField) {
      categoryField.value = !studentSelect.value
        ? 'Selecione um aluno'
        : categoryLabels[category] || 'Deficiência não cadastrada';
    }
    renderCategoryFields();
  });
  void loadDesignatedReportStudents();
  const form = document.getElementById('relatorioForm');
  form?.addEventListener('submit', event => {
    event.preventDefault();
    void once(form, async () => {
      const get = id => document.getElementById(id)?.value.trim() || '';
      const start = get('inicio');
      const end = get('fim');
      if (end < start) { formMessage(form, 'A data final não pode ser anterior à inicial.'); return; }
      const evaluations = {};
      document.querySelectorAll('[data-evaluation-score]:checked').forEach(field => {
        const key = field.dataset.evaluationScore;
        evaluations[key] = {
          nota: Number(field.value),
          comentario: document.querySelector(`[data-evaluation-comment="${key}"]`)?.value.trim() || '',
        };
      });
      const description = `${get('titulo')} (${get('tipo')})\nPeríodo: ${start} a ${end}\n${get('descricao')}`;
      try {
        const saved = await api('/api/relatorios', {
          method: 'POST',
          body: JSON.stringify({
            id_aluno: get('matricula'),
            data_relatorio: get('dataRelatorio'),
            materia: get('materia'),
            data_inicio: start,
            data_fim: end,
            descricao: description,
            observacao: get('descricao'),
            titulo: get('titulo'),
            tipo: get('tipo'),
            situacao: get('situacao'),
            avaliacoes: evaluations,
          }),
        });
        formMessage(form, `Relatório #${saved.id_relatorio} salvo.`);
        form.reset();
        if (reportDate) reportDate.value = today;
        studentSelect?.dispatchEvent(new Event('change'));
        await loadReports();
      } catch (error) { formMessage(form, error.message); }
    });
  });
  document.getElementById('exportarRelatorios')?.addEventListener('click', exportReports);
  document.getElementById('relatoriosResultado')?.addEventListener('click', event => {
    const button = event.target.closest('.ver-relatorio');
    if (!button) return;
    const report = cachedReports.find(row => String(row.id_relatorio) === button.dataset.id);
    const panel = document.getElementById('detalhesRelatorio');
    const content = document.getElementById('detalhesRelatorioConteudo');
    if (!report || !panel || !content) return;
    const aspects = categoryFields[report.categoria_deficiencia] || [];
    const evaluations = aspects.map(([key, label]) => {
      const value = report.avaliacoes?.[key] || {};
      return `<dt>${esc(label)}</dt><dd>Nota: ${esc(value.nota ?? '—')} · Comentário: ${esc(value.comentario || '—')}</dd>`;
    }).join('');
    content.innerHTML = `<dl class="detail-list"><dt>Aluno</dt><dd>${esc(report.id_aluno)}</dd><dt>Categoria</dt><dd>${esc(categoryLabels[report.categoria_deficiencia] || report.categoria_deficiencia)}</dd><dt>Matéria</dt><dd>${esc(report.materia || '—')}</dd><dt>Data do relatório</dt><dd>${esc(report.data_relatorio || '—')}</dd><dt>Período</dt><dd>${esc(report.data_inicio || '—')} a ${esc(report.data_fim || '—')}</dd>${evaluations}<dt>Descrição</dt><dd>${esc(report.descricao || '—')}</dd></dl>`;
    panel.hidden = false;
  });
  document.getElementById('fecharDetalhesRelatorio')?.addEventListener('click', () => {
    const panel = document.getElementById('detalhesRelatorio');
    if (panel) panel.hidden = true;
  });
  document.getElementById('imprimirRelatorio')?.addEventListener('click', () => window.print());
}
function setupStudentStatistics() {
  const form = document.getElementById('estatisticasBusca');
  const search = document.getElementById('buscarAluno');
  const select = document.getElementById('alunoSelecionado');
  const subject = document.getElementById('materiaEstatisticas');
  const chart = document.getElementById('estatisticasMensais');
  const title = document.getElementById('alunoEstatisticasTitulo');
  const message = document.getElementById('estatisticasMensagem');
  if (!form || !search || !select || !chart) return;

  let students = [];
  const refreshOptions = () => {
    const filter = search.value.trim().toLocaleLowerCase('pt-BR');
    const current = select.value;
    const filtered = students.filter(student =>
      `${student.nome || ''} ${student.matricula || ''}`.toLocaleLowerCase('pt-BR').includes(filter)
    );
    select.replaceChildren(new Option('Selecione um aluno', ''));
    filtered.forEach(student => {
      select.add(new Option(`${student.nome} — ${student.matricula}`, student.matricula));
    });
    if (filtered.some(student => String(student.matricula) === current)) select.value = current;
  };
  const renderStats = data => {
    const months = data.estatisticas_mensais || [];
    chart.innerHTML = months.length
      ? months.map(month => {
        const height = Math.round(month.media / 5 * 150);
        const aspects = (data.aspectos || []).map(aspect => {
          const value = month.medias_aspectos?.[aspect.chave];
          return value == null ? '' : `<span>${esc(aspect.nome)}: ${value.toFixed(2)}</span>`;
        }).filter(Boolean).join(' · ');
        return `<div class="bar-group" aria-label="${esc(month.mes)}: média ${month.media.toFixed(2)} de 5"><strong>${month.media.toFixed(2)}</strong><div class="bar" style="height:${height}px"></div><span>${esc(month.mes)}</span><small>${month.quantidade_relatorios} relatório(s)${aspects ? `<br>${aspects}` : ''}</small></div>`;
      }).join('')
      : '<p class="muted">Não há avaliações para o aluno e matéria selecionados.</p>';
    if (title) title.textContent = `${data.aluno.nome} — ${categoryLabels[data.aluno.categoria_deficiencia] || 'categoria não informada'}`;
  };
  const loadStudentStatistics = async (matricula, selectedSubject = '') => {
    if (!matricula) {
      if (message) message.textContent = 'Selecione um aluno.';
      return;
    }
    if (message) message.textContent = 'Carregando avaliações...';
    chart.textContent = 'Carregando avaliações...';
    try {
      const base = await api(`/api/alunos/${encodeURIComponent(matricula)}/estatisticas`);
      const filter = selectedSubject || '';
      const data = filter
        ? await api(`/api/alunos/${encodeURIComponent(matricula)}/estatisticas?materia=${encodeURIComponent(filter)}`)
        : base;
      const previous = subject.value;
      subject.replaceChildren(new Option('Todas as matérias', ''));
      (base.materias || []).forEach(value => subject.add(new Option(value, value)));
      subject.value = (base.materias || []).includes(previous) ? previous : filter;
      renderStats(data);
      if (message) message.textContent = '';
    } catch (error) {
      chart.textContent = error.message;
      if (message) message.textContent = error.message;
    }
  };

  search.addEventListener('input', refreshOptions);
  form.addEventListener('submit', event => {
    event.preventDefault();
    void loadStudentStatistics(select.value, subject.value);
  });
  subject.addEventListener('change', () => {
    if (select.value) void loadStudentStatistics(select.value, subject.value);
  });
  api('/api/alunos').then(rows => {
    students = rows;
    refreshOptions();
    const matricula = new URLSearchParams(location.search).get('matricula') || '';
    if (matricula) {
      search.value = matricula;
      refreshOptions();
      select.value = matricula;
      void loadStudentStatistics(matricula);
    }
  }).catch(error => {
    if (message) message.textContent = error.message;
  });
}
async function loadReports() {
  const out = document.getElementById('relatoriosResultado');
  if (!out) return;
  try {
    cachedReports = await api('/api/relatorios');
    out.innerHTML = cachedReports.length
      ? `<div class="table-wrap"><table><thead><tr><th>ID</th><th>Matrícula</th><th>Categoria</th><th>Matéria</th><th>Data</th><th>Título</th><th>Período</th><th>Ações</th></tr></thead><tbody>${cachedReports.map(row => `<tr><td>#${row.id_relatorio}</td><td>${esc(row.id_aluno)}</td><td>${esc(categoryLabels[row.categoria_deficiencia] || row.categoria_deficiencia)}</td><td>${esc(row.materia || '—')}</td><td>${esc(row.data_relatorio || '—')}</td><td>${esc(row.titulo || 'Relatório PAEE')}</td><td>${esc(row.data_inicio)} a ${esc(row.data_fim)}</td><td><button type="button" class="btn secondary ver-relatorio" data-id="${row.id_relatorio}">Detalhes</button></td></tr>`).join('')}</tbody></table></div>`
      : '<p class="muted">Nenhum relatório salvo.</p>';
  } catch (error) { out.textContent = error.message; }
}
function setupFeedback() {
  const form = document.getElementById('feedbackForm');
  if (currentUser?.nivel_usuario === 'COORDENADOR') return;
  form?.addEventListener('submit', event => {
    event.preventDefault();
    void once(form, async () => {
      const read = id => document.getElementById(id)?.value || '';
      try {
        await api('/api/feedback', {
          method: 'POST',
          body: JSON.stringify({ assunto: read('assunto'), avaliacao: Number(read('avaliacao')), comentario: read('comentario') }),
        });
        formMessage(form, 'Feedback registrado. Obrigado!');
        form.reset();
      } catch (error) { formMessage(form, error.message); }
    });
  });
}
async function loadFeedback() {
  const out = document.getElementById('feedbacksResultado');
  if (!out) return;
  try {
    const rows = await api('/api/feedback');
    out.innerHTML = rows.length
      ? `<div class="table-wrap"><table><thead><tr><th>Data</th><th>Usuário</th><th>Assunto</th><th>Avaliação</th><th>Comentário</th></tr></thead><tbody>${rows.map(row => `<tr><td>${dateText(row.criado_em)}</td><td>${esc(row.nome || row.email)}</td><td>${esc(row.assunto)}</td><td>${esc(row.avaliacao)}</td><td>${esc(row.comentario)}</td></tr>`).join('')}</tbody></table></div>`
      : '<p class="muted">Nenhum feedback recebido.</p>';
  } catch (error) { out.textContent = error.message; }
}

function setupFormsAndSignatures() {
  const signatureForm = document.getElementById('assinaturaForm');
  signatureForm?.addEventListener('submit', event => {
    event.preventDefault();
    void once(signatureForm, async () => {
      const id = document.getElementById('formulario')?.value;
      try {
        await api(`/api/formularios/${id}/assinar`, { method: 'POST' });
        formMessage(signatureForm, `Assinatura de ${currentUser.nivel_usuario} registrada.`);
        await loadForms();
      } catch (error) { formMessage(signatureForm, error.message); }
    });
  });
  const sectionForm = document.getElementById('secaoForm');
  sectionForm?.addEventListener('submit', event => {
    event.preventDefault();
    void once(sectionForm, async () => {
      const id = document.getElementById('secaoFormularioId').value;
      const name = document.getElementById('nomeSecao').value.trim();
      const content = document.getElementById('conteudoSecao').value.trim();
      try {
        await api(`/api/formularios/${id}/secoes/${encodeURIComponent(name)}`, {
          method: 'PUT', body: JSON.stringify({ conteudo: content }),
        });
        formMessage(sectionForm, 'Seção salva.');
        await loadForms();
      } catch (error) { formMessage(sectionForm, error.message); }
    });
  });
  const upload = document.getElementById('anexoForm');
  upload?.addEventListener('submit', event => {
    event.preventDefault();
    void once(upload, async () => {
      const id = document.getElementById('anexoFormularioId').value;
      const file = document.getElementById('arquivoPdf').files[0];
      if (!file) { formMessage(upload, 'Selecione um PDF.'); return; }
      if (file.size > 10 * 1024 * 1024) { formMessage(upload, 'O arquivo deve ter no máximo 10 MB.'); return; }
      const body = new FormData();
      body.append('arquivo', file);
      try {
        await api(`/api/formularios/${id}/anexo`, { method: 'POST', body });
        formMessage(upload, 'Anexo substituído. O arquivo fica em armazenamento privado.');
        await loadForms();
      } catch (error) { formMessage(upload, error.message); }
    });
  });
  document.getElementById('baixarAnexo')?.addEventListener('click', async () => {
    const id = document.getElementById('formulario')?.value;
    const output = document.getElementById('aprovacaoMensagem');
    try {
      const response = await fetch(`${API}/api/formularios/${id}/anexo`, { headers: authHeaders() });
      if (!response.ok) throw new Error('Não foi possível baixar o anexo autorizado.');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'anexo-paee.pdf';
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) { if (output) output.textContent = error.message; }
  });
  document.getElementById('aprovarFormulario')?.addEventListener('click', async event => {
    const button = event.currentTarget;
    const id = document.getElementById('formulario')?.value;
    const output = document.getElementById('aprovacaoMensagem');
    button.disabled = true;
    try {
      await api(`/api/formularios/${id}/aprovar`, { method: 'POST' });
      if (output) output.textContent = 'Formulário aprovado.';
      await loadForms();
    } catch (error) { if (output) output.textContent = error.message; }
    finally { button.disabled = false; }
  });
  document.getElementById('formulariosResultado')?.addEventListener('click', event => {
    const button = event.target.closest('.escolher-formulario');
    if (!button) return;
    const input = document.getElementById('formulario');
    const sectionInput = document.getElementById('secaoFormularioId');
    const uploadInput = document.getElementById('anexoFormularioId');
    if (input) input.value = button.dataset.id;
    if (sectionInput) sectionInput.value = button.dataset.id;
    if (uploadInput) uploadInput.value = button.dataset.id;
  });
}
async function loadForms() {
  const out = document.getElementById('formulariosResultado');
  if (!out) return;
  try {
    const rows = await api('/api/formularios');
    out.innerHTML = rows.length
      ? `<div class="table-wrap"><table><thead><tr><th>ID</th><th>Solicitação</th><th>Status</th><th>Seções</th><th>Assinaturas</th><th>Ação</th></tr></thead><tbody>${rows.map(form => `<tr><td>#${form.id_formulario}</td><td>#${form.id_solicitacao}</td><td>${esc(statusLabel(form.status))}</td><td>${Object.keys(form.secoes || {}).length}</td><td>${(form.assinaturas || []).length}</td><td><button type="button" class="btn secondary escolher-formulario" data-id="${form.id_formulario}">Selecionar</button>${form.anexo ? ` <button type="button" class="btn secondary baixar-formulario-anexo" data-id="${form.id_formulario}">Baixar PDF</button>` : ''}</td></tr>`).join('')}</tbody></table></div>`
      : '<p class="muted">Nenhum formulário disponível para seu perfil.</p>';
    out.querySelectorAll('.baixar-formulario-anexo').forEach(button => button.addEventListener('click', () => downloadAttachment(button.dataset.id)));
  } catch (error) { out.textContent = error.message; }
}
async function downloadAttachment(id) {
  try {
    const response = await fetch(`${API}/api/formularios/${id}/anexo`, { headers: authHeaders() });
    if (!response.ok) throw new Error('Download não autorizado ou anexo ausente.');
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'anexo-paee.pdf';
    a.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    const message = document.getElementById('aprovacaoMensagem');
    if (message) message.textContent = error.message;
  }
}

function setupHistory() {
  document.getElementById('buscarHistorico')?.addEventListener('click', () => loadHistory(
    document.getElementById('matriculaHistorico')?.value,
  ));
}
async function loadHistory(matricula) {
  const out = document.getElementById('historicoResultado');
  if (!out) return;
  try {
    const rows = await api(`/api/historico/${encodeURIComponent(matricula || '')}`);
    out.innerHTML = rows.length
      ? `<div class="table-wrap"><table><thead><tr><th>ID</th><th>Motivo</th><th>Status</th><th>Criação</th><th>Atualização</th></tr></thead><tbody>${rows.map(row => `<tr><td>#${row.id_solicitacao}</td><td>${esc(row.motivo)}</td><td>${esc(statusLabel(row.status))}</td><td>${dateText(row.criado_em)}</td><td>${dateText(row.atualizado_em)}</td></tr>`).join('')}</tbody></table></div>`
      : '<p class="muted">Nenhuma solicitação encontrada.</p>';
  } catch (error) { out.textContent = error.message; }
}

function setupTickets() {
  const search = document.getElementById('search');
  const filter = document.getElementById('filter');
  search?.addEventListener('input', filterTickets);
  filter?.addEventListener('change', filterTickets);
  document.getElementById('tickets')?.addEventListener('click', async event => {
    const button = event.target.closest('.details-ticket');
    if (!button) return;
    const panel = document.getElementById('detalhesChamado');
    const out = document.getElementById('detalhesChamadoConteudo');
    try {
      const row = await api(`/api/solicitacoes/${button.dataset.id}`);
      out.innerHTML = `<dl class="detail-list"><dt>Chamado</dt><dd>#${row.id_solicitacao}</dd><dt>Matrícula</dt><dd>${esc(row.matricula)}</dd><dt>Motivo</dt><dd>${esc(row.motivo)}</dd><dt>Status</dt><dd>${esc(statusLabel(row.status))}</dd><dt>Categoria</dt><dd>${esc(row.categoria_deficiencia || '—')}</dd><dt>Criado em</dt><dd>${dateText(row.criado_em)}</dd><dt>Formulário</dt><dd>${row.formulario?.id_formulario || '—'}</dd></dl>`;
      panel.hidden = false;
    } catch (error) { out.textContent = error.message; panel.hidden = false; }
  });
  document.getElementById('tickets')?.addEventListener('change', async event => {
    const select = event.target.closest('.status-ticket');
    if (!select || !select.value) return;
    try {
      await api(`/api/solicitacoes/${select.dataset.id}/status`, {
        method: 'PATCH', body: JSON.stringify({ status: select.value }),
      });
      await loadTickets();
      await window.carregarResumoVisual?.();
    } catch (error) {
      const message = document.getElementById('statusMessageTickets');
      if (message) message.textContent = error.message;
      await loadTickets();
    }
  });
  document.getElementById('fecharDetalhesChamado')?.addEventListener('click', () => {
    const panel = document.getElementById('detalhesChamado');
    if (panel) panel.hidden = true;
  });
}
function filterTickets() {
  const query = document.getElementById('search')?.value.toLowerCase() || '';
  const status = document.getElementById('filter')?.value || '';
  document.querySelectorAll('#ticketsBody tr[data-row-id]').forEach(row => {
    const matchSearch = row.textContent.toLowerCase().includes(query);
    const matchStatus = !status || row.dataset.status === status;
    row.hidden = !(matchSearch && matchStatus);
  });
}
async function loadTickets() {
  const tbody = document.getElementById('ticketsBody');
  if (!tbody) return;
  try {
    const rows = await api('/api/solicitacoes');
    const metrics = document.querySelectorAll('.cards .metric strong');
    const count = status => rows.filter(row => row.status === status).length;
    [rows.length, count('ABERTA'), rows.filter(row => ['EM_ANALISE', 'EM_PREENCHIMENTO', 'AGUARDANDO_ASSINATURAS', 'APROVADA'].includes(row.status)).length, count('CONCLUIDA')].forEach((value, index) => {
      if (metrics[index]) metrics[index].textContent = String(value);
    });
    tbody.innerHTML = rows.length
      ? rows.map(row => `<tr data-row-id="${row.id_solicitacao}" data-status="${esc(row.status)}"><td>#${row.id_solicitacao}</td><td>${esc(row.motivo)}</td><td>PAEE</td><td>${dateText(row.criado_em)}</td><td><span class="status">${esc(statusLabel(row.status))}</span></td><td><button class="btn secondary details-ticket" data-id="${row.id_solicitacao}" type="button">Detalhes</button> ${currentUser?.nivel_usuario === 'COORDENADOR' ? `<select class="status-ticket" aria-label="Novo status" data-id="${row.id_solicitacao}"><option value="">Alterar status…</option>${(allowedTransitions[row.status] || []).map(next => `<option value="${next}">${esc(statusLabel(next))}</option>`).join('')}</select>` : ''}</td></tr>`).join('')
      : '<tr><td colspan="6">Nenhuma solicitação disponível.</td></tr>';
    filterTickets();
  } catch (error) {
    tbody.innerHTML = `<tr><td colspan="6">${esc(error.message)}</td></tr>`;
  }
}

function setupUsers() {
  const createForm = document.getElementById('usuarioForm');
  const setStudentRequirements = (roleId, matriculaId, disabilityId, disabilityFieldId) => {
    const role = document.getElementById(roleId);
    const matricula = document.getElementById(matriculaId);
    const disability = document.getElementById(disabilityId);
    const disabilityField = document.getElementById(disabilityFieldId);
    if (!role || !matricula || !disability || !disabilityField) return;
    const update = () => {
      const isStudent = role.value === 'ALUNO';
      matricula.required = isStudent;
      disability.required = isStudent;
      disabilityField.hidden = !isStudent;
    };
    role.addEventListener('change', update);
    update();
  };
  setStudentRequirements('novoPapel', 'novaMatricula', 'novaDeficiencia', 'novaDeficienciaField');
  setStudentRequirements('editarPapel', 'editarMatricula', 'editarDeficiencia', 'editarDeficienciaField');
  createForm?.addEventListener('submit', event => {
    event.preventDefault();
    void once(createForm, async () => {
      const payload = Object.fromEntries(new FormData(createForm));
      try {
        await api('/api/usuarios', { method: 'POST', body: JSON.stringify(payload) });
        formMessage(createForm, 'Usuário criado.');
        createForm.reset();
        await loadUsers();
        await loadAudit();
      } catch (error) { formMessage(createForm, error.message); }
    });
  });
  document.getElementById('usuariosResultado')?.addEventListener('click', async event => {
    const select = event.target.closest('.editar-usuario');
    const toggle = event.target.closest('.alternar-usuario');
    if (select) {
      const user = JSON.parse(decodeURIComponent(select.dataset.user));
      document.getElementById('editarUsuarioId').value = user.id_usuario;
      document.getElementById('editarNome').value = user.nome || '';
      document.getElementById('editarEmail').value = user.email || '';
      document.getElementById('editarPapel').value = user.nivel_usuario || '';
      document.getElementById('editarMatricula').value = user.matricula || '';
      document.getElementById('editarMatricula').required = user.nivel_usuario === 'ALUNO';
      document.getElementById('editarDeficiencia').value = user.categoria_deficiencia || '';
      document.getElementById('editarDeficiencia').required = user.nivel_usuario === 'ALUNO';
      document.getElementById('editarDeficienciaField').hidden = user.nivel_usuario !== 'ALUNO';
      document.getElementById('editarCurso').value = user.curso || '';
      document.getElementById('editarPeriodo').value = user.periodo || '';
      document.getElementById('editarTelefone').value = user.telefone || '';
      return;
    }
    if (!toggle) return;
    try {
      const action = toggle.dataset.active === 'true' ? 'desativar' : 'reativar';
      await api(`/api/usuarios/${toggle.dataset.id}/${action}`, { method: 'POST' });
      await loadUsers();
      await loadAudit();
    } catch (error) {
      const output = document.getElementById('usuarioMensagem');
      if (output) output.textContent = error.message;
    }
  });
  document.getElementById('editarUsuarioForm')?.addEventListener('submit', event => {
    event.preventDefault();
    const form = event.currentTarget;
    void once(form, async () => {
      const value = id => document.getElementById(id).value;
      const payload = {
        nome: value('editarNome'),
        email: value('editarEmail'),
        nivel_usuario: value('editarPapel'),
        matricula: value('editarMatricula'),
        categoria_deficiencia: value('editarDeficiencia'),
        curso: value('editarCurso'),
        periodo: value('editarPeriodo'),
        telefone: value('editarTelefone'),
      };
      const password = value('editarSenha');
      if (password) payload.senha = password;
      try {
        await api(`/api/usuarios/${value('editarUsuarioId')}`, { method: 'PATCH', body: JSON.stringify(payload) });
        formMessage(form, 'Usuário atualizado.');
        form.reset();
        await loadUsers();
        await loadAudit();
      } catch (error) { formMessage(form, error.message); }
    });
  });
}
async function loadUsers() {
  const out = document.getElementById('usuariosResultado');
  if (!out || currentUser?.nivel_usuario !== 'COORDENADOR') return;
  try {
    const rows = await api('/api/usuarios');
    out.innerHTML = rows.length
      ? `<div class="table-wrap"><table><thead><tr><th>ID</th><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Matrícula</th><th>Deficiência</th><th>Estado</th><th>Ações</th></tr></thead><tbody>${rows.map(user => `<tr><td>${user.id_usuario}</td><td>${esc(user.nome)}</td><td>${esc(user.email)}</td><td>${esc(user.nivel_usuario)}</td><td>${esc(user.matricula || '—')}</td><td>${esc(categoryLabels[user.categoria_deficiencia] || user.categoria_deficiencia || '—')}</td><td>${user.ativo ? 'Ativo' : 'Inativo'}</td><td><button class="btn secondary editar-usuario" type="button" data-user="${encodeURIComponent(JSON.stringify(user))}">Editar</button> <button class="btn secondary alternar-usuario" type="button" data-id="${user.id_usuario}" data-active="${Boolean(user.ativo)}">${user.ativo ? 'Desativar' : 'Reativar'}</button></td></tr>`).join('')}</tbody></table></div>`
      : '<p class="muted">Nenhum usuário cadastrado.</p>';
  } catch (error) { out.textContent = error.message; }
}
async function loadAudit() {
  const out = document.getElementById('auditoriaResultado');
  if (!out || currentUser?.nivel_usuario !== 'COORDENADOR') return;
  try {
    const rows = await api('/api/auditoria');
    out.innerHTML = rows.length
      ? `<div class="table-wrap"><table><thead><tr><th>Data</th><th>Ator</th><th>Perfil</th><th>Ação</th><th>Registro</th></tr></thead><tbody>${rows.map(row => `<tr><td>${dateText(row.ocorrido_em)}</td><td>#${row.ator_id_usuario}</td><td>${esc(row.ator_papel)}</td><td>${esc(row.acao)}</td><td>${esc(row.entidade)} #${esc(row.alvo_id)}</td></tr>`).join('')}</tbody></table></div>`
      : '<p class="muted">Nenhum evento registrado.</p>';
  } catch (error) { out.textContent = error.message; }
}
async function exportReports() {
  const button = document.getElementById('exportarRelatorios');
  if (!button) return;
  button.disabled = true;
  try {
    const rows = await api('/api/relatorios');
    if (!rows.length) throw new Error('Não há relatórios para exportar.');
    const columns = ['id_relatorio', 'id_aluno', 'categoria_deficiencia', 'materia', 'data_relatorio', 'titulo', 'data_inicio', 'data_fim', 'avaliacoes', 'descricao'];
    const cell = value => `"${String(value && typeof value === 'object' ? JSON.stringify(value) : value ?? '').replace(/^[=+\-@]/, "'$&").replace(/"/g, '""')}"`;
    const csv = '\uFEFF' + [columns.join(';'), ...rows.map(row => columns.map(key => cell(row[key])).join(';'))].join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'relatorios_paee.csv';
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    const out = document.getElementById('relatoriosResultado');
    if (out) out.textContent = error.message;
  } finally { button.disabled = false; }
}

iniciarSessao();
