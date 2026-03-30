const API_URL = window.APP_CONFIG?.API_URL;

// ── Nav mobile ───────────────────────────────────────────
document.getElementById('mobile-menu').addEventListener('click', () => {
    document.getElementById('nav-links').classList.toggle('active');
});

// ── Init ─────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    loadLeaderboard();
});

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
        const res = await fetch(`${API_URL}/scoreboard`);
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

    try {
        const d = new Date(isoStr);
        if (isNaN(d.getTime())) return isoStr;

        const months = ['January', 'February', 'March', 'April', 'May', 'June',
                        'July', 'August', 'September', 'October', 'November', 'December'];
        const month = months[d.getUTCMonth()];
        const day = d.getUTCDate();
        const year = d.getUTCFullYear();

        let hours = d.getUTCHours();
        const minutes = String(d.getUTCMinutes()).padStart(2, '0');
        const ampm = hours >= 12 ? 'PM' : 'AM';
        hours = hours % 12 || 12;

        return `${month} ${day}, ${year} ${hours}:${minutes} ${ampm} (UTC)`;
    } catch (err) {
        return isoStr;
    }
}