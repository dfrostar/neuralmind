/*
 * dashboard.js — community benchmark dashboard for NeuralMind.
 *
 * Reads ../community-benchmarks.json at page load (one fetch, no backend)
 * and renders three views: hero stats, scatter (nodes vs reduction),
 * by-language bars, and a sortable submissions table.
 *
 * Deliberately small: vanilla JS + Chart.js via CDN. No build step, no
 * framework, no analytics. View source = ground truth.
 */

const PALETTE = {
    primary: '#667eea',
    secondary: '#764ba2',
    grid: 'rgba(102, 126, 234, 0.1)',
    text: '#444',
};

// Language colors deterministic across runs so the bar chart and scatter
// agree on what color Python is.
const LANGUAGE_COLORS = {
    Python: '#3776ab',
    JavaScript: '#f7df1e',
    TypeScript: '#3178c6',
    Go: '#00add8',
    Rust: '#dea584',
    Java: '#b07219',
    'C#': '#178600',
    Ruby: '#cc342d',
    PHP: '#777bb4',
    'C++': '#f34b7d',
    Mixed: '#888',
    Other: '#aaa',
};

const fmtNumber = (n) => new Intl.NumberFormat('en-US').format(n);
const fmtRatio = (n) => `${n.toFixed(1)}×`;

async function loadEntries() {
    const res = await fetch('../community-benchmarks.json', { cache: 'no-store' });
    if (!res.ok) {
        throw new Error(`Failed to load benchmarks: ${res.status}`);
    }
    const doc = await res.json();
    return doc.entries || [];
}

function renderHero(entries) {
    const container = document.getElementById('hero-stats');
    const note = document.getElementById('sample-note');
    container.innerHTML = '';

    if (entries.length === 0) {
        container.innerHTML = `
            <div class="stat-card">
                <div class="stat-number">—</div>
                <div class="stat-label">No submissions yet</div>
                <div class="stat-sub">Be the first — see "Add your numbers" below.</div>
            </div>`;
        note.textContent = '';
        return;
    }

    const ratios = entries.map(e => e.avg_reduction_ratio).sort((a, b) => a - b);
    const median = ratios.length % 2 === 1
        ? ratios[(ratios.length - 1) / 2]
        : (ratios[ratios.length / 2 - 1] + ratios[ratios.length / 2]) / 2;
    const min = ratios[0];
    const max = ratios[ratios.length - 1];
    const languages = new Set(entries.map(e => e.language));
    const models = new Set(entries.map(e => e.model).filter(Boolean));
    const nodeTotal = entries.reduce((s, e) => s + (e.nodes || 0), 0);

    const cards = [
        {
            value: fmtNumber(entries.length),
            label: 'Submissions',
            sub: `Across ${languages.size} language${languages.size === 1 ? '' : 's'}`,
        },
        {
            value: fmtRatio(median),
            label: 'Median reduction',
            sub: `Range ${fmtRatio(min)} – ${fmtRatio(max)}`,
        },
        {
            value: fmtNumber(nodeTotal),
            label: 'Total nodes indexed',
            sub: 'Across all reported repos',
        },
        {
            value: fmtNumber(models.size),
            label: 'Models covered',
            sub: [...models].slice(0, 3).join(', ') + (models.size > 3 ? '…' : ''),
        },
    ];

    container.innerHTML = cards.map(c => `
        <div class="stat-card">
            <div class="stat-number">${c.value}</div>
            <div class="stat-label">${c.label}</div>
            <div class="stat-sub">${c.sub}</div>
        </div>
    `).join('');

    // Honest sample-size note. With small N, say so.
    if (entries.length < 5) {
        note.textContent = `Note: only ${entries.length} submission${entries.length === 1 ? '' : 's'} so far — this dataset is in its early days. Numbers will firm up as more repos contribute. See "Add your numbers" below to be one of them.`;
    } else if (entries.length < 20) {
        note.textContent = `Note: ${entries.length} submissions so far — enough for directional signal across languages and repo sizes, not yet enough to draw confident conclusions on rare combinations.`;
    } else {
        note.textContent = `${entries.length} submissions across ${languages.size} languages — large enough that the by-language averages below are statistically meaningful.`;
    }
}

