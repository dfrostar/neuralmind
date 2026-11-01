'use client';

import { useEffect, useRef, useState } from 'react';
import type { VRM } from '@pixiv/three-vrm';
import { COPIED_EVENT } from '@/lib/events';

/**
 * The Pair, live: the mascot's VRM (built in VRoid Studio, site/mascot/SPEC.md)
 * drawn with three.js and pixiv's three-vrm.
 *
 * It behaves like the colleague it is meant to be: it blinks and breathes,
 * its eyes and head follow the pointer (the person, so the one thing it
 * watches is you), and it smiles when you copy a command, because copying
 * one is how you start working with it.
 *
 * - **Cost.** three and three-vrm are dynamic imports in their own chunk,
 *   fetched only once the box is on screen and the page has finished
 *   loading, so they never compete with the first paint. A box hidden by
 *   CSS never intersects, so a phone never downloads the model.
 * - **Motion.** Under `prefers-reduced-motion` it is posed once and stays
 *   still: no blink, no breathing, no following, no smile.
 * - **Failure.** No WebGL, or a model that fails to load, and the box
 *   collapses: the page is what it was without a mascot.
 * - **Rendering.** Only while on screen and the tab is visible.
 *
 * `MascotSlot` decides whether this renders at all (only when the .vrm is
 * in site/public/mascot/).
 */

