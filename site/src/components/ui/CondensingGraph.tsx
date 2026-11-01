'use client';

import { useEffect, useRef } from 'react';
import { CAP, tokenLinear } from '@/components/ui/LiquidBackground';

/**
 * A code graph that condenses out of the liquid at the top of every page.
 *
 * ASCII particles drift as a gas along a flowing field, then condense into a
 * graph like the one `build` makes of a codebase: modules as clusters of
 * nodes, calls as edges. The condensing spreads out from one node along the
 * edges, the way recall spreads through the graph, and the glyphs climb a
 * gas-to-solid ramp from graphite to amber, the colour the mark gives an
 * association NeuralMind learned. It holds, evaporates, and condenses again
 * into a new graph.
 *
 * It is part of the liquid (LiquidBackground.tsx), so it keeps the liquid's
 * constraints:
 *
 * - **Contrast.** Every glyph colour is dimmed in linear light to a relative
 *   luminance no higher than the liquid's `CAP`. A glyph composited over the
 *   liquid is a mix of two colours under the cap, so it stays under it too,
 *   and the tokens' AA ratios hold on top of both.
 * - **Motion.** Under `prefers-reduced-motion` it draws one still frame of the
 *   solid graph. It stops while the tab is hidden or the layer is scrolled out
 *   of view.
 * - **Failure.** Without JavaScript nothing is drawn; the layer fades in only
 *   after its first frame. It is aria-hidden and takes no pointer events.
 *
 * It covers the first screen only and fades out before the content below it
 * (`.condensing-graph` in globals.css). Colours are read from the `:root`
 * tokens, not repeated here.
 */

const CELL_W = 12;
const CELL_H = 18;
const FRAME_MS = 1000 / 15;
// Gas to solid, by how far a particle has condensed.
const RAMP = ['.', '·', ':', '+', '*', '#'];
const LEVELS = RAMP.length;
// Luminance of the gas and the solid, as shares of the liquid's cap: the gas
// sits just above the liquid's ground, the solid at the cap itself.
const GAS_Y = 0.8;
const SOLID_Y = 1;
// A glyph's alpha as gas and as solid.
const GAS_ALPHA = 0.55;
const SOLID_ALPHA = 1;
// One cycle, in seconds: gas, condense, hold, evaporate. A particle takes
// MELT seconds to condense, starting at CONDENSE_AT plus its delay.
const CYCLE = 22;
const CONDENSE_AT = 4;
const MELT = 1.6;
const HOLD_UNTIL = 15.5;
const EVAPORATE_FOR = 3.5;
// How long the condensing takes to cross one edge, in seconds.
const SPREAD = 0.55;
const GAS_SPEED = 16;
// Particles that never condense, per 10,000 px², so the gas never empties.
const FREE_DENSITY = 0.9;

type Particle = {
    x: number;
    y: number;
    tx: number;
    ty: number;
    delay: number;
    solid: string;
};

type Linear = [number, number, number];

