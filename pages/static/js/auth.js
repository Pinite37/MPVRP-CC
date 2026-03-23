const API_URL  = "http://localhost:8000";
let   authMode = 'login';

document.getElementById('mobile-menu').addEventListener('click', () => {
    document.getElementById('nav-links').classList.toggle('active');
});

// ═══════════════
// UTILITAIRES
// ═══════════════

function showMessage(message, type = 'error') {
    const existing = document.getElementById('msg-banner');
    if (existing) existing.remove();

    const colors = {
        error:   { bg: '#fdf2f2', border: '#e74c3c', text: '#c0392b' },
        success: { bg: '#f0fdf4', border: '#27ae60', text: '#1e8449' },
        info:    { bg: '#eff6ff', border: '#3C27F5', text: '#3C27F5' },
    };
    const c = colors[type] || colors.error;

    const banner = document.createElement('div');
    banner.id = 'msg-banner';
    banner.className = 'msg-banner';
    banner.style.cssText = `
        background:${c.bg}; border:1px solid ${c.border}; color:${c.text};
    `;
    banner.innerText = message;

    const authVisible = document.getElementById('auth-section').style.display !== 'none';
    const anchor = authVisible
        ? document.getElementById('auth-form')
        : document.getElementById('user-section').querySelector('.upload-card');
    anchor.insertAdjacentElement('afterend', banner);

    if (type !== 'info') {
        setTimeout(() => {
            banner.style.opacity = '0';
            setTimeout(() => banner.remove(), 400);
        }, 5000);
    }
}

function setBtn(id, loading, defaultText) {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.disabled  = loading;
    btn.innerText = loading ? "Loading..." : defaultText;
}

function formatDate(isoStr) {
    if (!isoStr) return '—';
    // Format UTC+1
    const normalized = isoStr.replace(' ', 'T').replace(/Z?$/, 'Z');
    const d = new Date(normalized);
    if (isNaN(d)) return isoStr;
    // Format de date international (en-GB) pour une lecture facile
    return d.toLocaleString('en-GB', { timeZone: 'Africa/Porto-Novo' });
}

// AUTH
function switchTab(mode) {
    authMode = mode;
    const existing = document.getElementById('msg-banner');
    if (existing) existing.remove();

    document.getElementById('group-team').style.display = mode === 'register' ? 'block' : 'none';
    document.getElementById('submit-btn').innerText     = mode === 'register' ? "Create Account" : "Login";
    document.getElementById('tab-login').classList.toggle('active',    mode === 'login');
    document.getElementById('tab-register').classList.toggle('active', mode === 'register');
}

async function handleAuth(e) {
    e.preventDefault();
    const email    = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const label    = authMode === 'register' ? "Create Account" : "Login";
    setBtn('submit-btn', true, label);

    if (authMode === 'login') {
        const fd = new FormData();
        fd.append('username', email);
        fd.append('password', password);

        const res = await fetch(`${API_URL}/auth/login`, { method: 'POST', body: fd });
        if (res.ok) {
            const data = await res.json();
            localStorage.setItem('token', data.access_token);
            showUserSection();
        } else {
            setBtn('submit-btn', false, label);
            showMessage("Incorrect email or password.", 'error');
        }

    } else {
        const teamName = document.getElementById('team_name').value.trim();
        if (!teamName) {
            setBtn('submit-btn', false, label);
            return showMessage("Team name is required.", 'error');
        }
        const res = await fetch(`${API_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ team_name: teamName, email, password })
});
        if (res.ok) {
            setBtn('submit-btn', false, label);
            showMessage("Registration successful! You can now login.", 'success');
            setTimeout(() => switchTab('login'), 1500);
        } else {
            const err = await res.json();
            setBtn('submit-btn', false, label);
            showMessage(err.detail || "Team name or email already in use.", 'error');
        }
    }
}


// UPLOAD
async function handleFileUpload() {
    const fileInput = document.getElementById('zip-file');
    const token     = localStorage.getItem('token');

    if (!token)              return showMessage("Session expired. Please login again.", 'error');
    if (!fileInput.files[0]) return showMessage("Please choose a .zip file before starting the evaluation.", 'error');

    setBtn('upload-btn', true, "Start Evaluation");

    const fd = new FormData();
    fd.append('file', fileInput.files[0]);

    const res = await fetch(`${API_URL}/scoring/submit`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: fd
    });

    setBtn('upload-btn', false, "Start Evaluation");

    if (res.ok) {
        const data = await res.json();
        showMessage(`Submission accepted — calculation in progress...`, 'info');
        pollResult(data.submission_id);
        loadHistory();
    } else if (res.status === 401) {
        showMessage("Invalid session. Please login again.", 'error');
        logout();
    } else {
        const err = await res.json();
        showMessage("Error: " + (err.detail || "Upload failed."), 'error');
    }
}

// POLLING
function pollResult(submissionId) {
    const token      = localStorage.getItem('token');
    const maxRetries = 20;
    let   attempts   = 0;

    const interval = setInterval(async () => {
        attempts++;
        try {
            const res = await fetch(`${API_URL}/scoring/result/${submissionId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (res.status === 401) { clearInterval(interval); logout(); return; }

            if (res.ok) {
                const data = await res.json();
                console.log(`[POLLING #${attempts}] is_ready=${data.is_ready} score=${data.total_score}`, data);
                if (data.is_ready) {
                    clearInterval(interval);
                    console.log("[POLLING] Completed — displaying result");
                    const b = document.getElementById('msg-banner');
                    if (b) b.remove();
                    showMessage(
                        `Score calculated: ${data.total_score.toFixed(4)} — ${data.total_valid_instances} valid instances.`,
                        'success'
                    );
                    displayResult(data);
                    loadHistory();
                }
            }
        } catch (err) {
            console.warn(`[POLLING] Attempt ${attempts} failed:`, err);
        }

        if (attempts >= maxRetries) {
            clearInterval(interval);
            const b = document.getElementById('msg-banner');
            if (b) b.remove();
            showMessage("Calculation in progress — please check your history in a few moments.", 'info');
        }
    }, 3000);
}


