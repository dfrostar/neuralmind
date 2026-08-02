/**
 * dashboard.js — Agency OS read-only dashboard frontend.
 *
 * Fetches /api/dashboard/full and renders all views. Tab navigation
 * switches between overview, memory, ingestion, performance, queries,
 * and communities. Refresh button re-fetches.
 */

(function () {
  'use strict';

  let dashboardData = null;

  // Fetch dashboard data from the API
  async function fetchDashboard() {
    const resp = await fetch('/api/dashboard/full');
    if (!resp.ok) {
      throw new Error(`Dashboard API returned ${resp.status}: ${resp.statusText}`);
    }
    return resp.json();
  }

  // Format helpers
  function fmtNumber(n) {
    if (n === null || n === undefined) return '—';
    if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return String(n);
  }

  function fmtTimestamp(ts) {
    if (!ts) return '—';
    try {
      const d = new Date(ts * 1000);
      const now = Date.now();
      const diff = now - d.getTime();
      if (diff < 60000) return 'just now';
      if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
      if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago';
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return '—';
    }
  }

  function fmtRatio(r) {
    if (!r) return '—';
    return r.toFixed(1) + '×';
  }

  function fmtTokens(t) {
    if (!t) return '—';
    return fmtNumber(t);
  }

  // Render all views
  function render(data) {
    dashboardData = data;
    renderOverview(data);
    renderSynapses(data);
    renderIngestion(data);
    renderPerformance(data);
    renderQueries(data);
    renderCommunities(data);
    renderAgentOS(data);
    updateTimestamp(data.generated_at);
  }

  // Overview cards
  function renderOverview(data) {
    const status = data.status || {};
    const savings = data.savings || {};
    const memory = data.synapses || {};
    const ingestion = data.ingestion || {};

    // Project status
    const built = status.built;
    const statusEl = document.getElementById('status-built');
    statusEl.innerHTML = built
      ? '<span class="status-dot live"></span> Built'
      : '<span class="status-dot dead"></span> Not Built';
    statusEl.className = 'metric-value ' + (built ? 'good' : 'bad');

    setText('status-backend', status.backend || '—');
    setText('status-nodes', fmtNumber(status.nodes));
    setText('status-communities', fmtNumber(status.communities));

    // Savings
    const ratio = savings.avg_reduction_ratio;
    const ratioEl = document.getElementById('savings-ratio');
    ratioEl.textContent = fmtRatio(ratio);
    ratioEl.className = 'metric-value ' + (ratio >= 20 ? 'good' : ratio >= 10 ? 'warn' : '');

    setText('savings-tokens', fmtTokens(savings.total_tokens_saved));
    setText('savings-queries', fmtNumber(savings.total_queries));
    setText('savings-baseline', '50K tokens/query');

    // Memory
    setText('memory-namespace', memory.namespace || 'personal');
    setText('memory-edges', fmtNumber(memory.total_edges));
    setText('memory-transitions', fmtNumber(memory.total_transitions));
    setText('memory-ltp', fmtNumber(memory.ltp_count));

    // Ingestion
    setText('ingestion-nodes', fmtNumber(ingestion.total_doc_nodes));
    const fwCount = ingestion.frameworks ? Object.keys(ingestion.frameworks).length : 0;
    setText('ingestion-frameworks', fwCount);
    setText('ingestion-last', fmtTimestamp(ingestion.last_ingested_at));

    // Project name
    setText('project-name', status.project || '');
  }

  // Synapses / Memory
  function renderSynapses(data) {
    const memory = data.synapses || {};

    // Namespaces
    const nsList = document.getElementById('namespaces-list');
    const namespaces = memory.namespaces || {};
    if (Object.keys(namespaces).length === 0) {
      nsList.innerHTML = '<div class="empty-state">No namespace data</div>';
    } else {
      nsList.innerHTML = Object.entries(namespaces)
        .map(([ns, info]) => `
          <div class="list-item">
            <span class="list-label">${escapeHtml(ns)}</span>
            <span class="list-meta">${fmtNumber(info.edges)} edges · ${fmtNumber(info.transitions)} trans</span>
          </div>
        `).join('');
    }

    // Top edges
    const edgesList = document.getElementById('top-edges-list');
    const topEdges = memory.top_edges || [];
    if (topEdges.length === 0) {
      edgesList.innerHTML = '<div class="empty-state">No synapse edges yet — run queries to build associations</div>';
    } else {
      edgesList.innerHTML = topEdges
        .map(e => `
          <div class="list-item">
            <span class="list-label">${escapeHtml(e.a)} → ${escapeHtml(e.b)}</span>
            <span class="list-meta">weight ${e.weight} · count ${e.count}</span>
          </div>
        `).join('');
    }
  }

  // Ingestion
  function renderIngestion(data) {
    const ingestion = data.ingestion || {};

    // Frameworks
    const fwList = document.getElementById('frameworks-list');
    const frameworks = ingestion.frameworks || {};
    if (Object.keys(frameworks).length === 0) {
      fwList.innerHTML = '<div class="empty-state">No frameworks ingested</div>';
    } else {
      fwList.innerHTML = Object.entries(frameworks)
        .map(([fw, count]) => `
          <div class="list-item">
            <span class="list-label">${escapeHtml(fw)}</span>
            <span class="list-meta">${fmtNumber(count)} nodes</span>
          </div>
        `).join('');
    }

    // Recent ingestion events
    const evList = document.getElementById('ingestion-list');
    const events = ingestion.ingested_files || [];
    if (events.length === 0) {
      evList.innerHTML = '<div class="empty-state">No ingestion events</div>';
    } else {
      evList.innerHTML = events
        .slice()
        .reverse()
        .map(e => `
          <div class="list-item">
            <span class="list-label">${escapeHtml(e.source || e.action)}</span>
            <span class="list-meta">
              ${escapeHtml(e.framework || '—')} · ${e.node_count} nodes · ${fmtTimestamp(e.timestamp)}
            </span>
          </div>
        `).join('');
    }
  }

  // Performance
  function renderPerformance(data) {
    const perf = data.performance || {};
    const container = document.getElementById('performance-metrics');

    const queries = perf.queries || {};
    const builds = perf.builds || {};

    if (perf.n_events === 0) {
      container.innerHTML = '<div class="empty-state">No metrics data — run queries to populate</div>';
      return;
    }

    let html = '';

    if (queries.n_queries) {
      html += `
        <div class="metric-row">
          <span class="metric-label">Total Queries</span>
          <span class="metric-value">${fmtNumber(queries.n_queries)}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Avg Latency</span>
          <span class="metric-value">${queries.mean_latency_ms ? queries.mean_latency_ms.toFixed(0) + ' ms' : '—'}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Avg Retrieval Reuse</span>
          <span class="metric-value">${queries.mean_retrieval_reuse_rate ? (queries.mean_retrieval_reuse_rate * 100).toFixed(1) + '%' : '—'}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Avg Tokens/Query</span>
          <span class="metric-value">${queries.mean_tokens_used ? fmtNumber(queries.mean_tokens_used) : '—'}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Avg Synapses Activated</span>
          <span class="metric-value">${queries.mean_synapses_activated ? queries.mean_synapses_activated.toFixed(1) : '—'}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Tool Calls</span>
          <span class="metric-value">${fmtNumber(queries.sum_tool_calls)} (${fmtNumber(queries.sum_tool_successes)} success)</span>
        </div>
      `;
    }

    if (builds.n_builds) {
      html += `
        <div class="metric-row">
          <span class="metric-label">Total Builds</span>
          <span class="metric-value">${fmtNumber(builds.n_builds)}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Avg Build Duration</span>
          <span class="metric-value">${builds.mean_duration_s ? builds.mean_duration_s.toFixed(1) + 's' : '—'}</span>
        </div>
      `;
    }

    container.innerHTML = html || '<div class="empty-state">No query metrics</div>';
  }

  // Queries
  function renderQueries(data) {
    const queries = (data.queries || {}).recent || [];
    const container = document.getElementById('queries-list');

    if (queries.length === 0) {
      container.innerHTML = '<div class="empty-state">No queries recorded</div>';
      return;
    }

    container.innerHTML = queries
      .map(q => {
        const query = q.query || q.question || '(unknown)';
        const ratio = q.reduction_ratio || q.ratio || 0;
        const tokens = q.tokens || 0;
        const ts = q.timestamp || q.ts;
        return `
          <div class="query-item">
            <span class="query-text">${escapeHtml(query)}</span>
            <span class="query-meta">
              <span class="query-ratio">${fmtRatio(ratio)} reduction</span>
              <span>${fmtTokens(tokens)} tokens</span>
              <span>${fmtTimestamp(ts)}</span>
            </span>
          </div>
        `;
      })
      .join('');
  }

  // Communities
  function renderCommunities(data) {
    const communities = data.communities || [];
    const container = document.getElementById('communities-list');

    if (communities.length === 0) {
      container.innerHTML = '<div class="empty-state">No community data — build index first</div>';
      return;
    }

    const maxSize = Math.max(...communities.map(c => c.size), 1);

    container.innerHTML = communities
      .map(c => {
        const pct = (c.size / maxSize) * 100;
        const labels = (c.top_labels || []).join(', ');
        return `
          <div class="community-row">
            <span class="community-id">CID ${c.id}</span>
            <div class="community-bar-wrap">
              <div class="community-bar" style="width: ${pct}%"></div>
            </div>
            <span class="community-size">${c.size}</span>
            <span class="community-labels" title="${escapeHtml(labels)}">${escapeHtml(labels)}</span>
          </div>
        `;
      })
      .join('');
  }

  // Agent OS
  function renderAgentOS(data) {
    const agentos = data.agent_os || {};

    // Tenants
    const tenants = agentos.tenants || {};
    setText('agentos-total-tenants', fmtNumber(tenants.total_tenants));
    const tiersList = document.getElementById('agentos-tiers');
    const tiers = tenants.tiers || {};
    if (Object.keys(tiers).length === 0) {
      tiersList.innerHTML = '<div class="empty-state">No tenants</div>';
    } else {
      tiersList.innerHTML = Object.entries(tiers)
        .map(([tier, count]) => `
          <div class="list-item">
            <span class="list-label">${escapeHtml(tier)}</span>
            <span class="list-meta">${fmtNumber(count)} tenants</span>
          </div>
        `).join('');
    }

    // Signals
    const signals = agentos.signals || {};
    setText('agentos-tracked-metrics', fmtNumber(signals.tracked_metrics));
    const signalsList = document.getElementById('agentos-signals-list');
    const metrics = signals.metrics || {};
    if (Object.keys(metrics).length === 0) {
      signalsList.innerHTML = '<div class="empty-state">No signals tracked</div>';
    } else {
      signalsList.innerHTML = Object.entries(metrics)
        .map(([name, stats]) => `
          <div class="list-item">
            <span class="list-label">${escapeHtml(name)}</span>
            <span class="list-meta">mean ${stats.running_mean?.toFixed(2) || '—'} · std ${stats.running_std?.toFixed(2) || '—'}</span>
          </div>
        `).join('');
    }

    // Experiments
    const experiments = agentos.experiments || {};
    setText('agentos-total-experiments', fmtNumber(experiments.total_experiments));
    setText('agentos-promotions', fmtNumber(experiments.promotions));
    setText('agentos-rollbacks', fmtNumber(experiments.rollbacks));
    const expList = document.getElementById('agentos-experiments-list');
    const recent = experiments.recent || [];
    if (recent.length === 0) {
      expList.innerHTML = '<div class="empty-state">No experiments run</div>';
    } else {
      expList.innerHTML = recent
        .map(e => `
          <div class="list-item">
            <span class="list-label">${escapeHtml(e.proposal_id)}</span>
            <span class="list-meta">${escapeHtml(e.metric_name)} · delta ${e.delta?.toFixed(3) || '—'} · ${escapeHtml(e.verdict)}</span>
          </div>
        `).join('');
    }
  }

  // Utility: set textContent
  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  // Utility: escape HTML
  function escapeHtml(s) {
    if (!s) return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  // Update timestamp display
  function updateTimestamp(ts) {
    const el = document.getElementById('last-updated');
    if (el) el.textContent = 'Updated: ' + fmtTimestamp(ts);
  }

  // Show error banner
  function showError(msg) {
    const el = document.getElementById('error-banner');
    if (el) {
      el.textContent = msg;
      el.classList.remove('hidden');
      setTimeout(() => el.classList.add('hidden'), 8000);
    }
  }

  // Load and render
  async function load() {
    try {
      const data = await fetchDashboard();
      render(data);
      document.getElementById('loading').classList.add('hidden');
    } catch (err) {
      document.getElementById('loading').textContent = 'Failed to load dashboard';
      showError('Failed to load dashboard: ' + err.message);
    }
  }

  // Tab navigation
  function setupTabs() {
    document.querySelectorAll('.tab').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        btn.classList.add('active');
        const view = document.getElementById('view-' + btn.dataset.view);
        if (view) view.classList.add('active');
      });
    });
  }

  // Refresh button
  function setupRefresh() {
    document.getElementById('refresh').addEventListener('click', () => {
      load();
    });
  }

  // Init
  document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupRefresh();
    load();
    // Auto-refresh every 60s
    setInterval(load, 60000);
  });
})();
