async function loadDemoUsers() {
  const panel = document.getElementById('demoUsers');
  const list = document.getElementById('demoUsersList');
  const passwordHint = document.getElementById('demoPasswordHint');
  if (!panel || !list || !passwordHint) return;

  try {
    const response = await fetch('/api/demo-users');
    if (!response.ok) return;
    const data = await response.json();
    if (!Array.isArray(data.usuarios) || !data.usuarios.length || !data.senha_compartilhada) return;

    data.usuarios.forEach(user => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'w-full text-left px-3 py-2 rounded-lg border border-gray-200 hover:border-red-300 hover:bg-red-50 transition-colors';
      button.textContent = `${user.perfil} — ${user.email}`;
      button.addEventListener('click', () => {
        document.getElementById('identifier').value = user.email;
        document.getElementById('password').value = data.senha_compartilhada;
      });
      const item = document.createElement('li');
      item.appendChild(button);
      list.appendChild(item);
    });
    passwordHint.textContent = `Senha comum das contas de demonstração: ${data.senha_compartilhada}`;
    panel.hidden = false;
    panel.classList.remove('hidden');
  } catch {
    panel.hidden = true;
  }
}

loadDemoUsers();
