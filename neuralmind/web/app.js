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
    localDepth: 1,
    soloCommunity: false,
    filterToSearch: false,
    showLabels: false,
    activeCommunity: null,
    project: "",
    projectKey: "",        // absolute project path; stable across same-name repos
    searchHitIds: null,    // Set when filter-to-search is on (or when a replay is active)
    synapseMinWeight: 0.05, // matches server-side default; slider can raise it
    hoveredEdge: null,     // {type, e} or null
    replayActive: null,    // the currently replayed query record, if any
    alpha: 1,
  };

  // O(E) edge hover scales fine for typical projects (low thousands of
  // edges); switch off above this to keep mousemove cheap on huge graphs.
  const EDGE_HOVER_CAP = 8000;
  const EDGE_HOVER_RADIUS = 4; // CSS pixels

  // Keying layout by the absolute project path stops two repos with the
  // same basename from overwriting each other's pinned positions.
  const LS_KEY = (key) => `nm:layout:${key}`;

  /* ---------- data loading ---------- */

  async function load() {
    const res = await fetch("/api/graph");
    const data = await res.json();
    state.project = data.project || "";
    state.projectKey = data.project_path || data.project || "";
    document.getElementById("project-name").textContent = state.project;

    const W = canvas.clientWidth || 800;
    const H = canvas.clientHeight || 600;
    const saved = loadLayout(state.projectKey);
    state.nodes = data.nodes.map((n) => {
      const pos = saved && saved[n.id];
      return {
        ...n,
        x: pos ? pos.x : W / 2 + (Math.random() - 0.5) * W * 0.8,
        y: pos ? pos.y : H / 2 + (Math.random() - 0.5) * H * 0.8,
        vx: 0,
        vy: 0,
        degree: 0,
        pinned: !!(pos && pos.pinned),
      };
    });
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
    let set = null;
    if (state.localOnly && state.selected) {
      set = new Set([state.selected.id]);
      let frontier = new Set([state.selected.id]);
      const depth = Math.max(1, Math.min(3, state.localDepth | 0));
      for (let hop = 0; hop < depth && frontier.size; hop++) {
        const next = new Set();
        const visit = (e) => {
          if (frontier.has(e.s.id) && !set.has(e.t.id)) {
            set.add(e.t.id);
            next.add(e.t.id);
          }
          if (frontier.has(e.t.id) && !set.has(e.s.id)) {
            set.add(e.s.id);
            next.add(e.s.id);
          }
        };
        for (const e of state.structuralEdges) visit(e);
        for (const e of state.synapseEdges) visit(e);
        frontier = next;
      }
    }
    if (state.soloCommunity && state.activeCommunity != null) {
      const solo = new Set(
        state.nodes
          .filter((n) => n.community === state.activeCommunity)
          .map((n) => n.id)
      );
      set = set ? new Set([...set].filter((id) => solo.has(id))) : solo;
    }
    if (state.filterToSearch && state.searchHitIds) {
      set = set
        ? new Set([...set].filter((id) => state.searchHitIds.has(id)))
        : new Set(state.searchHitIds);
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
      const minW = state.synapseMinWeight;
      for (const e of state.synapseEdges) {
        if (e.weight < minW) continue;
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
      const pulse = pulseAmount(n.id);
      if (pulse > 0) {
        ctx.globalAlpha = pulse * 0.8;
        ctx.lineWidth = 2 / t.k;
        ctx.strokeStyle = "#e0a458";
        ctx.beginPath();
        ctx.arc(n.x, n.y, r + 5 + 6 * pulse, 0, Math.PI * 2);
        ctx.stroke();
      }
      if (n.pinned) {
        // Pin glyph: small warm dot at top-right, zoom-stable.
        const off = r * 0.72;
        const pr = 2.4 / t.k;
        ctx.beginPath();
        ctx.arc(n.x + off, n.y - off, pr, 0, Math.PI * 2);
        ctx.fillStyle = "#e0a458";
        ctx.fill();
        ctx.lineWidth = 0.8 / t.k;
        ctx.strokeStyle = "#1a1b1e";
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

  // Pause the render loop when the layout is idle so we don't spin at
  // 60fps drawing the same static graph forever. Interactions and
  // incoming activity pulses call wake() to kick it back on.
  let paused = false;
  function sweepPulses() {
    // Evict expired entries even for hidden nodes, otherwise filters
    // (local-graph, solo-community, search) could leave the pulse map
    // permanently non-empty and the render loop would never re-pause.
    if (!pulses.size) return;
    const now = performance.now();
    for (const [id, exp] of pulses) {
      if (exp <= now) pulses.delete(id);
    }
  }
  function tick() {
    sweepPulses();
    simulate();
    draw();
    if (state.alpha < 0.005 && !dragNode && pulses.size === 0) {
      paused = true;
    } else {
      requestAnimationFrame(tick);
    }
  }
  function wake() {
    if (paused) {
      paused = false;
      requestAnimationFrame(tick);
    }
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
  window.addEventListener("resize", () => {
    resize();
    wake();
  });

  /* ---------- interaction ---------- */

  let dragNode = null;
  let panning = false;
  let last = { x: 0, y: 0 };
  let downAt = null;

  const toWorld = (sx, sy) => ({
    x: (sx - state.transform.x) / state.transform.k,
    y: (sy - state.transform.y) / state.transform.k,
  });

  function distSqPointToSegment(px, py, ax, ay, bx, by) {
    const dx = bx - ax;
    const dy = by - ay;
    const lenSq = dx * dx + dy * dy;
    if (lenSq === 0) {
      const ex = px - ax;
      const ey = py - ay;
      return ex * ex + ey * ey;
    }
    let t = ((px - ax) * dx + (py - ay) * dy) / lenSq;
    t = Math.max(0, Math.min(1, t));
    const cx = ax + t * dx;
    const cy = ay + t * dy;
    const ex = px - cx;
    const ey = py - cy;
    return ex * ex + ey * ey;
  }

  // Find the visible edge nearest to the world-space point, or null. We
  // walk both structural and synapse arrays and keep the closest hit
  // within the (zoom-scaled) hover radius.
  function edgeAt(wx, wy) {
    const vis = visibleSet();
    const isVisible = (n) => !vis || vis.has(n.id);
    const radius = EDGE_HOVER_RADIUS / state.transform.k;
    const radiusSq = radius * radius;

    const totalEdges = state.structuralEdges.length + state.synapseEdges.length;
    if (totalEdges > EDGE_HOVER_CAP) return null;

    let bestEdge = null;
    let bestType = null;
    let bestDist = Infinity;

    const consider = (e, type, weightGuard) => {
      if (weightGuard && e.weight < state.synapseMinWeight) return;
      if (!isVisible(e.s) || !isVisible(e.t)) return;
      const d = distSqPointToSegment(wx, wy, e.s.x, e.s.y, e.t.x, e.t.y);
      if (d < bestDist && d <= radiusSq) {
        bestDist = d;
        bestEdge = e;
        bestType = type;
      }
    };

    if (state.showStructural) {
      for (const e of state.structuralEdges) consider(e, "structural", false);
    }
    if (state.showSynapses) {
      for (const e of state.synapseEdges) consider(e, "synapse", true);
    }
    return bestEdge ? { type: bestType, e: bestEdge } : null;
  }

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
    wake();
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
      wake();
    } else if (panning) {
      state.transform.x += sx - last.x;
      state.transform.y += sy - last.y;
      wake();
    } else {
      const hit = nodeAt(sx, sy);
      const hoverChanged = hit !== state.hovered;
      state.hovered = hit;
      if (hit) {
        // Node hover takes precedence; clear any edge hover.
        if (state.hoveredEdge) state.hoveredEdge = null;
        tooltip.hidden = false;
        tooltip.innerHTML = "";
        tooltip.textContent = hit.source_file
          ? `${hit.label}  —  ${hit.source_file}`
          : hit.label;
        tooltip.style.left = sx + 12 + "px";
        tooltip.style.top = sy + 12 + "px";
      } else {
        const w = toWorld(sx, sy);
        const edge = edgeAt(w.x, w.y);
        const edgeChanged =
          (edge && (!state.hoveredEdge || state.hoveredEdge.e !== edge.e)) ||
          (!edge && state.hoveredEdge);
        state.hoveredEdge = edge;
        if (edge) {
          tooltip.hidden = false;
          tooltip.innerHTML = "";
          const e = edge.e;
          const head = document.createElement("span");
          const arrow = edge.type === "structural" ? "→" : "↔";
          head.textContent = `${e.s.label} ${arrow} ${e.t.label}`;
          const detail = document.createElement("span");
          detail.className = "tt-edge";
          if (edge.type === "structural") {
            detail.textContent = `structural · ${e.relation || "related"}`;
          } else {
            detail.textContent = `learned · w ${e.weight.toFixed(2)} · ${e.activation_count}×`;
          }
          tooltip.append(head, detail);
          tooltip.style.left = sx + 12 + "px";
          tooltip.style.top = sy + 12 + "px";
        } else {
          tooltip.hidden = true;
        }
        if (edgeChanged) wake();
      }
      if (hoverChanged) wake();
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
      // Either branch changes the pinned-set: a drag pinned the node,
      // a click unpinned it. Persist both so refreshes match what the
      // user just did.
      saveLayout();
    }
    dragNode = null;
    panning = false;
    downAt = null;
    wake();
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
      wake();
    },
    { passive: false }
  );

  /* ---------- selection + detail panel ---------- */

  function selectNode(node) {
    state.selected = node;
    renderDetail(node);
    syncCommunityActive();
    wake();
  }

  function focusNode(node) {
    // center the viewport on a node (used by search / link clicks)
    selectNode(node);
    const t = state.transform;
    t.x = canvas.clientWidth / 2 - node.x * t.k;
    t.y = canvas.clientHeight / 2 - node.y * t.k;
    state.alpha = Math.max(state.alpha, 0.15);
    wake();
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

    const pinBtn = document.createElement("button");
    pinBtn.type = "button";
    pinBtn.className = "open-btn";
    const refreshPinLabel = () => {
      pinBtn.textContent = node.pinned ? "Unpin" : "Pin";
    };
    refreshPinLabel();
    pinBtn.addEventListener("click", () => {
      node.pinned = !node.pinned;
      refreshPinLabel();
      saveLayout();
      if (!node.pinned) state.alpha = Math.max(state.alpha, 0.3);
      wake();
    });
    panel.append(pinBtn);

    if (node.source_file) {
      const openBtn = document.createElement("button");
      openBtn.type = "button";
      openBtn.className = "open-btn";
      openBtn.textContent = "Open in editor";
      const status = document.createElement("span");
      status.className = "open-status";
      openBtn.addEventListener("click", () => openInEditor(node, status, openBtn));
      panel.append(openBtn, status);
    }

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
        wake();
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
  let searchAbort = null;

  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    const q = searchInput.value.trim();
    if (!q) {
      // Cancel any in-flight request so a slow stale response can't
      // overwrite the cleared state half a second later.
      if (searchAbort) searchAbort.abort();
      searchResults.innerHTML = "";
      state.searchHitIds = null;
      wake();
      return;
    }
    searchTimer = setTimeout(async () => {
      if (searchAbort) searchAbort.abort();
      searchAbort = new AbortController();
      const mySignal = searchAbort.signal;
      try {
        const res = await fetch(
          "/api/search?q=" + encodeURIComponent(q),
          { signal: mySignal }
        );
        if (mySignal.aborted) return;
        const data = await res.json();
        if (mySignal.aborted) return;
        renderSearchResults(data.results || []);
        state.searchHitIds = new Set((data.results || []).map((r) => r.id));
        wake();
      } catch (e) {
        if (e && e.name === "AbortError") return;
        searchResults.innerHTML = "";
        state.searchHitIds = null;
        wake();
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

  /* ---------- keyboard shortcuts ---------- */

  // Cmd/Ctrl-K from anywhere, '/' when no field is focused → jump to
  // the search box (select existing text so re-typing overwrites).
  // Esc inside the search box clears it and returns focus to the page.
  window.addEventListener("keydown", (ev) => {
    const t = ev.target;
    const inField =
      t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable);
    const cmdK = (ev.metaKey || ev.ctrlKey) && (ev.key === "k" || ev.key === "K");
    if (cmdK || (ev.key === "/" && !inField)) {
      ev.preventDefault();
      searchInput.focus();
      searchInput.select();
    } else if (ev.key === "Escape" && t === searchInput) {
      searchInput.value = "";
      searchInput.dispatchEvent(new Event("input"));
      searchInput.blur();
    }
  });

  /* ---------- open in editor ---------- */

  async function openInEditor(node, statusEl, btn) {
    btn.disabled = true;
    statusEl.textContent = "Opening…";
    statusEl.classList.remove("error");
    try {
      const res = await fetch("/api/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: node.id }),
      });
      const data = await res.json();
      if (data.ok) {
        const tail = data.line ? `:${data.line}` : "";
        statusEl.textContent = `Opened ${data.file}${tail}`;
      } else {
        statusEl.classList.add("error");
        statusEl.textContent = data.error || "Could not open file.";
      }
    } catch (err) {
      statusEl.classList.add("error");
      statusEl.textContent = "Network error: " + err;
    } finally {
      btn.disabled = false;
    }
  }

  /* ---------- layout persistence ---------- */

  function loadLayout(key) {
    if (!key) return null;
    try {
      const raw = localStorage.getItem(LS_KEY(key));
      if (!raw) return null;
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  let saveTimer = null;
  function saveLayout() {
    if (!state.projectKey) return;
    clearTimeout(saveTimer);
    // Debounce — drags fire many events; we only need the resting state.
    saveTimer = setTimeout(() => {
      const out = {};
      for (const n of state.nodes) {
        if (n.pinned) out[n.id] = { x: n.x, y: n.y, pinned: true };
      }
      try {
        localStorage.setItem(LS_KEY(state.projectKey), JSON.stringify(out));
      } catch {
        // localStorage may be full or disabled — non-critical.
      }
    }, 250);
  }

  /* ---------- recent queries / replay overlay ---------- */

  async function refreshRecentQueries() {
    try {
      const res = await fetch("/api/queries?n=20");
      const data = await res.json();
      renderRecentQueries(data.queries || []);
    } catch {
      // Network errors are non-fatal — leave whatever was rendered.
    }
  }

  function renderRecentQueries(queries) {
    const ul = document.getElementById("replay-list");
    const empty = document.getElementById("replay-empty");
    ul.innerHTML = "";
    if (!queries.length) {
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    for (const q of queries) {
      const li = document.createElement("li");
      li.className = "replay-row";
      const qLine = document.createElement("span");
      qLine.className = "q";
      qLine.textContent = q.question || "(empty)";
      const meta = document.createElement("span");
      meta.className = "meta";
      const ratio = document.createElement("span");
      ratio.className = "ratio";
      ratio.textContent = q.reduction_ratio ? `${q.reduction_ratio.toFixed(1)}×` : "";
      const stats = document.createElement("span");
      const hitCount = (q.top_hits || []).length;
      stats.textContent = `${q.tokens || 0} tok · ${hitCount} hit${hitCount === 1 ? "" : "s"} · ${shortTs(q.ts)}`;
      meta.append(ratio, stats);
      li.append(qLine, meta);
      if (state.replayActive && state.replayActive.ts === q.ts) {
        li.classList.add("active");
      }
      li.addEventListener("click", () => replayQuery(q, li));
      ul.appendChild(li);
    }
  }

  function shortTs(iso) {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      const diff = (Date.now() - d.getTime()) / 1000;
      if (diff < 60) return "just now";
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
      return d.toLocaleDateString();
    } catch {
      return "";
    }
  }

  function replayQuery(record, row) {
    // Re-clicking the active query clears the replay.
    if (state.replayActive && state.replayActive.ts === record.ts) {
      clearReplay();
      return;
    }
    state.replayActive = record;
    state.searchHitIds = new Set((record.top_hits || []).map((h) => h.id));
    // Auto-enable "limit graph to search hits" so the replay actually
    // filters the canvas — otherwise the highlight is invisible against
    // a busy graph.
    const filterToggle = document.getElementById("toggle-filter-search");
    filterToggle.checked = true;
    state.filterToSearch = true;

    document.querySelectorAll(".replay-row.active").forEach((el) =>
      el.classList.remove("active")
    );
    if (row) row.classList.add("active");

    renderReplayDetail(record);
    wake();
  }

  function clearReplay() {
    state.replayActive = null;
    state.searchHitIds = null;
    document.getElementById("toggle-filter-search").checked = false;
    state.filterToSearch = false;
    document.querySelectorAll(".replay-row.active").forEach((el) =>
      el.classList.remove("active")
    );
    renderDetail(state.selected);
    wake();
  }

  function renderReplayDetail(record) {
    // Repurpose the detail panel to summarize the replayed query so the
    // user sees exactly which nodes the agent received and at what cost.
    const panel = document.getElementById("detail-panel");
    panel.innerHTML = "<h2>Replayed query</h2>";

    const q = document.createElement("p");
    q.className = "detail-title";
    q.textContent = record.question || "(empty)";
    const sub = document.createElement("p");
    sub.className = "detail-sub";
    const layers = (record.layers_used || []).join(", ") || "—";
    sub.textContent =
      `${record.tokens || 0} tokens · ${
        record.reduction_ratio ? record.reduction_ratio.toFixed(1) + "× reduction" : "no ratio"
      } · layers: ${layers}`;
    panel.append(q, sub);

    if (record.communities_loaded && record.communities_loaded.length) {
      const c = document.createElement("p");
      c.className = "detail-sub";
      c.textContent = "Communities loaded: " + record.communities_loaded.join(", ");
      panel.appendChild(c);
    }

    const clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "open-btn";
    clearBtn.textContent = "Clear replay";
    clearBtn.addEventListener("click", clearReplay);
    panel.appendChild(clearBtn);

    const section = document.createElement("div");
    section.className = "detail-section";
    const h = document.createElement("h3");
    h.textContent = `Top hits (${(record.top_hits || []).length})`;
    section.appendChild(h);
    const ul = document.createElement("ul");
    for (const hit of record.top_hits || []) {
      const node = state.nodeById.get(hit.id);
      if (!node) continue;
      ul.appendChild(linkRow(node, `score ${hit.score}`));
    }
    section.appendChild(ul);
    panel.appendChild(section);
  }

  document
    .getElementById("replay-refresh")
    .addEventListener("click", refreshRecentQueries);

  /* ---------- toggles ---------- */

  const bind = (id, key) => {
    const el = document.getElementById(id);
    el.addEventListener("change", () => {
      state[key] = el.checked;
      wake();
    });
  };
  bind("toggle-synapses", "showSynapses");
  bind("toggle-structural", "showStructural");
  bind("toggle-local", "localOnly");
  bind("toggle-solo", "soloCommunity");
  bind("toggle-filter-search", "filterToSearch");
  bind("toggle-labels", "showLabels");

  const weightSlider = document.getElementById("synapse-min-weight");
  const weightReadout = document.getElementById("weight-readout");
  weightSlider.addEventListener("input", () => {
    const v = parseFloat(weightSlider.value);
    state.synapseMinWeight = isFinite(v) ? v : 0;
    weightReadout.textContent = state.synapseMinWeight.toFixed(2);
    // If the currently-hovered edge fell below the threshold, drop it
    // so the tooltip doesn't stay stuck on an invisible line.
    if (
      state.hoveredEdge &&
      state.hoveredEdge.type === "synapse" &&
      state.hoveredEdge.e.weight < state.synapseMinWeight
    ) {
      state.hoveredEdge = null;
      tooltip.hidden = true;
    }
    wake();
  });

  const depthInput = document.getElementById("local-depth");
  const depthValue = document.getElementById("local-depth-value");
  const depthRow = depthInput.closest(".slider-row");
  function syncDepthEnabled() {
    const off = !state.localOnly;
    depthRow.classList.toggle("disabled", off);
    // Mirror the CSS state on the input itself so keyboard / screen-reader
    // users see the same "inert" behavior the sighted UI shows. Without
    // this the range is still focusable + adjustable while it looks dimmed.
    depthInput.disabled = off;
  }
  depthInput.addEventListener("input", () => {
    state.localDepth = Math.max(1, Math.min(3, parseInt(depthInput.value, 10) || 1));
    depthValue.textContent = String(state.localDepth);
    wake();
  });
  document.getElementById("toggle-local").addEventListener("change", syncDepthEnabled);
  syncDepthEnabled();

  document.getElementById("reset-layout").addEventListener("click", () => {
    if (!state.projectKey) return;
    try {
      localStorage.removeItem(LS_KEY(state.projectKey));
    } catch {}
    for (const n of state.nodes) {
      n.pinned = false;
      n.x = canvas.clientWidth / 2 + (Math.random() - 0.5) * canvas.clientWidth * 0.8;
      n.y = canvas.clientHeight / 2 + (Math.random() - 0.5) * canvas.clientHeight * 0.8;
    }
    state.alpha = 1;
    if (state.selected) renderDetail(state.selected);
    wake();
  });

  document.getElementById("unpin-all").addEventListener("click", () => {
    let any = false;
    for (const n of state.nodes) {
      if (n.pinned) {
        n.pinned = false;
        any = true;
      }
    }
    if (!any) return;
    saveLayout();
    state.alpha = Math.max(state.alpha, 0.6);
    if (state.selected) renderDetail(state.selected);
    wake();
  });

  /* ---------- live activity stream ---------- */

  // nodeId → pulse-end timestamp (performance.now() units). The render
  // loop reads pulseAmount(id) ∈ [0,1] each frame; entries are evicted
  // once expired so an idle graph can pause animation.
  const PULSE_MS = 1400;
  const pulses = new Map();
  function pulseAmount(id) {
    const exp = pulses.get(id);
    if (!exp) return 0;
    const now = performance.now();
    if (exp <= now) {
      pulses.delete(id);
      return 0;
    }
    return (exp - now) / PULSE_MS;
  }
  function triggerPulses(ids) {
    if (!Array.isArray(ids) || !ids.length) return;
    const exp = performance.now() + PULSE_MS;
    let any = false;
    for (const id of ids) {
      if (state.nodeById.has(id)) {
        pulses.set(id, exp);
        any = true;
      }
    }
    if (any) wake();
  }

  const eventLog = document.getElementById("event-log");
  const eventStatus = document.getElementById("activity-status");
  const MAX_LOG_ROWS = 80;

  function formatEventTime(ts) {
    const d = ts ? new Date(ts * 1000) : new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }

  function describeEvent(ev) {
    if (ev.type === "synapse") {
      const n = ev.nodes ? ev.nodes.length : 0;
      const p = ev.pair_count || 0;
      return `synapse · ${p} pair${p === 1 ? "" : "s"} on ${n} node${n === 1 ? "" : "s"}`;
    }
    if (ev.type === "file") {
      const c = ev.count || (ev.paths ? ev.paths.length : 0);
      const first = ev.paths && ev.paths[0] ? shortPath(ev.paths[0]) : "";
      return c <= 1 && first
        ? `file · ${first}`
        : `file · ${c} edit${c === 1 ? "" : "s"}` + (first ? ` (${first}…)` : "");
    }
    if (ev.type === "hello") return "stream connected";
    return ev.type;
  }

  function shortPath(p) {
    const parts = String(p).split("/");
    return parts.length <= 2 ? p : parts.slice(-2).join("/");
  }

  function appendEvent(ev) {
    const li = document.createElement("li");
    li.className = "event-row fresh event-" + (ev.type || "system");
    const time = document.createElement("span");
    time.className = "event-time";
    time.textContent = formatEventTime(ev.ts);
    const label = document.createElement("span");
    label.className = "event-label";
    label.textContent = describeEvent(ev);
    li.append(time, label);
    eventLog.prepend(li);
    while (eventLog.children.length > MAX_LOG_ROWS) {
      eventLog.removeChild(eventLog.lastChild);
    }
    // Fade the "fresh" highlight after a beat so newer rows still stand out.
    setTimeout(() => li.classList.remove("fresh"), 1200);
  }

  function setStreamStatus(kind, message) {
    eventStatus.classList.toggle("live", kind === "live");
    eventStatus.classList.toggle("dead", kind === "dead");
    eventStatus.title = message;
    // Update the screen-reader announcement too so the live/disconnected
    // state isn't conveyed by color alone.
    eventStatus.setAttribute("aria-label", message);
  }

  function startEventStream() {
    if (typeof EventSource === "undefined") {
      setStreamStatus("dead", "Live stream not supported in this browser");
      return;
    }
    const es = new EventSource("/api/events");
    es.onopen = () => {
      setStreamStatus("live", "Live stream connected");
    };
    es.onerror = () => {
      // EventSource auto-reconnects; just mark the status until then.
      setStreamStatus("dead", "Live stream disconnected; will retry");
    };
    es.onmessage = (m) => {
      let ev;
      try {
        ev = JSON.parse(m.data);
      } catch {
        return;
      }
      appendEvent(ev);
      if (ev.type === "synapse" && Array.isArray(ev.nodes)) {
        triggerPulses(ev.nodes);
      }
    };
  }

  /* ---------- boot ---------- */

  resize();
  load()
    .then(() => refreshRecentQueries())
    .catch((e) => {
      loading.textContent = "Failed to load graph: " + e;
    });
  startEventStream();
})();