// AFFICHAGE RÉSULTAT
function displayResult(data) {
    const existing = document.getElementById('result-section');
    if (existing) existing.remove();

    const section = document.createElement('div');
    section.id    = 'result-section';

    section.innerHTML = `
        <h2>Result — Submission #${data.submission_id}</h2>
        <table>
            <thead><tr><th>Metric</th><th>Value</th></tr></thead>
            <tbody>
                <tr><td>Weighted Total Score</td><td><strong>${data.total_score.toFixed(4)}</strong></td></tr>
                <tr><td>Valid Instances</td><td>${data.total_valid_instances}</td></tr>
                <tr><td>Full Feasibility</td><td>${data.is_fully_feasible ? "Yes" : "No"}</td></tr>
            </tbody>
        </table>

        ${data.processor_info ? `
        <details style="margin-top:15px;">
            <summary style="color:#c0392b;">ZIP Structure Report</summary>
            <pre style="
                background:#fdf2f2; border:1px solid #f5b7b1; border-radius:4px;
                padding:12px; font-size:13px; line-height:1.6;
                white-space:pre-wrap; word-break:break-word; margin-top:8px;
            ">${data.processor_info}</pre>
        </details>` : ''}

        <details style="margin-top:15px;">
            <summary>Instance Details (${data.instances_details.length})</summary>
            <table style="margin-top:10px; font-size:15px;">
                <thead>
                    <tr>
                        <th>Instance</th><th>Category</th><th>Feasible</th>
                        <th>Distance</th><th>Transition Cost</th><th>Errors</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.instances_details.map(r => `
                        <tr ${!r.feasible ? 'style="background:#fdf2f2;"' : ''}>
                            <td>${r.instance}</td>
                            <td>${r.category}</td>
                            <td>${r.feasible ? "✅" : "❌"}</td>
                            <td>${r.distance ?? "—"}</td>
                            <td>${r.transition_cost ?? "—"}</td>
                            <td style="color:#c0392b; font-size:13px;">
                                ${r.errors.length > 0 ? r.errors.join('<br>') : "—"}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </details>
    `;

    const uploadCard = document.querySelector('.upload-card');
    uploadCard.insertAdjacentElement('afterend', section);
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ═══════════════
// HISTORIQUE
// ═══════════════

async function loadHistory() {
    const token = localStorage.getItem('token');
    const res   = await fetch(`${API_URL}/scoring/history`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!res.ok) { if (res.status === 401) logout(); return; }

    const data = await res.json();
    document.getElementById('team-name-display').innerText = data.team_name;

    const navTeam = document.getElementById('nav-team-name');
    if (navTeam) navTeam.innerText = `👤 ${data.team_name}`;

    const tbody = document.getElementById('history-body');

    if (data.history.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align:center; color:#888; font-style:italic;">
                    No submissions yet.
                </td>
            </tr>`;
        return;
    }

    tbody.innerHTML = data.history.map(sub => `
        <tr>
            <td>Submission ${sub.submission_number}</td>
            <td>${formatDate(sub.submitted_at)}</td>
            <td><strong>${sub.score.toFixed(2)}</strong></td>
            <td>${sub.valid_instances}</td>
            <td>
                ${sub.is_fully_feasible
                    ? '<span class="badge badge-ok">Validated</span>'
                    : '<span class="badge badge-err">Incomplete</span>'
                }
            </td>
            <td>
                <button
                    id="details-btn-${sub.submission_id}"
                    class="btn-details"
                    onclick="loadAndDisplayDetails(${sub.submission_id})"
                >Details</button>
            </td>
        </tr>
    `).join('');
}


// DÉTAILS DEPUIS L'HISTORIQUE
async function loadAndDisplayDetails(submissionId) {
    const token = localStorage.getItem('token');
    const btn   = document.getElementById(`details-btn-${submissionId}`);

    if (btn) { btn.disabled = true; btn.innerText = "Loading..."; }

    try {
        const res = await fetch(`${API_URL}/scoring/result/${submissionId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (res.status === 401) { logout(); return; }
        if (res.status === 403) { showMessage("Unauthorized access to this submission.", 'error'); return; }
        if (!res.ok)            { showMessage("Unable to load details.", 'error'); return; }

        const data = await res.json();
        console.log(`[DETAILS #${submissionId}] is_ready=${data.is_ready}`, data);

        if (!data.is_ready) {
            showMessage("This submission is still being processed. Please try again in a moment.", 'info');
            return;
        }
        displayResult(data);

    } catch (err) {
        showMessage("Network error while loading details.", 'error');
        console.error(err);
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = "Details"; }
    }
}


// SESSION
function showUserSection() {
    document.getElementById('auth-section').style.display = 'none';
    document.getElementById('user-section').style.display = 'block';
    document.getElementById('nav-logout-li').style.display = 'inline';
    document.getElementById('nav-team-name').style.display = 'inline';
    loadHistory();
}

function logout() {
    localStorage.removeItem('token');
    window.location.replace(window.location.pathname);
}

window.addEventListener('DOMContentLoaded', () => {
    if (localStorage.getItem('token')) {
        showUserSection();
    }
});