function renderScatter(entries) {
    const ctx = document.getElementById('scatter');
    const dataByLang = {};
    entries.forEach(e => {
        if (!dataByLang[e.language]) dataByLang[e.language] = [];
        dataByLang[e.language].push({
            x: e.nodes,
            y: e.avg_reduction_ratio,
            project: e.project_name,
            wakeup: e.avg_wakeup_tokens,
            query: e.avg_query_tokens,
            model: e.model || 'unspecified',
        });
    });

    const datasets = Object.entries(dataByLang).map(([lang, points]) => ({
        label: lang,
        data: points,
        backgroundColor: LANGUAGE_COLORS[lang] || '#888',
        borderColor: LANGUAGE_COLORS[lang] || '#888',
        pointRadius: 8,
        pointHoverRadius: 10,
    }));

    new Chart(ctx, {
        type: 'scatter',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const d = ctx.raw;
                            const parts = [
                                `${d.project} (${ctx.dataset.label})`,
                                `Nodes: ${fmtNumber(d.x)}`,
                                `Reduction: ${fmtRatio(d.y)}`,
                            ];
                            if (d.wakeup) parts.push(`Wakeup: ${d.wakeup} tok`);
                            if (d.query) parts.push(`Query: ${d.query} tok`);
                            parts.push(`Model: ${d.model}`);
                            return parts;
                        },
                    },
                },
            },
            scales: {
                x: {
                    type: 'logarithmic',
                    title: { display: true, text: 'Graph node count (log scale)', color: PALETTE.text },
                    grid: { color: PALETTE.grid },
                },
                y: {
                    title: { display: true, text: 'Avg reduction ratio (×)', color: PALETTE.text },
                    grid: { color: PALETTE.grid },
                    beginAtZero: true,
                },
            },
        },
    });
}

function renderByLanguage(entries) {
    const ctx = document.getElementById('by-language');
    const byLang = {};
    entries.forEach(e => {
        if (!byLang[e.language]) byLang[e.language] = { sum: 0, count: 0 };
        byLang[e.language].sum += e.avg_reduction_ratio;
        byLang[e.language].count += 1;
    });

    const langs = Object.keys(byLang).sort((a, b) =>
        (byLang[b].sum / byLang[b].count) - (byLang[a].sum / byLang[a].count)
    );
    const averages = langs.map(l => byLang[l].sum / byLang[l].count);
    const counts = langs.map(l => byLang[l].count);

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: langs,
            datasets: [{
                label: 'Avg reduction ratio',
                data: averages,
                backgroundColor: langs.map(l => LANGUAGE_COLORS[l] || '#888'),
                borderRadius: 6,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const lang = ctx.label;
                            const avg = ctx.raw;
                            const n = byLang[lang].count;
                            return `${fmtRatio(avg)} avg · n=${n} submission${n === 1 ? '' : 's'}`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    grid: { display: false },
                },
                y: {
                    title: { display: true, text: 'Avg reduction ratio (×)', color: PALETTE.text },
                    grid: { color: PALETTE.grid },
                    beginAtZero: true,
                },
            },
        },
    });
}

function renderTable(entries) {
    const body = document.getElementById('submissions-body');
    if (entries.length === 0) {
        body.innerHTML = '<tr><td colspan="10" class="placeholder">No submissions yet.</td></tr>';
        return;
    }
    const sorted = [...entries].sort((a, b) =>
        (b.date_submitted || '').localeCompare(a.date_submitted || '')
    );
    body.innerHTML = sorted.map(e => `
        <tr>
            <td>${escapeHtml(e.project_name)}</td>
            <td>${escapeHtml(e.language)}</td>
            <td class="num">${fmtNumber(e.nodes)}</td>
            <td class="num"><strong>${fmtRatio(e.avg_reduction_ratio)}</strong></td>
            <td class="num">${e.avg_wakeup_tokens ? fmtNumber(e.avg_wakeup_tokens) : '—'}</td>
            <td class="num">${e.avg_query_tokens ? fmtNumber(e.avg_query_tokens) : '—'}</td>
            <td>${escapeHtml(e.model || '—')}</td>
            <td>${e.submitted_by ? `<a href="https://github.com/${escapeHtml(e.submitted_by)}">@${escapeHtml(e.submitted_by)}</a>` : '—'}</td>
            <td>${escapeHtml(e.date_submitted || '')}</td>
            <td class="notes">${escapeHtml(e.notes || '')}</td>
        </tr>
    `).join('');
}

// Minimal escaping — entries come from a schema-validated JSON file
// in our own repo, but treat the data as untrusted anyway because the
// dashboard JSON might be served from a fork in the future.
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function renderError(err) {
    const note = document.getElementById('sample-note');
    if (note) {
        note.textContent = `Couldn't load benchmark data: ${err.message}. View the raw JSON on GitHub instead.`;
        note.style.color = '#c0392b';
        note.style.fontStyle = 'normal';
    }
    const body = document.getElementById('submissions-body');
    if (body) {
        body.innerHTML = `<tr><td colspan="10" class="placeholder">Load failed: ${escapeHtml(err.message)}.</td></tr>`;
    }
}

(async function init() {
    try {
        const entries = await loadEntries();
        renderHero(entries);
        if (entries.length > 0) {
            renderScatter(entries);
            renderByLanguage(entries);
        }
        renderTable(entries);
    } catch (err) {
        console.error(err);
        renderError(err);
    }
})();
