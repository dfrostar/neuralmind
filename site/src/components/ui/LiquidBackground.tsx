'use client';

import { useEffect, useRef } from 'react';

/**
 * The liquid behind every page.
 *
 * A fixed WebGL canvas drawing a domain-warped noise field in the graphite
 * steps, with hairline currents along its level sets, a faint sheen of the
 * instrument's blue where the field runs fast, and a swirl of amber where the
 * pointer is: amber is the person's colour everywhere else on the site, so the
 * one thing in the liquid that answers you is amber too. It flows on its own,
 * drifts as the page scrolls, and bends around the pointer.
 *
 * It is a background, so it may never cost the copy anything:
 *
 * - **Contrast.** The shader clamps every pixel's relative luminance to
 *   `CAP`, under the 0.0155 at which `faint` text drops below 4.5:1, so the
 *   tokens' AA ratios hold on top of it.
 * - **Motion.** Under `prefers-reduced-motion` it draws one still frame and
 *   ignores the pointer and scroll. It stops while the tab is hidden.
 * - **Cost.** It renders at well under device resolution (the field is soft,
 *   so upscaling is invisible) and at most every other animation frame.
 * - **Failure.** Without WebGL or JavaScript nothing is drawn and the page
 *   keeps its solid `carbon` ground; the canvas is aria-hidden and takes no
 *   pointer events.
 *
 * Colours are read from the `:root` tokens in globals.css, not repeated here.
 */

const CAP = 0.014;
const SCALE = 0.55; // canvas pixels per CSS pixel
const MAX_SIDE = 1100; // and never wider or taller than this

const VERTEX = `
attribute vec2 aPos;
void main() { gl_Position = vec4(aPos, 0.0, 1.0); }
`;

const FRAGMENT = `
precision highp float;
uniform vec2 uRes;
uniform float uTime;
uniform vec2 uPointer;
uniform float uTouch;
uniform float uScroll;
uniform vec3 uDeep;
uniform vec3 uGround;
uniform vec3 uRule;
uniform vec3 uCool;
uniform vec3 uWarm;
uniform float uCap;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    mat2 m = mat2(1.6, 1.2, -1.2, 1.6);
    for (int i = 0; i < 5; i++) {
        v += a * noise(p);
        p = m * p;
        a *= 0.5;
    }
    return v;
}

vec2 toField(vec2 px) {
    vec2 p = (px - 0.5 * uRes) / min(uRes.x, uRes.y) * 1.8;
    p.y -= uScroll;
    return p;
}

void main() {
    vec2 p = toField(gl_FragCoord.xy);
    float t = uTime * 0.035;

    vec2 q = vec2(fbm(p + vec2(0.0, t)), fbm(p + vec2(5.2, 1.3) - t));

    vec2 d = p - toField(uPointer);
    float touch = uTouch * exp(-dot(d, d) * 9.0);

    vec2 r = vec2(fbm(p + 3.0 * q + vec2(1.7, 9.2) + 0.15 * t),
                  fbm(p + 3.0 * q + vec2(8.3, 2.8) - 0.12 * t));
    r += touch * 0.35 * vec2(-d.y, d.x);

    float f = fbm(p + 3.0 * r);

    vec3 col = mix(uDeep, uGround, smoothstep(0.15, 0.85, f));

    float line = 1.0 - smoothstep(0.0, 0.035, abs(fract(f * 9.0) - 0.5));
    col = mix(col, uRule, line * 0.6 * smoothstep(0.3, 0.75, length(q)));
    col += uCool * 0.05 * smoothstep(0.55, 1.0, r.x);
    col += uWarm * touch * (0.01 + 0.4 * line);

    float y = dot(col, vec3(0.2126, 0.7152, 0.0722));
    if (y > uCap) col *= uCap / y;

    gl_FragColor = vec4(pow(col, vec3(1.0 / 2.4)), 1.0);
}
`;

/** A `#rrggbb` token as linear RGB, which is what the shader mixes in. */
function tokenLinear(styles: CSSStyleDeclaration, name: string): [number, number, number] {
    const hex = styles.getPropertyValue(name).trim().replace('#', '');
    const channel = (i: number) => {
        const c = parseInt(hex.slice(i, i + 2), 16) / 255;
        return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    };
    return [channel(0), channel(2), channel(4)];
}

function compile(gl: WebGLRenderingContext, type: number, source: string) {
    const shader = gl.createShader(type);
    if (!shader) return null;
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    return gl.getShaderParameter(shader, gl.COMPILE_STATUS) ? shader : null;
}

