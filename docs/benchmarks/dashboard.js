/*
 * dashboard.js — community benchmark dashboard for NeuralMind.
 *
 * Reads ../community-benchmarks.json at page load (one fetch, no backend)
 * and renders: community stat cards, scatter (nodes vs reduction),
 * by-language bars, and a sortable submissions table.
 *
 * Deliberately small: vanilla JS + Chart.js via CDN. No build step, no
 * framework, no analytics. View source = ground truth.
 */

// Text/grid tokens mirror dashboard.css (--text-dim / --border tones).
const PALETTE = {
    text: '#97a3ba',
    faint: '#67748f',
    grid: 'rgba(151, 163, 186, 0.10)',
    tooltipBg: '#0c1322',
    tooltipBorder: '#28395c',
    error: '#f87171',
};

// Categorical slots validated (CVD separation + contrast) against the dark
// card surface #0e1626. Assignment is by FIXED slot order per language —
// never cycled — so a language keeps its color across both charts and
// across dataset growth. One adjacent pair sits in the CVD floor band,
// which is why every slot also carries a distinct point shape (secondary
// encoding) on the scatter.
const SLOTS = [
    { color: '#3987e5', point: 'circle' },
    { color: '#199e70', point: 'rect' },
    { color: '#c98500', point: 'triangle' },
    { color: '#008300', point: 'rectRot' },
    { color: '#9085e9', point: 'crossRot' },
    { color: '#e66767', point: 'star' },
    { color: '#d55181', point: 'rectRounded' },
    { color: '#d95926', point: 'cross' },
];
const LANGUAGE_SLOT = {
    Python: 0,
    JavaScript: 1,
    TypeScript: 2,
    Go: 3,
    Rust: 4,
    Java: 5,
    'C#': 6,
    'C++': 7,
};
// Languages beyond the eight slots fold into a deliberate neutral —
// identity then comes from the legend, point shape, and the table.
const OTHER_SLOT = { color: '#8892a8', point: 'triangle' };

function slotFor(language) {
    const idx = LANGUAGE_SLOT[language];
    return idx === undefined ? OTHER_SLOT : SLOTS[idx];
}

const fmtNumber = (n) => new Intl.NumberFormat('en-US').format(n);
const fmtRatio = (n) => `${n.toFixed(1)}×`;

const TOOLTIP_STYLE = {
    backgroundColor: PALETTE.tooltipBg,
    borderColor: PALETTE.tooltipBorder,
    borderWidth: 1,
    titleColor: '#e7ecf5',
    bodyColor: PALETTE.text,
    padding: 10,
    cornerRadius: 8,
    boxPadding: 4,
};

if (typeof Chart !== 'undefined') {
    Chart.defaults.color = PALETTE.text;
    Chart.defaults.borderColor = PALETTE.grid;
    Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
}

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
                <div class="stat-sub">Be the first — see "Add your repo's numbers" below.</div>
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
        note.textContent = `Note: only ${entries.length} submission${entries.length === 1 ? '' : 's'} so far — this dataset is in its early days. Numbers will firm up as more repos contribute. See "Add your repo's numbers" below to be one of them.`;
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

    const datasets = Object.entries(dataByLang).map(([lang, points]) => {
        const slot = slotFor(lang);
        return {
            label: lang,
            data: points,
            backgroundColor: slot.color,
            borderColor: slot.color,
            pointStyle: slot.point,
            pointRadius: 6,
            pointHoverRadius: 9,
            borderWidth: 2,
        };
    });

    new Chart(ctx, {
        type: 'scatter',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        pointStyleWidth: 12,
                        color: PALETTE.text,
                        padding: 16,
                    },
                },
                tooltip: {
                    ...TOOLTIP_STYLE,
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
                    ticks: { color: PALETTE.faint },
                    grid: { color: PALETTE.grid },
                },
                y: {
                    title: { display: true, text: 'Avg reduction ratio (×)', color: PALETTE.text },
                    ticks: { color: PALETTE.faint },
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

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: langs,
            datasets: [{
                label: 'Avg reduction ratio',
                data: averages,
                backgroundColor: langs.map(l => slotFor(l).color),
                borderRadius: 4,
                maxBarThickness: 46,
                categoryPercentage: 0.6,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    ...TOOLTIP_STYLE,
                    callbacks: {
                        title: (items) => items[0].label,
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
                    ticks: {
                        color: PALETTE.text,
                        // Two-line tick: language name + honest sample size.
                        callback: function (value) {
                            const lang = this.getLabelForValue(value);
                            return [lang, `n=${byLang[lang].count}`];
                        },
                    },
                },
                y: {
                    title: { display: true, text: 'Avg reduction ratio (×)', color: PALETTE.text },
                    ticks: { color: PALETTE.faint },
                    grid: { color: PALETTE.grid },
                    beginAtZero: true,
                },
            },
        },
    });
}