export default function Mascot({
    src,
    poster,
    className = '',
}: {
    src: string;
    /** A still of the model, shown while it loads. */
    poster?: string;
    className?: string;
}) {
    const hostRef = useRef<HTMLDivElement>(null);
    const [state, setState] = useState<'idle' | 'loading' | 'ready' | 'failed'>('idle');

    useEffect(() => {
        const host = hostRef.current;
        if (!host) return;
        let disposed = false;
        let teardown: (() => void) | undefined;

        const start = async () => {
            setState('loading');
            // Held outside the try so a failed load can still free it.
            let created: import('three').WebGLRenderer | undefined;
            try {
                const [THREE, { GLTFLoader }, { VRMLoaderPlugin, VRMUtils }] = await Promise.all([
                    import('three'),
                    import('three/examples/jsm/loaders/GLTFLoader.js'),
                    import('@pixiv/three-vrm'),
                ]);
                if (disposed) return;

                const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' });
                created = renderer;
                renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
                renderer.outputColorSpace = THREE.SRGBColorSpace;
                renderer.domElement.setAttribute('aria-hidden', 'true');
                renderer.domElement.style.width = '100%';
                renderer.domElement.style.height = '100%';

                const scene = new THREE.Scene();
                const camera = new THREE.PerspectiveCamera(22, 1, 0.1, 20);
                // Key light from the upper left; a faint rim in the instrument's
                // blue, read from the tokens, so the silhouette separates from
                // the graphite ground without a glow.
                const css = getComputedStyle(document.documentElement);
                const key = new THREE.DirectionalLight(0xffffff, Math.PI * 0.9);
                key.position.set(1, 1.6, 2.2);
                const rim = new THREE.DirectionalLight(css.getPropertyValue('--evidence').trim() || '#92b3fb', 1.2);
                rim.position.set(-1.4, 1.2, -1.6);
                scene.add(key, rim);

                const loader = new GLTFLoader();
                loader.register((parser) => new VRMLoaderPlugin(parser));
                const gltf = await loader.loadAsync(src);
                if (disposed) {
                    // Unmounted while the model loaded: teardown was never set, so free it here.
                    VRMUtils.deepDispose(gltf.scene);
                    renderer.dispose();
                    renderer.forceContextLoss();
                    return;
                }
                const vrm = gltf.userData.vrm as VRM;
                VRMUtils.removeUnnecessaryVertices(gltf.scene);
                VRMUtils.combineSkeletons(gltf.scene);
                VRMUtils.rotateVRM0(vrm); // VRM 0.x faces the other way; a no-op for VRM 1.0
                vrm.scene.traverse((o) => {
                    o.frustumCulled = false;
                });
                scene.add(vrm.scene);

                // Out of the T-pose: arms down, elbows soft.
                const bone = (name: Parameters<typeof vrm.humanoid.getNormalizedBoneNode>[0]) =>
                    vrm.humanoid.getNormalizedBoneNode(name);
                bone('leftUpperArm')?.rotation.set(0, 0, -1.2);
                bone('rightUpperArm')?.rotation.set(0, 0, 1.2);
                bone('leftLowerArm')?.rotation.set(0, -0.25, 0);
                bone('rightLowerArm')?.rotation.set(0, 0.25, 0);
                vrm.update(0);

                // Frame the head and shoulders, with room above the hair; the
                // record panel below covers the rest. The head bone sits at the
                // base of the skull, so the frame's centre is a little above it.
                const headY = bone('head')?.getWorldPosition(new THREE.Vector3()).y ?? 1.4;
                camera.position.set(0, headY + 0.02, 1.35);
                camera.lookAt(0, headY + 0.02, 0);

                // Where the eyes look: a point in front of the face, moved by the pointer.
                const gaze = new THREE.Object3D();
                gaze.position.set(0, headY, 1.5);
                scene.add(gaze);
                if (vrm.lookAt) vrm.lookAt.target = gaze;

                const resize = () => {
                    const { width, height } = host.getBoundingClientRect();
                    if (!width || !height) return;
                    renderer.setSize(width, height, false);
                    camera.aspect = width / height;
                    camera.updateProjectionMatrix();
                };

                const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
                const pointer = { x: 0, y: 0 };
                const look = { x: 0, y: 0 };
                let smile = 0;
                let smileUntil = 0;
                let nextBlink = performance.now() + 2500;
                let last = performance.now();
                let raf = 0;
                let onScreen = true;

                const frame = (now: number) => {
                    const dt = Math.min((now - last) / 1000, 0.1);
                    last = now;
                    const still = reduce.matches;
                    const t = now / 1000;

                    // Follow the pointer, eased by time so it reads the same at any
                    // frame rate; the head turns part of the way, the eyes the rest.
                    // The model faces +Z, so +Y rotation turns it to screen right
                    // and +X tips its face down.
                    const ease = 1 - Math.exp(-dt * 5);
                    look.x += ((still ? 0 : pointer.x) - look.x) * ease;
                    look.y += ((still ? 0 : pointer.y) - look.y) * ease;
                    gaze.position.set(look.x * 0.9, headY - look.y * 0.6, 1.5);
                    const neck = bone('neck');
                    if (neck) {
                        neck.rotation.y = look.x * 0.45;
                        neck.rotation.x = look.y * 0.2;
                    }

                    // Breathing.
                    const chest = bone('chest') ?? bone('spine');
                    if (chest) chest.rotation.x = still ? 0 : Math.sin(t * 1.7) * 0.018;

                    const face = vrm.expressionManager;
                    if (face) {
                        let blink = 0;
                        if (!still) {
                            const since = now - nextBlink;
                            if (since > 0) blink = since < 90 ? since / 90 : since < 200 ? 1 - (since - 90) / 110 : 0;
                            if (since > 200) nextBlink = now + 2500 + Math.random() * 3500;
                        }
                        smile += ((!still && now < smileUntil ? 1 : 0) - smile) * (1 - Math.exp(-dt * 8));
                        face.setValue('blink', blink);
                        face.setValue('happy', smile);
                    }

                    vrm.update(still ? 0 : dt);
                    renderer.render(scene, camera);
                };

                const loop = (now: number) => {
                    frame(now);
                    raf = requestAnimationFrame(loop);
                };
                const play = () => {
                    cancelAnimationFrame(raf);
                    if (reduce.matches) {
                        frame(performance.now());
                        return;
                    }
                    if (onScreen && !document.hidden) {
                        last = performance.now();
                        raf = requestAnimationFrame(loop);
                    }
                };

                const onPointer = (e: PointerEvent) => {
                    const box = host.getBoundingClientRect();
                    const cx = box.left + box.width / 2;
                    const cy = box.top + box.height * 0.4;
                    pointer.x = Math.max(-1, Math.min(1, (e.clientX - cx) / (window.innerWidth / 2)));
                    pointer.y = Math.max(-1, Math.min(1, (e.clientY - cy) / (window.innerHeight / 2)));
                };
                const onCopied = () => {
                    smileUntil = performance.now() + 1400;
                };
                const visibility = new IntersectionObserver(([entry]) => {
                    onScreen = entry.isIntersecting;
                    play();
                });
                const sizing = new ResizeObserver(() => {
                    resize();
                    if (reduce.matches) frame(performance.now());
                });

                host.appendChild(renderer.domElement);
                resize();
                visibility.observe(host);
                sizing.observe(host);
                window.addEventListener('pointermove', onPointer, { passive: true });
                window.addEventListener(COPIED_EVENT, onCopied);
                document.addEventListener('visibilitychange', play);
                reduce.addEventListener('change', play);
                setState('ready');
                play();

                teardown = () => {
                    cancelAnimationFrame(raf);
                    visibility.disconnect();
                    sizing.disconnect();
                    window.removeEventListener('pointermove', onPointer);
                    window.removeEventListener(COPIED_EVENT, onCopied);
                    document.removeEventListener('visibilitychange', play);
                    reduce.removeEventListener('change', play);
                    VRMUtils.deepDispose(vrm.scene);
                    renderer.dispose();
                    renderer.forceContextLoss();
                    renderer.domElement.remove();
                };
            } catch {
                created?.dispose();
                created?.forceContextLoss();
                if (!disposed) setState('failed');
            }
        };

        // Load once the box is on screen, after the page itself has loaded.
        const whenLoaded = () => {
            if (document.readyState === 'complete') start();
            else window.addEventListener('load', () => start(), { once: true });
        };
        const firstSight = new IntersectionObserver(([entry]) => {
            if (!entry.isIntersecting) return;
            firstSight.disconnect();
            whenLoaded();
        });
        firstSight.observe(host);

        return () => {
            disposed = true;
            firstSight.disconnect();
            teardown?.();
        };
    }, [src]);

    if (state === 'failed') return null;

    return (
        <div ref={hostRef} className={`relative ${className}`} aria-hidden="true">
            {poster && state !== 'ready' && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={poster} alt="" className="absolute inset-0 w-full h-full object-contain object-bottom" />
            )}
        </div>
    );
}
