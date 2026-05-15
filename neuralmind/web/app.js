/*
 * app.js — NeuralMind graph-view UI.
 *
 * Vanilla canvas force-directed graph over the code graph returned by
 * /api/graph. Structural edges (calls/imports) and the learned synapse
 * overlay are drawn together; the sidebar gives Obsidian-style backlinks,
 * a local-graph focus mode, a community browser, and semantic quick-switch.
 */
(() => {
  "use strict";

  const canvas = document.getElementById("graph");
  const ctx = canvas.getContext("2d");
  const tooltip = document.getElementById("tooltip");
  const loading = document.getElementById("loading");

  const PALETTE = [
    "#7c6cf0", "#e0a458", "#5fb37a", "#d9694f", "#4fa3d9",
    "#c45fb3", "#8aab4a", "#d97fae", "#5fc7c0", "#b08a5f",
  ];
  const communityColor = (c) =>
    c < 0 ? "#6b6d75" : PALETTE[c % PALETTE.length];

  const state = {
    nodes: [],
    structuralEdges: [],
    synapseEdges: [],
    nodeById: new Map(),
    structAdj: new Map(),   // id -> Set of {edge}
    selected: null,
    hovered: null,
    transform: { x: 0, y: 0, k: 1 },
    showSynapses: true,
    showStructural: true,
    localOnly: false,
    showLabels: false,
    activeCommunity: null,
    alpha: 1,
  };

  /* ---------- data loading ---------- */

  async function load() {
    const res = await fetch("/api/graph");
    const data = await res.json();
    document.getElementById("project-name").textContent = data.project || "";

    const W = canvas.clientWidth || 800;
    const H = canvas.clientHeight || 600;
    state.nodes = data.nodes.map((n) => ({
      ...n,
      x: W / 2 + (Math.random() - 0.5) * W * 0.8,
      y: H / 2 + (Math.random() - 0.5) * H * 0.8,
      vx: 0,
      vy: 0,
      degree: 0,
      pinned: false,
    }));
    state.nodeById = new Map(state.nodes.map((n) => [n.id, n]));

    const resolve = (e) => {
      const s = state.nodeById.get(e.source);
      const t = state.nodeById.get(e.target);
      return s && t ? { ...e, s, t } : null;
    };
    state.structuralEdges = data.edges.map(resolve).filter(Boolean);
    state.synapseEdges = data.synapses.map(resolve).filter(Boolean);

    for (const e of state.structuralEdges) {
      e.s.degree++;
      e.t.degree++;
      if (!state.structAdj.has(e.s.id)) state.structAdj.set(e.s.id, []);
      if (!state.structAdj.has(e.t.id)) state.structAdj.set(e.t.id, []);
      state.structAdj.get(e.s.id).push(e);
      state.structAdj.get(e.t.id).push(e);
    }

    renderCommunities(data.communities);
    document.getElementById("stats").innerHTML =
      `${data.stats.nodes} nodes · ${data.stats.edges} structural edges<br>` +
      `${data.stats.synapses} learned synapses<br>` +
      `<span class="muted">scroll to zoom · drag to pan · drag a node to pin</span>`;

    loading.classList.add("hidden");
    state.alpha = 1;
    requestAnimationFrame(tick);
  }

  /* ---------- force simulation ---------- */

  const REPULSION = 2400;
  const SPRING_LEN = 70;
  const SPRING_K = 0.02;
  const SYNAPSE_K = 0.06;
  const CENTER_K = 0.015;
  const DAMPING = 0.82;

  function simulate() {
    if (state.alpha < 0.005) return;
    const nodes = state.nodes;
    const W = canvas.clientWidth;
    const H = canvas.clientHeight;
    const cx = W / 2;
    const cy = H / 2;

    // Grid-bucketed repulsion so large graphs stay interactive.
    const cell = 90;
    const grid = new Map();
    const key = (gx, gy) => gx + "," + gy;
    for (const n of nodes) {
      const gx = Math.floor(n.x / cell);
      const gy = Math.floor(n.y / cell);
      const k = key(gx, gy);
      if (!grid.has(k)) grid.set(k, []);
      grid.get(k).push(n);
    }
    for (const n of nodes) {
      const gx = Math.floor(n.x / cell);
      const gy = Math.floor(n.y / cell);
      for (let dx = -1; dx <= 1; dx++) {
        for (let dy = -1; dy <= 1; dy++) {
          const bucket = grid.get(key(gx + dx, gy + dy));
          if (!bucket) continue;
          for (const m of bucket) {
            if (m === n) continue;
            let ddx = n.x - m.x;
            let ddy = n.y - m.y;
            let d2 = ddx * ddx + ddy * ddy;
            if (d2 < 0.01) {
              ddx = Math.random() - 0.5;
              ddy = Math.random() - 0.5;
              d2 = 1;
            }
            if (d2 > cell * cell * 4) continue;
            const force = REPULSION / d2;
            const d = Math.sqrt(d2);
            n.vx += (ddx / d) * force * state.alpha;
            n.vy += (ddy / d) * force * state.alpha;
          }
        }
      }
    }

    const spring = (e, k, restMul) => {
      const dx = e.t.x - e.s.x;
      const dy = e.t.y - e.s.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 1;
      const rest = SPRING_LEN * restMul;
      const f = (d - rest) * k * state.alpha;
      const fx = (dx / d) * f;
      const fy = (dy / d) * f;
      e.s.vx += fx;
      e.s.vy += fy;
      e.t.vx -= fx;
      e.t.vy -= fy;
    };
    for (const e of state.structuralEdges) spring(e, SPRING_K, 1);
    for (const e of state.synapseEdges) spring(e, SYNAPSE_K * e.weight, 0.7);

    for (const n of nodes) {
      n.vx += (cx - n.x) * CENTER_K * state.alpha;
      n.vy += (cy - n.y) * CENTER_K * state.alpha;
      if (n.pinned || n === dragNode) {
        n.vx = 0;
        n.vy = 0;
        continue;
      }
      n.vx *= DAMPING;
      n.vy *= DAMPING;
      n.x += n.vx;
      n.y += n.vy;
    }
    state.alpha *= 0.99;
  }

  /* ---------- rendering ---------- */

  const nodeRadius = (n) => 3.5 + Math.sqrt(n.degree);

  function visibleSet() {
    if (!state.localOnly || !state.selected) return null;
    const set = new Set([state.selected.id]);
    for (const e of state.structuralEdges) {
      if (e.s.id === state.selected.id) set.add(e.t.id);
      if (e.t.id === state.selected.id) set.add(e.s.id);
    }
    for (const e of state.synapseEdges) {
      if (e.s.id === state.selected.id) set.add(e.t.id);
      if (e.t.id === state.selected.id) set.add(e.s.id);
    }
    return set;
  }

  function neighborIds(node) {
    const set = new Set();
    if (!node) return set;
    for (const e of state.structuralEdges) {
      if (e.s.id === node.id) set.add(e.t.id);
      if (e.t.id === node.id) set.add(e.s.id);
    }
    for (const e of state.synapseEdges) {
      if (e.s.id === node.id) set.add(e.t.id);
      if (e.t.id === node.id) set.add(e.s.id);
    }
    return set;
  }

  function draw() {
    const W = canvas.width;
    const H = canvas.height;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const t = state.transform;
    ctx.setTransform(t.k * dpr, 0, 0, t.k * dpr, t.x * dpr, t.y * dpr);

    const vis = visibleSet();
    const isVisible = (n) => !vis || vis.has(n.id);
    const focus = state.hovered || state.selected;
    const highlight = focus ? neighborIds(focus) : null;

    // structural edges
    if (state.showStructural) {
      ctx.lineWidth = 0.7 / t.k;
      for (const e of state.structuralEdges) {
        if (!isVisible(e.s) || !isVisible(e.t)) continue;
        const lit =
          focus && (e.s.id === focus.id || e.t.id === focus.id);
        ctx.strokeStyle = lit ? "#9aa0b8" : "#3a3c45";
        ctx.globalAlpha = focus && !lit ? 0.25 : 0.7;
        ctx.beginPath();
        ctx.moveTo(e.s.x, e.s.y);
        ctx.lineTo(e.t.x, e.t.y);
        ctx.stroke();
      }
    }

    // synapse overlay
    if (state.showSynapses) {
      for (const e of state.synapseEdges) {
        if (!isVisible(e.s) || !isVisible(e.t)) continue;
        const lit =
          focus && (e.s.id === focus.id || e.t.id === focus.id);
        ctx.strokeStyle = "#e0a458";
        ctx.globalAlpha = (focus && !lit ? 0.2 : 0.85) * (0.35 + e.weight * 0.65);
        ctx.lineWidth = (0.6 + e.weight * 2.4) / t.k;
        ctx.beginPath();
        ctx.moveTo(e.s.x, e.s.y);
        ctx.lineTo(e.t.x, e.t.y);
        ctx.stroke();
      }
    }

    // nodes
    ctx.globalAlpha = 1;
    for (const n of state.nodes) {
      if (!isVisible(n)) continue;
      const r = nodeRadius(n);
      const dim =
        (state.activeCommunity != null && n.community !== state.activeCommunity) ||
        (focus && focus.id !== n.id && highlight && !highlight.has(n.id));
      ctx.globalAlpha = dim ? 0.25 : 1;
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      ctx.fillStyle = communityColor(n.community);
      ctx.fill();
      if (n === state.selected) {
        ctx.lineWidth = 2 / t.k;
        ctx.strokeStyle = "#fff";
        ctx.stroke();
      }
      if (state.showLabels || n === focus || n === state.selected) {
        ctx.globalAlpha = dim ? 0.4 : 1;
        ctx.fillStyle = "#d6d7da";
        ctx.font = `${11 / t.k}px sans-serif`;
        ctx.fillText(n.label, n.x + r + 2 / t.k, n.y + 3 / t.k);
      }
    }
    ctx.globalAlpha = 1;
  }

  function tick() {
    simulate();
    draw();
    requestAnimationFrame(tick);
  }

  /* ---------- canvas sizing ---------- */

  let dpr = window.devicePixelRatio || 1;
  function resize() {
    dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
  }
  window.addEventListener("resize", resize);

  /* ---------- interaction ---------- */

  let dragNode = null;
  let panning = false;
  let last = { x: 0, y: 0 };
  let downAt = null;

  const toWorld = (sx, sy) => ({
    x: (sx - state.transform.x) / state.transform.k,
    y: (sy - state.transform.y) / state.transform.k,
  });

  function nodeAt(sx, sy) {
    const w = toWorld(sx, sy);
    let best = null;
    let bestD = Infinity;
    const vis = visibleSet();
    for (const n of state.nodes) {
      if (vis && !vis.has(n.id)) continue;
      const r = nodeRadius(n) + 4;
      const dx = n.x - w.x;
      const dy = n.y - w.y;
      const d = dx * dx + dy * dy;
      if (d < r * r && d < bestD) {
        bestD = d;
        best = n;
      }
    }
    return best;
  }

  canvas.addEventListener("mousedown", (ev) => {
    const rect = canvas.getBoundingClientRect();
    const sx = ev.clientX - rect.left;
    const sy = ev.clientY - rect.top;
    downAt = { x: sx, y: sy };
    const hit = nodeAt(sx, sy);
    if (hit) {
      dragNode = hit;
      dragNode.pinned = true;
      state.alpha = Math.max(state.alpha, 0.3);
    } else {
      panning = true;
    }
    last = { x: sx, y: sy };
  });

  window.addEventListener("mousemove", (ev) => {
    const rect = canvas.getBoundingClientRect();
    const sx = ev.clientX - rect.left;
    const sy = ev.clientY - rect.top;

    if (dragNode) {
      const w = toWorld(sx, sy);
      dragNode.x = w.x;
      dragNode.y = w.y;
      state.alpha = Math.max(state.alpha, 0.2);
    } else if (panning) {
      state.transform.x += sx - last.x;
      state.transform.y += sy - last.y;
    } else {
      const hit = nodeAt(sx, sy);
      state.hovered = hit;
      if (hit) {
        tooltip.hidden = false;
        tooltip.textContent = hit.source_file
          ? `${hit.label}  —  ${hit.source_file}`
          : hit.label;
        tooltip.style.left = sx + 12 + "px";
        tooltip.style.top = sy + 12 + "px";
      } else {
        tooltip.hidden = true;
      }
    }
    last = { x: sx, y: sy };
  });

  window.addEventListener("mouseup", (ev) => {
    if (dragNode && downAt) {
      const moved =
        Math.hypot(last.x - downAt.x, last.y - downAt.y) > 4;
      if (!moved) {
        dragNode.pinned = false;
        selectNode(dragNode);
      }
    }
    dragNode = null;
    panning = false;
    downAt = null;
  });

  canvas.addEventListener(
    "wheel",
    (ev) => {
      ev.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const sx = ev.clientX - rect.left;
      const sy = ev.clientY - rect.top;
      const factor = ev.deltaY < 0 ? 1.12 : 1 / 1.12;
      const t = state.transform;
      const wx = (sx - t.x) / t.k;
      const wy = (sy - t.y) / t.k;
      t.k = Math.min(6, Math.max(0.1, t.k * factor));
      t.x = sx - wx * t.k;
      t.y = sy - wy * t.k;
    },
    { passive: false }
  );

  /* ---------- selection + detail panel ---------- */

  function selectNode(node) {
    state.selected = node;
    renderDetail(node);
    syncCommunityActive();
  }

  function focusNode(node) {
    // center the viewport on a node (used by search / link clicks)
    selectNode(node);
    const t = state.transform;
    t.x = canvas.clientWidth / 2 - node.x * t.k;
    t.y = canvas.clientHeight / 2 - node.y * t.k;
    state.alpha = Math.max(state.alpha, 0.15);
  }

  function linkRow(node, meta) {
    const li = document.createElement("li");
    li.className = "link-item";
    const label = document.createElement("span");
    label.className = "link-label";
    label.textContent = node.label;
    const m = document.createElement("span");
    m.className = "link-meta";
    m.textContent = meta || "";
    li.append(label, m);
    li.addEventListener("click", () => focusNode(node));
    return li;
  }

  function renderDetail(node) {
    const panel = document.getElementById("detail-panel");
    if (!node) {
      panel.innerHTML =
        '<h2>Node</h2><p class="muted">Click a node to inspect its links.</p>';
      return;
    }

    const backlinks = [];
    const outgoing = [];
    for (const e of state.structAdj.get(node.id) || []) {
      if (e.t.id === node.id) backlinks.push({ node: e.s, rel: e.relation });
      if (e.s.id === node.id) outgoing.push({ node: e.t, rel: e.relation });
    }
    const synaptic = [];
    for (const e of state.synapseEdges) {
      if (e.s.id === node.id) synaptic.push({ node: e.t, w: e.weight, c: e.activation_count });
      else if (e.t.id === node.id) synaptic.push({ node: e.s, w: e.weight, c: e.activation_count });
    }
    synaptic.sort((a, b) => b.w - a.w);

    panel.innerHTML = "<h2>Node</h2>";
    const title = document.createElement("p");
    title.className = "detail-title";
    title.textContent = node.label;
    const sub = document.createElement("p");
    sub.className = "detail-sub";
    sub.textContent =
      (node.source_file || "no source file") +
      (node.source_location ? `  ·  ${node.source_location}` : "") +
      `  ·  community ${node.community}  ·  ${node.file_type}`;
    panel.append(title, sub);

    const section = (heading, items, builder) => {
      const div = document.createElement("div");
      div.className = "detail-section" + (items.length ? "" : " empty");
      const h = document.createElement("h3");
      h.textContent = `${heading} (${items.length})`;
      div.appendChild(h);
      const ul = document.createElement("ul");
      items.slice(0, 30).forEach((it) => ul.appendChild(builder(it)));
      div.appendChild(ul);
      panel.appendChild(div);
    };

    section("Outgoing links", outgoing, (it) => linkRow(it.node, it.rel));
    section("Backlinks", backlinks, (it) => linkRow(it.node, it.rel));
    section("Synaptic neighbors", synaptic, (it) =>
      linkRow(it.node, `w ${it.w.toFixed(2)} · ${it.c}×`)
    );
  }

  /* ---------- community browser ---------- */

  function renderCommunities(communities) {
    const ul = document.getElementById("community-list");
    ul.innerHTML = "";
    for (const c of communities) {
      const li = document.createElement("li");
      li.className = "community-row";
      li.dataset.community = c.id;
      const wrap = document.createElement("span");
      wrap.className = "label-wrap";
      const dot = document.createElement("span");
      dot.className = "dot";
      dot.style.background = communityColor(c.id);
      const label = document.createElement("span");
      label.className = "result-label";
      label.textContent = c.id < 0 ? "ungrouped" : `community ${c.id}`;
      wrap.append(dot, label);
      const meta = document.createElement("span");
      meta.className = "result-meta";
      meta.textContent = c.size;
      li.append(wrap, meta);
      li.addEventListener("click", () => {
        state.activeCommunity =
          state.activeCommunity === c.id ? null : c.id;
        syncCommunityActive();
      });
      ul.appendChild(li);
    }
  }

  function syncCommunityActive() {
    document.querySelectorAll("#community-list li").forEach((li) => {
      li.classList.toggle(
        "active",
        Number(li.dataset.community) === state.activeCommunity
      );
    });
  }

  /* ---------- semantic quick-switch ---------- */

  const searchInput = document.getElementById("search");
  const searchResults = document.getElementById("search-results");
  let searchTimer = null;

  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    const q = searchInput.value.trim();
    if (!q) {
      searchResults.innerHTML = "";
      return;
    }
    searchTimer = setTimeout(async () => {
      try {
        const res = await fetch("/api/search?q=" + encodeURIComponent(q));
        const data = await res.json();
        renderSearchResults(data.results || []);
      } catch (e) {
        searchResults.innerHTML = "";
      }
    }, 180);
  });

  function renderSearchResults(results) {
    searchResults.innerHTML = "";
    for (const r of results) {
      const li = document.createElement("li");
      const label = document.createElement("span");
      label.className = "result-label";
      label.textContent = r.label;
      const meta = document.createElement("span");
      meta.className = "result-meta";
      meta.textContent = r.score;
      li.append(label, meta);
      li.addEventListener("click", () => {
        const node = state.nodeById.get(r.id);
        if (node) focusNode(node);
      });
      searchResults.appendChild(li);
    }
  }

  /* ---------- toggles ---------- */

  const bind = (id, key) => {
    const el = document.getElementById(id);
    el.addEventListener("change", () => {
      state[key] = el.checked;
    });
  };
  bind("toggle-synapses", "showSynapses");
  bind("toggle-structural", "showStructural");
  bind("toggle-local", "localOnly");
  bind("toggle-labels", "showLabels");

  /* ---------- boot ---------- */

  resize();
  load().catch((e) => {
    loading.textContent = "Failed to load graph: " + e;
  });
})();
