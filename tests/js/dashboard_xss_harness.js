// Renders neuralmind/web/dashboard.js against a stub DOM with hostile API
// data and prints every element's innerHTML as JSON. Driven by
// tests/test_dashboard_xss.py; needs only Node (no browser, no npm deps).
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const PAYLOAD = 'x" onmouseover="alert(1)" y="<img src=x onerror=alert(2)>';

const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    elements.set(id, {
      id,
      innerHTML: '',
      textContent: '',
      style: {},
      dataset: {},
      classList: { add() {}, remove() {} },
      addEventListener() {},
    });
  }
  return elements.get(id);
}

let onReady = null;
const document = {
  getElementById: element,
  querySelectorAll: () => [],
  addEventListener: (event, fn) => {
    if (event === 'DOMContentLoaded') onReady = fn;
  },
  // What a browser does for `div.textContent = s; div.innerHTML`: escapes
  // &, < and >, and leaves quotes alone.
  createElement: () => {
    let text = '';
    return {
      set textContent(value) {
        text = String(value);
      },
      get innerHTML() {
        return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      },
    };
  },
};

const data = {
  status: { built: true },
  communities: [{ id: PAYLOAD, size: PAYLOAD, top_labels: [PAYLOAD] }],
  synapses: { top_edges: [{ a: 'a', b: 'b', weight: PAYLOAD, count: PAYLOAD }] },
  ingestion: { ingested_files: [{ source: 's', node_count: PAYLOAD, timestamp: 0 }] },
};

const sandbox = {
  document,
  window: {},
  console,
  setInterval: () => 0,
  fetch: async () => ({ ok: true, json: async () => data }),
};
vm.createContext(sandbox);
const source = fs.readFileSync(
  path.join(__dirname, '..', '..', 'neuralmind', 'web', 'dashboard.js'),
  'utf8'
);
vm.runInContext(source, sandbox);

(async () => {
  onReady();
  for (let i = 0; i < 20; i++) await new Promise((r) => setImmediate(r));
  const out = {};
  for (const [id, el] of elements) out[id] = el.innerHTML;
  process.stdout.write(JSON.stringify(out));
})();