// ── sortable submissions table ────────────────────────────────────────────

let tableEntries = [];
const sortState = { key: 'date_submitted', dir: 'desc' };

function compareEntries(a, b, key, numeric) {
    const av = a[key];
    const bv = b[key];
    if (av === undefined || av === null || av === '') return 1;  // blanks last
    if (bv === undefined || bv === null || bv === '') return -1;
    if (numeric) return av - bv;
    return String(av).localeCompare(String(bv), 'en', { sensitivity: 'base' });
}

function renderTable() {
    const body = document.getElementById('submissions-body');
    if (tableEntries.length === 0) {
        body.innerHTML = '<tr><td colspan="10" class="placeholder">No submissions yet.</td></tr>';
        return;
    }
    const th = document.querySelector(`#submissions-table th[data-key="${sortState.key}"]`);
    const numeric = th && th.dataset.type === 'num';
    const sorted = [...tableEntries].sort((a, b) => {
        const cmp = compareEntries(a, b, sortState.key, numeric);
        return sortState.dir === 'asc' ? cmp : -cmp;
    });

    document.querySelectorAll('#submissions-table th').forEach(el => {
        if (el.dataset.key === sortState.key) {
            el.setAttribute('aria-sort', sortState.dir === 'asc' ? 'ascending' : 'descending');
        } else {
            el.setAttribute('aria-sort', 'none');
        }
    });

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

function initSorting() {
    document.querySelectorAll('#submissions-table th[data-key]').forEach(th => {
        th.addEventListener('click', () => {
            const key = th.dataset.key;
            if (sortState.key === key) {
                sortState.dir = sortState.dir === 'asc' ? 'desc' : 'asc';
            } else {
                sortState.key = key;
                // Numbers read best big-first; text reads best A–Z.
                sortState.dir = th.dataset.type === 'num' ? 'desc' : 'asc';
            }
            renderTable();
        });
    });
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
        note.style.color = PALETTE.error;
    }
    const body = document.getElementById('submissions-body');
    if (body) {
        body.innerHTML = `<tr><td colspan="10" class="placeholder">Load failed: ${escapeHtml(err.message)}.</td></tr>`;
    }
}

(async function init() {
    let entries;
    try {
        entries = await loadEntries();
    } catch (err) {
        console.error(err);
        renderError(err);
        return;
    }
    renderHero(entries);
    tableEntries = entries;
    initSorting();
    renderTable();
    // Charts are progressive enhancement: if Chart.js failed to load or
    // there's nothing to plot, hide the chart cards — the stat cards and
    // table above carry the full dataset either way.
    if (entries.length > 0 && typeof Chart !== 'undefined') {
        try {
            renderScatter(entries);
            renderByLanguage(entries);
        } catch (err) {
            console.error(err);
        }
    } else {
        document.querySelectorAll('.chart-card').forEach(el => { el.style.display = 'none'; });
    }
})();
