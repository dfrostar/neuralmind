'use client';

import Link from 'next/link';
import { useState } from 'react';

// Root-relative so the menu works from every page, not just the homepage.
// A bare "#benchmarks" does nothing on /security, /privacy, /terms — those
// sections only exist on "/". "/#benchmarks" navigates home, then scrolls.
const navLinks = [
    { href: '/#how-it-works', label: 'How it works' },
    { href: '/#benchmarks', label: 'Benchmarks' },
    { href: '/effectiveness', label: 'Effectiveness' },
    { href: '/publications', label: 'Research' },
    { href: '/#features', label: 'Features' },
    { href: '/pricing', label: 'Pricing' },
    { href: '/team', label: 'Teams' },
    { href: '/#assessment', label: 'Assessment' },
    { href: '/#faq', label: 'FAQ' },
];

export default function Navbar() {
    const [open, setOpen] = useState(false);

    return (
        <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md bg-carbon/80 border-b border-carbon-border/50">
            <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
                <Link href="/" className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-electric to-proton flex items-center justify-center text-center leading-none">
                        <span className="text-white font-display font-bold text-sm">N</span>
                    </div>
                    <span className="font-display font-bold text-xl tracking-tight text-white">
                        NeuralMind
                    </span>
                </Link>

                <div className="hidden md:flex items-center gap-8">
                    {navLinks.map((link) => (
                        <Link
                            key={link.href}
                            href={link.href}
                            className="text-slate-400 hover:text-white transition-colors text-sm font-medium"
                        >
                            {link.label}
                        </Link>
                    ))}
                </div>

                <div className="hidden md:flex items-center gap-4">
                    <Link
                        href="https://docs.neuralmind.uk/wiki/Home"
                        className="text-slate-400 hover:text-white transition-colors text-sm font-medium"
                    >
                        Docs
                    </Link>
                    <Link
                        href="https://github.com/dfrostar/neuralmind"
                        className="text-slate-400 hover:text-white transition-colors text-sm font-medium"
                    >
                        GitHub
                    </Link>
                    <Link
                        href="https://pypi.org/project/neuralmind/"
                        className="btn-primary text-sm"
                    >
                        Install
                    </Link>
                </div>

                <button
                    className="md:hidden text-slate-400 hover:text-white"
                    onClick={() => setOpen(!open)}
                    aria-label="Toggle menu"
                >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        {open ? (
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        ) : (
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                        )}
                    </svg>
                </button>
            </div>

            {open && (
                <div className="md:hidden border-t border-carbon-border/50 bg-carbon/95 backdrop-blur-md">
                    <div className="px-6 py-4 flex flex-col gap-3">
                        {navLinks.map((link) => (
                            <Link
                                key={link.href}
                                href={link.href}
                                className="text-slate-400 hover:text-white transition-colors text-sm font-medium py-2"
                                onClick={() => setOpen(false)}
                            >
                                {link.label}
                            </Link>
                        ))}
                        <Link
                            href="https://docs.neuralmind.uk/wiki/Home"
                            className="text-slate-400 hover:text-white transition-colors text-sm font-medium py-2"
                            onClick={() => setOpen(false)}
                        >
                            Docs
                        </Link>
                        <Link
                            href="https://pypi.org/project/neuralmind/"
                            className="btn-primary text-sm text-center"
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
