const API_URL = window.APP_CONFIG?.API_URL;
const KNOWN_SUBMITTERS_KEY = 'mpvrp_known_submitter_emails';

document.getElementById('mobile-menu').addEventListener('click', () => {
    document.getElementById('nav-links').classList.toggle('active');
});

function showMessage(message, type = 'error') {
    const existing = document.getElementById('msg-banner');
    if (existing) existing.remove();

    const colors = {
        error: { bg: '#fdf2f2', border: '#e74c3c', text: '#c0392b' },
        success: { bg: '#f0fdf4', border: '#27ae60', text: '#1e8449' },
        info: { bg: '#eff6ff', border: '#3C27F5', text: '#3C27F5' },
    };
    const c = colors[type] || colors.error;

    const banner = document.createElement('div');
    banner.id = 'msg-banner';
    banner.className = 'msg-banner';
    banner.style.cssText = `background:${c.bg}; border:1px solid ${c.border}; color:${c.text};`;
    banner.innerText = message;

    const anchor = document.querySelector('.upload-card');
    anchor.insertAdjacentElement('afterend', banner);

    if (type !== 'info') {
        setTimeout(() => {
            banner.style.opacity = '0';
            setTimeout(() => banner.remove(), 400);
        }, 5000);
    }
}

function setBtn(loading) {
    const btn = document.getElementById('upload-btn');
    btn.disabled = loading;
    btn.innerText = loading ? 'Submitting...' : 'Start evaluation';
}

function getKnownSubmitterEmails() {
    try {
        return JSON.parse(localStorage.getItem(KNOWN_SUBMITTERS_KEY) || '[]');
    } catch (_) {
        return [];
    }
}

function rememberSubmitterEmail(email) {
    const normalized = email.trim().toLowerCase();
    if (!normalized) return;
    const emails = new Set(getKnownSubmitterEmails());
    emails.add(normalized);
    localStorage.setItem(KNOWN_SUBMITTERS_KEY, JSON.stringify(Array.from(emails)));
}

function isKnownSubmitter(email) {
    const normalized = email.trim().toLowerCase();
    return getKnownSubmitterEmails().includes(normalized);
}

async function handleFileUpload(event) {
    event.preventDefault();

    const nameInput = document.getElementById('name');
    const emailInput = document.getElementById('email');
    const fileInput = document.getElementById('zip-file');

    const name = nameInput.value.trim();
    const email = emailInput.value.trim().toLowerCase();
    const file = fileInput.files[0];

    if (!email) return showMessage('Email is required.', 'error');
    if (!file) return showMessage('Please choose a .zip file before starting the evaluation.', 'error');
    if (!file.name.toLowerCase().endsWith('.zip')) return showMessage('Only .zip files are accepted.', 'error');
    if (!isKnownSubmitter(email) && !name) {
        return showMessage('For a first submission, please provide your name and email.', 'error');
    }

    setBtn(true);

    const fd = new FormData();
    fd.append('file', file);
    fd.append('email', email);
    if (name) fd.append('name', name);

    try {
        const res = await fetch(`${API_URL}/scoring/submit`, {
            method: 'POST',
            body: fd,
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Upload failed.');
        }

        const data = await res.json();
        rememberSubmitterEmail(email);
        showMessage(`Submission accepted. Score: ${Number(data.total_score).toFixed(2)}.`, 'success');
        displayResult(data);
    } catch (err) {
        showMessage(`Error: ${err.message}`, 'error');
    } finally {
        setBtn(false);
    }
}

function displayResult(data) {
    const existing = document.getElementById('result-section');
    if (existing) existing.remove();

    const section = document.createElement('div');
    section.id = 'result-section';
    section.className = 'result-section';

    section.innerHTML = `
        <div class="result-card">
            <h2>Result - Submission #${data.submission_id}</h2>

            <table class="result-metrics">
                <thead>
                    <tr>
                        <th>Metric</th><th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td>Weighted total score</td><td><strong>${Number(data.total_score).toFixed(4)}</strong></td></tr>
                    <tr><td>Valid solutions</td><td>${data.total_valid_instances}</td></tr>
                    <tr><td>Full feasibility</td><td>${data.is_fully_feasible ? 'Yes' : 'No'}</td></tr>
                </tbody>
            </table>

            ${data.processor_info ? `
            <details class="result-details result-details--warning">
                <summary>ZIP structure report</summary>
                <pre class="result-pre">${data.processor_info}</pre>
            </details>` : ''}

            <details class="result-details">
                <summary>Instance details (${data.instances_details.length})</summary>
                <table class="result-instances">
                    <thead>
                        <tr>
                            <th>Instance</th><th>Category</th><th>Feasible</th>
                            <th>Distance</th><th>Transition cost</th><th>Errors</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.instances_details.map(r => `
                            <tr class="${!r.feasible ? 'result-row--invalid' : ''}">
                                <td>${r.instance}</td>
                                <td>${r.category}</td>
                                <td>${r.feasible ? 'Yes' : 'No'}</td>
                                <td>${r.distance ?? '—'}</td>
                                <td>${r.transition_cost ?? '—'}</td>
                                <td class="result-errors">
                                    ${r.errors.length > 0 ? r.errors.join('<br>') : '—'}
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </details>
        </div>
    `;

    const uploadCard = document.querySelector('.upload-card');
    uploadCard.insertAdjacentElement('afterend', section);
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
