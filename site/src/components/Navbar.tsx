'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import Logo from '@/components/ui/Logo';

// Root-relative so the menu works from every page, not just the homepage.
// A bare "#benchmarks" does nothing on /security, /privacy, /terms — those
// sections only exist on "/". "/#benchmarks" navigates home, then scrolls.
//
// All ten destinations are still reachable; they are grouped now rather than
// laid out as ten equal-weight links that only stopped colliding at 1280px
// and collapsed to a hamburger on every laptop below it.
type NavItem = { href: string; label: string; hint?: string };

const productLinks: NavItem[] = [
    { href: '/#how-it-works', label: 'How it works', hint: 'Index, query, remember' },
    { href: '/#features', label: 'Features', hint: 'The full capability list' },
    { href: '/#benchmarks', label: 'Benchmarks', hint: 'What CI measures, and how' },
    { href: '/effectiveness', label: 'Effectiveness', hint: 'Before / after, misses included' },
];

const resourceLinks: NavItem[] = [
    { href: '/publications', label: 'Research', hint: 'Write-ups and methodology' },
    { href: '/#assessment', label: 'Assessment', hint: 'Free spend analysis' },
    { href: '/#faq', label: 'FAQ', hint: 'Common questions' },
    { href: 'https://docs.neuralmind.uk/wiki/Home', label: 'Docs', hint: 'CLI and wiki' },
];

const directLinks: NavItem[] = [
    { href: '/pricing', label: 'Pricing' },
    { href: '/team', label: 'Teams' },
    { href: '/services', label: 'Services' },
];

function Dropdown({ label, items }: { label: string; items: NavItem[] }) {
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    // Click-outside and Escape. A hover-only menu is unusable by keyboard and
    // unreachable by touch, so this opens on click and closes on both.
    useEffect(() => {
        if (!open) return;
        const onPointer = (e: PointerEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        };
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') setOpen(false);
        };
        document.addEventListener('pointerdown', onPointer);
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('pointerdown', onPointer);
            document.removeEventListener('keydown', onKey);
        };
    }, [open]);

    return (
        <div ref={ref} className="relative">
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-expanded={open}
                aria-haspopup="true"
                className={`flex items-center gap-1.5 text-sm transition-colors py-2 ${
                    open ? 'text-white' : 'text-slate-400 hover:text-white'
                }`}
            >
                {label}
                <svg
                    viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth={1.5}
                    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
                    className={`w-3 h-3 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
                >
                    <path d="M3 4.5 6 7.5 9 4.5" />
                </svg>
            </button>

            {open && (
                <div className="absolute left-0 top-full pt-2 w-[17rem] animate-fade-in">
                    <div className="panel rounded-xl p-1.5 shadow-2xl shadow-black/50">
                        {items.map((item) => (
                            <Link
                                key={item.href}
                                href={item.href}
                                onClick={() => setOpen(false)}
                                className="block px-3 py-2.5 rounded-lg hover:bg-white/[0.045] transition-colors group"
                            >
                                <span className="block text-sm text-slate-200 group-hover:text-white font-medium">
                                    {item.label}
                                </span>
                                {item.hint && (
                                    <span className="block text-xs text-faint mt-0.5">{item.hint}</span>
                                )}
                            </Link>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

export default function Navbar() {
    const [open, setOpen] = useState(false);
    const [scrolled, setScrolled] = useState(false);

    // The bar is borderless over the hero and gains its hairline once the page
    // moves, so it reads as part of the page rather than a strip bolted on top.
    useEffect(() => {
        const onScroll = () => setScrolled(window.scrollY > 8);
        onScroll();
        window.addEventListener('scroll', onScroll, { passive: true });
        return () => window.removeEventListener('scroll', onScroll);
    }, []);

    const allMobileLinks = [...productLinks, ...resourceLinks, ...directLinks];

    return (
        <nav
            className={`fixed top-0 left-0 right-0 z-50 backdrop-blur-xl transition-colors duration-200 ${
                scrolled ? 'bg-carbon/85 border-b border-carbon-border' : 'bg-carbon/40 border-b border-transparent'
            }`}
        >
            <div className="max-w-6xl mx-auto px-4 md:px-6 h-16 flex items-center justify-between gap-6">
                <Link href="/" className="flex items-center gap-2.5 shrink-0 group">
                    <Logo className="w-[1.625rem] h-[1.625rem] text-electric transition-colors group-hover:text-electric-bright" />
                    <span className="font-display font-semibold text-[1.0625rem] tracking-tight text-white">
                        NeuralMind
                    </span>
                </Link>

                <div className="hidden lg:flex items-center gap-6">
                    <Dropdown label="Product" items={productLinks} />
                    <Dropdown label="Resources" items={resourceLinks} />
                    {directLinks.map((link) => (
                        <Link
                            key={link.href}
                            href={link.href}
                            className="text-sm text-slate-400 hover:text-white transition-colors py-2"
                        >
                            {link.label}
                        </Link>
                    ))}
                </div>

                <div className="hidden lg:flex items-center gap-4 shrink-0">
                    <Link
                        href="https://github.com/dfrostar/neuralmind"
                        aria-label="NeuralMind on GitHub"
                        className="text-slate-400 hover:text-white transition-colors"
                    >
                        <svg className="w-[1.125rem] h-[1.125rem]" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                        </svg>
                    </Link>
                    <Link href="https://pypi.org/project/neuralmind/" className="btn-primary text-sm py-2">
                        Install
                    </Link>
                </div>

                <button
                    className="lg:hidden text-slate-400 hover:text-white -mr-1 p-1"
                    onClick={() => setOpen(!open)}
                    aria-expanded={open}
                    aria-label="Toggle menu"
                >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" aria-hidden="true">
                        {open ? (
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        ) : (
                            <path strokeLinecap="round" strokeLinejoin="round" d="M4 7h16M4 12h16M4 17h16" />
                        )}
                    </svg>
                </button>
            </div>

            {open && (
                <div className="lg:hidden border-t border-carbon-border bg-carbon/95 backdrop-blur-xl max-h-[calc(100vh-4rem)] overflow-y-auto">
                    <div className="px-4 py-4 flex flex-col gap-1">
                        {allMobileLinks.map((link) => (
                            <Link
                                key={link.href}
                                href={link.href}
                                className="text-slate-300 hover:text-white transition-colors text-[0.9375rem] py-2.5"
                                onClick={() => setOpen(false)}
                            >
                                {link.label}
                            </Link>
                        ))}
                        <Link
                            href="https://github.com/dfrostar/neuralmind"
                            className="text-slate-300 hover:text-white transition-colors text-[0.9375rem] py-2.5"
                            onClick={() => setOpen(false)}
                        >
                            GitHub
                        </Link>
                        <Link
                            href="https://pypi.org/project/neuralmind/"
                            className="btn-primary text-sm mt-3"
                            onClick={() => setOpen(false)}
                        >
                            Install
                        </Link>
                    </div>
                </div>
            )}
        </nav>
    );
}