// mulberry32: a small seeded generator, so each cycle's graph is new but
// stable within the cycle.
function rng(seed: number) {
    return () => {
        seed = (seed + 0x6d2b79f5) | 0;
        let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

const luminance = (c: Linear) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];

// A linear colour scaled down, never up, to relative luminance `y`.
function dimmed(c: Linear, y: number): Linear {
    const k = Math.min(1, y / luminance(c));
    return [c[0] * k, c[1] * k, c[2] * k];
}

// Linear RGB to a CSS colour with alpha, each channel rounded down so 8-bit
// rounding never lifts a colour over the cap.
function css(c: Linear, alpha: number) {
    const srgb = c.map((v) => Math.floor(255 * (v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055)));
    return `rgba(${srgb.join(', ')}, ${alpha.toFixed(3)})`;
}

// The direction a gas particle drifts: a domain-warped sum of sines, read as
// an angle, so neighbours flow together like a liquid.
function flowAngle(x: number, y: number, t: number) {
    const wx = x + 1.4 * Math.sin(y * 0.9 + t * 0.21);
    const wy = y + 1.4 * Math.sin(x * 0.7 - t * 0.17);
    return (Math.sin(wx * 1.1 + t * 0.3) + Math.sin(wy * 1.3 - t * 0.25)) * Math.PI;
}

function edgeGlyph(dx: number, dy: number) {
    if (Math.abs(dx) > 2 * Math.abs(dy)) return '-';
    if (Math.abs(dy) > 2 * Math.abs(dx)) return '|';
    return dx * dy > 0 ? '\\' : '/';
}

// A graph shaped like a codebase's: three to five modules spread across the
// layer, each a hub with a few files around it, linked inside the module and
// by a few calls between hubs. Every particle gets a place in it and a delay:
// the hop distance from a start node, so the solid spreads along the edges.
function condense(width: number, height: number, seed: number): Particle[] {
    const rand = rng(seed);
    const nodes: { x: number; y: number }[] = [];
    const edges: [number, number][] = [];
    const hubs: number[] = [];
    const modules = width < 640 ? 3 : 4 + Math.floor(rand() * 2);
    for (let m = 0; m < modules; m++) {
        const cx = width * ((m + 0.5) / modules) + (rand() - 0.5) * width * 0.08;
        const cy = height * (0.14 + rand() * 0.36);
        const hub = nodes.push({ x: cx, y: cy }) - 1;
        hubs.push(hub);
        const files = 3 + Math.floor(rand() * 4);
        for (let f = 0; f < files; f++) {
            const a = (f / files) * Math.PI * 2 + rand() * 0.8;
            const r = 60 + rand() * 70;
            const n = nodes.push({ x: cx + Math.cos(a) * r * 1.4, y: cy + Math.sin(a) * r * 0.8 }) - 1;
            edges.push([hub, n]);
            if (f > 0 && rand() < 0.35) edges.push([n - 1, n]);
        }
    }
    for (let m = 1; m < hubs.length; m++) edges.push([hubs[m - 1], hubs[m]]);
    if (hubs.length > 3) edges.push([hubs[0], hubs[2 + Math.floor(rand() * (hubs.length - 2))]]);

    // Hops from the start node, breadth first.
    const hops = nodes.map(() => Infinity);
    const start = hubs[Math.floor(rand() * hubs.length)];
    hops[start] = 0;
    for (let queue = [start]; queue.length; ) {
        const n = queue.shift()!;
        for (const [a, b] of edges) {
            const o = a === n ? b : b === n ? a : -1;
            if (o >= 0 && hops[o] > hops[n] + 1) {
                hops[o] = hops[n] + 1;
                queue.push(o);
            }
        }
    }

    const out: Particle[] = [];
    const gas = () => ({ x: rand() * width, y: rand() * height });
    nodes.forEach((n, i) => {
        const hub = hubs.includes(i);
        // A node is a small block of solid cells, a hub a larger one.
        const half = hub ? 2 : 1;
        for (let dx = -half; dx <= half; dx++) {
            for (let dy = -1; dy <= 1; dy++) {
                if (!hub && dy !== 0 && dx !== 0) continue;
                out.push({
                    ...gas(),
                    tx: n.x + dx * CELL_W,
                    ty: n.y + dy * CELL_H,
                    delay: hops[i] * SPREAD + rand() * 0.3,
                    solid: dx === 0 && dy === 0 ? '@' : '#',
                });
            }
        }
    });
    for (const [a, b] of edges) {
        const na = nodes[a];
        const nb = nodes[b];
        const dx = nb.x - na.x;
        const dy = nb.y - na.y;
        const glyph = edgeGlyph(dx, dy);
        const steps = Math.max(2, Math.floor(Math.hypot(dx / CELL_W, dy / CELL_H)));
        for (let s = 1; s < steps; s++) {
            const k = s / steps;
            out.push({
                ...gas(),
                tx: na.x + dx * k,
                ty: na.y + dy * k,
                // The wave reaches this cell from whichever end it gets to
                // first, so an edge fills outward from its nearer node.
                delay: Math.min(hops[a] + k, hops[b] + 1 - k) * SPREAD + rand() * 0.2,
                solid: glyph,
            });
        }
    }
    const free = Math.round(((width * height) / 10000) * FREE_DENSITY);
    for (let i = 0; i < free; i++) out.push({ ...gas(), tx: NaN, ty: NaN, delay: 0, solid: '' });
    return out;
}

const ease = (k: number) => (k <= 0 ? 0 : k >= 1 ? 1 : k * k * (3 - 2 * k));

// How solid a particle is at time `t` into the cycle, 0 (gas) to 1 (solid).
function solidity(t: number, delay: number) {
    const formed = ease((t - CONDENSE_AT - delay) / MELT);
    const melted = ease((t - HOLD_UNTIL - delay * 0.25) / EVAPORATE_FOR);
    return formed * (1 - melted);
}

export default function CondensingGraph() {
    const wrapRef = useRef<HTMLDivElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const wrap = wrapRef.current;
        const canvas = canvasRef.current;
        const ctx = canvas?.getContext('2d');
        if (!wrap || !canvas || !ctx) return;

        const still = window.matchMedia('(prefers-reduced-motion: reduce)');
        const root = getComputedStyle(document.documentElement);
        const mono = root.getPropertyValue('--font-mono').trim() || 'monospace';
        // Graphite gas to amber solid, each dimmed under the cap, mixed in
        // linear light so every step between them stays under it as well.
        const gasColour = dimmed(tokenLinear(root, '--text'), CAP * GAS_Y);
        const solidColour = dimmed(tokenLinear(root, '--accent'), CAP * SOLID_Y);
        const styles = Array.from({ length: LEVELS }, (_, l) => {
            const k = l / (LEVELS - 1);
            const c = gasColour.map((g, i) => g + (solidColour[i] - g) * k) as Linear;
            return css(c, GAS_ALPHA + (SOLID_ALPHA - GAS_ALPHA) * k);
        });
        let width = 0;
        let height = 0;
        let cols = 0;
        let rows = 0;
        let level = new Int8Array(0);
        let glyph: string[] = [];
        let particles: Particle[] = [];
        let cycle = -1;
        let inView = true;
        let raf = 0;
        let last = 0;
        const start = performance.now();

        // Draws time `now` (seconds since start); `dt` moves the gas on.
        const render = (now: number, dt: number) => {
            const n = Math.floor(now / CYCLE);
            if (n !== cycle) {
                // A new graph each cycle, condensing out of the gas already on
                // screen rather than a fresh scatter, so nothing jumps.
                const prev = particles;
                cycle = n;
                particles = condense(width, height, n * 7919 + 17);
                if (prev.length) {
                    particles.forEach((p, i) => {
                        const q = prev[i % prev.length];
                        p.x = q.x + (Math.random() - 0.5) * CELL_W;
                        p.y = q.y + (Math.random() - 0.5) * CELL_H;
                    });
                }
            }
            const t = now - n * CYCLE;
            level.fill(-1);
            for (const p of particles) {
                const a = flowAngle(p.x * 0.004, p.y * 0.006, now);
                // The flow, plus a little diffusion so the gas doesn't settle
                // into the field's streamlines.
                p.x = (p.x + (Math.cos(a) + Math.random() - 0.5) * GAS_SPEED * dt + width) % width;
                p.y = (p.y + (Math.sin(a) * 0.6 + Math.random() - 0.5) * GAS_SPEED * dt + height) % height;
                const s = p.solid ? solidity(t, p.delay) : 0;
                const x = p.solid ? p.x + (p.tx - p.x) * s : p.x;
                const y = p.solid ? p.y + (p.ty - p.y) * s : p.y;
                const c = Math.floor(x / CELL_W);
                const r = Math.floor(y / CELL_H);
                if (c < 0 || r < 0 || c >= cols || r >= rows) continue;
                const l = Math.min(LEVELS - 1, Math.floor(s * LEVELS));
                const at = r * cols + c;
                if (l <= level[at]) continue;
                level[at] = l;
                glyph[at] = s > 0.92 ? p.solid : RAMP[l];
            }
            ctx.clearRect(0, 0, width, height);
            for (let l = 0; l < LEVELS; l++) {
                ctx.fillStyle = styles[l];
                for (let at = 0; at < level.length; at++) {
                    if (level[at] === l) ctx.fillText(glyph[at], (at % cols) * CELL_W, Math.floor(at / cols) * CELL_H);
                }
            }
            wrap.dataset.drawn = '';
        };

        // The still frame: the graph fully condensed.
        const stillFrame = () => render(HOLD_UNTIL - 0.5, 0);

        const tick = (stamp: number) => {
            raf = requestAnimationFrame(tick);
            if (stamp - last < FRAME_MS) return;
            const dt = last ? Math.min((stamp - last) / 1000, 0.25) : 0;
            last = stamp;
            render((stamp - start) / 1000, dt);
        };

        const sync = () => {
            cancelAnimationFrame(raf);
            raf = 0;
            last = 0;
            if (still.matches) stillFrame();
            else if (inView && !document.hidden) raf = requestAnimationFrame(tick);
        };

        const resize = () => {
            const dpr = Math.min(window.devicePixelRatio || 1, 2);
            width = wrap.clientWidth;
            height = wrap.clientHeight;
            canvas.width = Math.round(width * dpr);
            canvas.height = Math.round(height * dpr);
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            ctx.font = `${Math.round(CELL_H * 0.72)}px ${mono}`;
            ctx.textBaseline = 'top';
            cols = Math.ceil(width / CELL_W);
            rows = Math.ceil(height / CELL_H);
            level = new Int8Array(cols * rows);
            glyph = new Array(cols * rows).fill('');
            cycle = -1;
            if (still.matches) stillFrame();
            else render((performance.now() - start) / 1000, 0);
        };

        const sizes = new ResizeObserver(resize);
        const seen = new IntersectionObserver(([entry]) => {
            inView = entry.isIntersecting;
            sync();
        });
        sizes.observe(wrap);
        seen.observe(wrap);
        document.addEventListener('visibilitychange', sync);
        still.addEventListener('change', sync);
        resize();
        sync();

        return () => {
            cancelAnimationFrame(raf);
            sizes.disconnect();
            seen.disconnect();
            document.removeEventListener('visibilitychange', sync);
            still.removeEventListener('change', sync);
        };
    }, []);

    return (
        <div ref={wrapRef} aria-hidden="true" className="condensing-graph">
            <canvas ref={canvasRef} className="h-full w-full" />
        </div>
    );
}
