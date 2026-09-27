// ==========================================================
// Fatec - Indaiatuba | Acesso ao Portal
// Lógica de interação da tela de login
// ==========================================================

function togglePasswordVisibility() {
  const passwordInput = document.getElementById('password');
  const eyeIcon = document.getElementById('passwordEyeIcon');

  if (passwordInput.type === 'password') {
    passwordInput.type = 'text';
    eyeIcon.classList.remove('fa-eye');
    eyeIcon.classList.add('fa-eye-slash');
  } else {
    passwordInput.type = 'password';
    eyeIcon.classList.remove('fa-eye-slash');
    eyeIcon.classList.add('fa-eye');
  }
}

function showMessage(type, text) {
  const box = document.getElementById('statusMessage');
  const icon = document.getElementById('statusIcon');
  const label = document.getElementById('statusText');

  box.className = "mb-5 p-3.5 rounded-xl text-xs sm:text-sm transition-all duration-300 flex items-center gap-3 ";

  if (type === 'error') {
    box.classList.add('bg-red-50', 'text-red-700', 'border', 'border-red-200');
    icon.className = 'fa-solid fa-triangle-exclamation text-base text-red-600';
  } else if (type === 'success') {
    box.classList.add('bg-emerald-50', 'text-emerald-800', 'border', 'border-emerald-200');
    icon.className = 'fa-solid fa-circle-check text-base text-emerald-600';
  } else {
    box.classList.add('bg-blue-50', 'text-blue-800', 'border', 'border-blue-200');
    icon.className = 'fa-solid fa-circle-info text-base text-blue-600';
  }

  label.innerText = text;
  box.classList.remove('hidden');
}

function hideMessage() {
  document.getElementById('statusMessage').classList.add('hidden');
}

function showInfoModal(title, content) {
  document.getElementById('modalTitle').innerText = title;
  document.getElementById('modalContent').innerText = content;
  document.getElementById('infoModal').classList.remove('hidden');
}

function closeInfoModal() {
  document.getElementById('infoModal').classList.add('hidden');
}

function handleLogin(event) {
  event.preventDefault();
  hideMessage();

  const id = document.getElementById('identifier').value.trim();
  const pwd = document.getElementById('password').value;
  const btnText = document.getElementById('btnText');
  const btnSpinner = document.getElementById('btnSpinner');
  const submitBtn = document.getElementById('submitBtn');

  if (!id || !pwd) {
    showMessage('error', 'Por favor, preencha todos os campos obrigatórios.');
    return;
  }

  btnText.innerText = 'Autenticando...';
  btnSpinner.classList.remove('hidden');
  submitBtn.disabled = true;
  submitBtn.classList.add('opacity-80', 'cursor-wait');

  setTimeout(() => {
    btnText.innerText = 'Entrar no Portal';
    btnSpinner.classList.add('hidden');
    submitBtn.disabled = false;
    submitBtn.classList.remove('opacity-80', 'cursor-wait');

    showMessage('success', 'Credenciais validadas com sucesso! Redirecionando para o ambiente acadêmico...');
  }, 1300);
}

function handleForgotPassword(e) {
  e.preventDefault();
  showInfoModal(
    'Recuperação de Acesso',
    'Para redefinir sua senha acadêmica, informe o e-mail cadastrado ou procure a secretaria acadêmica da Fatec Indaiatuba.'
  );
}

window.addEventListener('click', (e) => {
  const modal = document.getElementById('infoModal');
  if (e.target === modal) {
    closeInfoModal();
  }
});