export default function LiquidBackground() {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const gl = canvas.getContext('webgl', { antialias: false, alpha: false, powerPreference: 'low-power' });
        if (!gl) return;

        const vs = compile(gl, gl.VERTEX_SHADER, VERTEX);
        const fs = compile(gl, gl.FRAGMENT_SHADER, FRAGMENT);
        const program = gl.createProgram();
        if (!vs || !fs || !program) return;
        gl.attachShader(program, vs);
        gl.attachShader(program, fs);
        gl.linkProgram(program);
        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
        gl.useProgram(program);

        const buffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
        const aPos = gl.getAttribLocation(program, 'aPos');
        gl.enableVertexAttribArray(aPos);
        gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

        const u = (name: string) => gl.getUniformLocation(program, name);
        const styles = getComputedStyle(document.documentElement);
        gl.uniform3fv(u('uDeep'), tokenLinear(styles, '--bg-raised'));
        gl.uniform3fv(u('uGround'), tokenLinear(styles, '--bg-card'));
        gl.uniform3fv(u('uRule'), tokenLinear(styles, '--border-strong'));
        gl.uniform3fv(u('uCool'), tokenLinear(styles, '--evidence'));
        gl.uniform3fv(u('uWarm'), tokenLinear(styles, '--accent'));
        gl.uniform1f(u('uCap'), CAP);
        const uRes = u('uRes');
        const uTime = u('uTime');
        const uPointer = u('uPointer');
        const uTouch = u('uTouch');
        const uScroll = u('uScroll');

        const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
        let scale = SCALE;
        let frame = 0;
        let raf = 0;
        let running = false;
        const start = performance.now();
        // The pointer eases toward where it is, and its touch fades over ~2s.
        const pointer = { x: 0, y: 0, tx: 0, ty: 0, touch: 0 };

        const resize = () => {
            const w = window.innerWidth;
            const h = window.innerHeight;
            scale = Math.min(SCALE, MAX_SIDE / Math.max(w, h));
            canvas.width = Math.max(1, Math.round(w * scale));
            canvas.height = Math.max(1, Math.round(h * scale));
            gl.viewport(0, 0, canvas.width, canvas.height);
            gl.uniform2f(uRes, canvas.width, canvas.height);
        };

        const draw = (now: number) => {
            const still = reduce.matches;
            pointer.x += (pointer.tx - pointer.x) * 0.08;
            pointer.y += (pointer.ty - pointer.y) * 0.08;
            pointer.touch *= 0.985;
            gl.uniform1f(uTime, still ? 0 : (now - start) / 1000);
            gl.uniform2f(uPointer, pointer.x * scale, (window.innerHeight - pointer.y) * scale);
            gl.uniform1f(uTouch, still ? 0 : pointer.touch);
            gl.uniform1f(uScroll, still ? 0 : (window.scrollY / window.innerHeight) * 0.35);
            gl.drawArrays(gl.TRIANGLES, 0, 3);
            canvas.dataset.drawn = 'true';
        };

        const loop = (now: number) => {
            raf = requestAnimationFrame(loop);
            frame += 1;
            if (frame % 2 === 0) draw(now);
        };

        const play = () => {
            if (running || reduce.matches || document.hidden) return;
            running = true;
            raf = requestAnimationFrame(loop);
        };

        const pause = () => {
            running = false;
            cancelAnimationFrame(raf);
        };

        const onPointer = (e: PointerEvent) => {
            pointer.tx = e.clientX;
            pointer.ty = e.clientY;
            if (pointer.touch < 0.02) {
                pointer.x = e.clientX;
                pointer.y = e.clientY;
            }
            pointer.touch = 1;
        };

        const onVisibility = () => (document.hidden ? pause() : play());

        const onMotionChange = () => {
            pause();
            draw(performance.now());
            play();
        };

        const onResize = () => {
            resize();
            if (!running) draw(performance.now());
        };

        resize();
        draw(start);
        play();

        window.addEventListener('resize', onResize);
        window.addEventListener('pointermove', onPointer, { passive: true });
        document.addEventListener('visibilitychange', onVisibility);
        reduce.addEventListener('change', onMotionChange);

        return () => {
            pause();
            window.removeEventListener('resize', onResize);
            window.removeEventListener('pointermove', onPointer);
            document.removeEventListener('visibilitychange', onVisibility);
            reduce.removeEventListener('change', onMotionChange);
            gl.getExtension('WEBGL_lose_context')?.loseContext();
        };
    }, []);

    return <canvas ref={canvasRef} className="liquid-bg" aria-hidden="true" />;
}
