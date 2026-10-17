const dateElement = document.getElementById('date');

if (dateElement) {
    dateElement.textContent = new Intl.DateTimeFormat('pt-BR', {
        dateStyle: 'full'
    }).format(new Date());
}

document.querySelectorAll('form[data-demo]').forEach((form) => {
    form.addEventListener('submit', (event) => {
        event.preventDefault();

        if (form.reportValidity()) {
            form.querySelector('.message').textContent = form.dataset.demo;
        }
    });
});

const search = document.getElementById('search');
const filter = document.getElementById('filter');

function updateTickets() {
    if (!search) return;

    document.querySelectorAll('#tickets tbody tr').forEach((row) => {
        const matchesSearch = row.textContent.toLowerCase().includes(search.value.toLowerCase());
        const matchesFilter = !filter.value || row.cells[4].textContent.trim() === filter.value;
        row.hidden = !(matchesSearch && matchesFilter);
    });
}

search?.addEventListener('input', updateTickets);
filter?.addEventListener('change', updateTickets);

document.querySelectorAll('[data-ticket]').forEach((button) => {
    button.addEventListener('click', () => {
        alert('Chamado #' + button.dataset.ticket + '\nDetalhamento depende de integração com o backend.');
    });
});
