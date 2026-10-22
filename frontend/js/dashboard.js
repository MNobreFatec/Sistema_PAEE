const dashboardChart = document.getElementById('chamadosPorMes');
const recentActivities = document.getElementById('atividadesRecentes');
const statusSummary = document.getElementById('statusResumo');
const dashboardMetrics = document.querySelectorAll('.cards .metric strong');

function dashboardEscape(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[char]);
}

function dashboardDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Data indisponível' : date.toLocaleDateString('pt-BR');
}

function dashboardStatus(value) {
  return ({
    ABERTA: 'Aberta',
    EM_ANALISE: 'Em análise',
    EM_PREENCHIMENTO: 'Em preenchimento',
    AGUARDANDO_ASSINATURAS: 'Aguardando assinaturas',
    APROVADA: 'Aprovada',
    CONCLUIDA: 'Concluída',
    INDEFERIDA: 'Indeferida',
  })[value] || value;
}

async function carregarResumoVisual() {
  if (!dashboardChart && !recentActivities && !statusSummary && !dashboardMetrics.length) return;

  try {
    const response = await fetch(`${window.PAEE_API_URL || window.location.origin}/api/solicitacoes`);
    const result = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(result?.detail || `Erro HTTP ${response.status}`);
    }
    if (!Array.isArray(result)) throw new Error('A API retornou uma lista de solicitações inválida.');
    const rows = result;
    const count = status => rows.filter(row => row.status === status).length;
    const open = count('ABERTA');
    const inProgress = ['EM_ANALISE', 'EM_PREENCHIMENTO', 'AGUARDANDO_ASSINATURAS', 'APROVADA']
      .reduce((total, status) => total + count(status), 0);
    const completed = count('CONCLUIDA');
    [rows.length, open, inProgress, completed].forEach((value, index) => {
      if (dashboardMetrics[index]) dashboardMetrics[index].textContent = String(value);
    });

    if (statusSummary) {
      const total = Math.max(rows.length, 1);
      const groups = [['Concluídos', completed], ['Em andamento', inProgress], ['Abertos', open]];
      statusSummary.innerHTML = groups.map(([label, value]) => {
        const percentage = Math.round(value / total * 100);
        return `${label} — ${value} (${percentage}%)<div class="progress"><div style="width:${percentage}%"></div></div>`;
      }).join('');
      const note = document.querySelector('.note');
      if (note) note.textContent = `Indicadores atualizados com ${rows.length} solicitação(ões) registrada(s) neste ambiente.`;
    }

    if (dashboardChart) {
      const now = new Date();
      const months = Array.from({length: 6}, (_, index) => {
        const month = new Date(now.getFullYear(), now.getMonth() - 5 + index, 1);
        return {
          year: month.getFullYear(),
          month: month.getMonth(),
          label: new Intl.DateTimeFormat('pt-BR', {month: 'short'}).format(month),
          count: 0,
        };
      });
      rows.forEach(row => {
        const created = new Date(row.criado_em);
        const month = months.find(item =>
          item.year === created.getFullYear() && item.month === created.getMonth()
        );
        if (month) month.count += 1;
      });
      const highest = Math.max(...months.map(month => month.count), 1);
      dashboardChart.innerHTML = months.map(month => {
        const height = Math.max(Math.round(month.count / highest * 150), month.count ? 8 : 0);
        return `<div class="bar-group"><strong>${month.count}</strong><div class="bar" style="height:${height}px"></div><span>${dashboardEscape(month.label)}</span></div>`;
      }).join('');
    }

    if (recentActivities) {
      const recent = [...rows].sort((left, right) =>
        new Date(right.criado_em) - new Date(left.criado_em)
      ).slice(0, 5);
      recentActivities.innerHTML = recent.length
        ? recent.map(row => `<div class="item"><span>Solicitação #${row.id_solicitacao} — ${dashboardEscape(row.motivo)}</span><span class="status">${dashboardEscape(dashboardStatus(row.status))} · ${dashboardDate(row.criado_em)}</span></div>`).join('')
        : '<p class="muted">Nenhuma solicitação cadastrada.</p>';
    }
  } catch (error) {
    const detail = error instanceof TypeError && /fetch|network|load failed/i.test(error.message)
      ? 'Não foi possível conectar ao servidor.'
      : error.message;
    const message = `Não foi possível carregar os dados: ${dashboardEscape(detail)}`;
    dashboardMetrics.forEach(metric => { metric.textContent = '—'; });
    if (dashboardChart) dashboardChart.textContent = message;
    if (recentActivities) recentActivities.textContent = message;
    if (statusSummary) statusSummary.textContent = message;
    const note = document.querySelector('.note');
    if (note) note.textContent = 'Os indicadores não foram atualizados.';
  }
}

window.carregarResumoVisual = carregarResumoVisual;
carregarResumoVisual();
