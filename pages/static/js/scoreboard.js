const API_URL = window.APP_CONFIG?.API_URL || "https://mpvrppythonapi.pinite37.me";

// ── Nav mobile ───────────────────────────────────────────
document.getElementById('mobile-menu').addEventListener('click', () => {
    document.getElementById('nav-links').classList.toggle('active');
});

// ── Session (logout conditionnel) ────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    if (localStorage.getItem('token')) {
        // On récupère le nom d'Team depuis l'historique pour l'afficher dans la nav
        fetchTeamName();
        document.getElementById('nav-logout-li').style.display = 'inline';
    }
    loadLeaderboard();
});

async function fetchTeamName() {
    const token = localStorage.getItem('token');
    if (!token) return;
    try {
        const res = await fetch(`${API_URL}/scoring/history`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
            const data = await res.json();
            const el = document.getElementById('nav-team-name');
            el.innerText = `👤 ${data.team_name}`;
            el.style.display = 'inline';
        } else if (res.status === 401) {
            logout();
        }
    } catch (_) {}
}

function logout() {
    localStorage.removeItem('token');
    window.location.replace(window.location.pathname);
}

// ── Leaderboard ──────────────────────────────────────────
async function loadLeaderboard() {
    const stateEl   = document.getElementById('lb-state');
    const tableEl   = document.getElementById('leaderboard-table');
    const tbody     = document.getElementById('leaderboard-body');
    const countEl   = document.getElementById('lb-count');
    const refreshBtn = document.getElementById('refresh-btn');

    stateEl.className   = 'lb-state';
    stateEl.innerText   = 'Loading…';
    stateEl.style.display = 'block';
    tableEl.style.display = 'none';
    refreshBtn.disabled = true;

    try {
        const res = await fetch(`${API_URL}/scoreboard/`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();

        if (data.length === 0) {
            stateEl.innerText = "No submissions recorded yet. Be the first team on the leaderboard!";
            countEl.innerText = '';
            return;
        }

        const medals = { 1: '🥇', 2: '🥈', 3: '🥉' };

        tbody.innerHTML = data.map(row => `
            <tr class="${row.rank <= 3 ? `rank-${row.rank}` : ''}">
                <td>${medals[row.rank] ?? row.rank}</td>
                <td>${row.team}</td>
                <td><strong>${row.score.toFixed(2)}</strong></td>
                <td>${row.instances_validated}</td>
                <td>${formatDate(row.last_submission)}</td>
            </tr>
        `).join('');

        countEl.innerText = `${data.length} Team${data.length > 1 ? 's' : ''} on the scoreboard`;
        stateEl.style.display = 'none';
        tableEl.style.display = 'table';

    } catch (err) {
        stateEl.className = 'lb-state lb-error';
        stateEl.innerText = "Unable to load leaderboard. Check the server is reachable.";
        console.error('Leaderboard error:', err);
    } finally {
        refreshBtn.disabled = false;
    }
}

function formatDate(isoStr) {
    if (!isoStr) return '—';
    const normalized = isoStr.replace(' ', 'T').replace(/Z?$/, 'Z');
    const d = new Date(normalized);
    if (isNaN(d)) return isoStr;
    return d.toLocaleString('fr-FR', { timeZone: 'Africa/Porto-Novo' });
}