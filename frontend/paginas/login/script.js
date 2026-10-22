const API_URL = window.PAEE_API_URL || window.location.origin;

const savedEmail = localStorage.getItem('paee_email');
if (savedEmail) {
  document.getElementById('identifier').value = savedEmail;
  document.getElementById('rememberMe').checked = true;
}

function togglePasswordVisibility() {
  const password = document.getElementById('password');
  const icon = document.getElementById('passwordEyeIcon');
  const visible = password.type === 'password';
  password.type = visible ? 'text' : 'password';
  icon.classList.toggle('fa-eye', !visible);
  icon.classList.toggle('fa-eye-slash', visible);
  document.getElementById('togglePasswordBtn').setAttribute(
    'aria-label',
    visible ? 'Ocultar senha' : 'Mostrar senha'
  );
}

function handleForgotPassword(event) {
  event.preventDefault();
  showInfoModal(
    'Recuperação de senha',
    'A recuperação de senha não está disponível no modo local. Entre em contato com o suporte da instituição.'
  );
}

function showInfoModal(title, content) {
  document.getElementById('modalTitle').textContent = title;
  document.getElementById('modalContent').textContent = content;
  document.getElementById('infoModal').classList.remove('hidden');
}

function closeInfoModal() {
  document.getElementById('infoModal').classList.add('hidden');
}

function hideMessage() {
  document.getElementById('statusMessage').classList.add('hidden');
  document.getElementById('statusMessage').classList.remove('flex');
}

function showLoginMessage(message, isError = false) {
  const panel = document.getElementById('statusMessage');
  const icon = document.getElementById('statusIcon');
  panel.classList.remove('hidden', 'bg-red-50', 'text-red-700', 'bg-gray-50', 'text-gray-700');
  panel.classList.add('flex', isError ? 'bg-red-50' : 'bg-gray-50', isError ? 'text-red-700' : 'text-gray-700');
  icon.className = isError
    ? 'fa-solid fa-circle-exclamation'
    : 'fa-solid fa-circle-notch fa-spin';
  document.getElementById('statusText').textContent = message;
}

async function handleLogin(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const email = form.querySelector('#identifier')?.value.trim();
  const senha = form.querySelector('#password')?.value;
  const submitButton = document.getElementById('submitBtn');

  if (!email || !senha) {
    showLoginMessage('Informe e-mail e senha.', true);
    return;
  }

  hideMessage();
  submitButton.disabled = true;
  document.getElementById('btnText').textContent = 'Entrando...';
  document.getElementById('btnSpinner').classList.remove('hidden');
  showLoginMessage('Verificando credenciais...');

  try {
    const response = await fetch(`${API_URL}/login`, {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: new URLSearchParams({username: email, password: senha}),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || 'Não foi possível entrar.');
    }

    sessionStorage.setItem('paee_token', data.access_token);
    sessionStorage.setItem('paee_usuario', JSON.stringify(data.usuario || {}));
    if (document.getElementById('rememberMe').checked) {
      localStorage.setItem('paee_email', email);
    } else {
      localStorage.removeItem('paee_email');
    }
    window.location.assign(new URL('../tela_inicial.html', window.location.href));
  } catch (error) {
    showLoginMessage(error.message || 'Não foi possível entrar.', true);
  } finally {
    submitButton.disabled = false;
    document.getElementById('btnText').textContent = 'Entrar no Portal';
    document.getElementById('btnSpinner').classList.add('hidden');
  }
}
