'use client';

import { useState, useEffect } from 'react';

const tags = ['Claude Code', 'Codex', 'Cursor', 'Cline', 'Continue', 'MCP'];
const heroStats = [
    { label: 'Token Ratio', value: '12–50×', highlight: true },
    { label: 'Languages Indexed', value: '10', highlight: false },
    { label: 'Gold-File Recall', value: '100%', highlight: false },
    { label: 'Free Tier', value: 'Auto-provisioned', highlight: false },
];

export default function Hero() {
    const [tagIndex, setTagIndex] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setTagIndex((i) => (i + 1) % tags.length);
        }, 2400);
        return () => clearInterval(interval);
    }, []);

    return (
        <section className="relative min-h-screen flex items-center justify-center overflow-hidden pt-20 pb-16">
            {/* gradient background */}
            <div className="absolute inset-0 -z-10">
                <div className="absolute top-1/4 -left-1/4 w-[600px] h-[600px] bg-electric/5 rounded-full blur-[120px]" />
                <div className="absolute bottom-1/4 -right-1/4 w-[600px] h-[600px] bg-proton/5 rounded-full blur-[120px]" />
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-iris/3 rounded-full blur-[150px]" />
            </div>

            <div className="max-w-4xl mx-auto px-4 md:px-6 text-center">
                {/* Agent compatibility tag */}
                <div className="inline-flex items-center gap-2 mb-8 px-4 py-2 rounded-full border border-carbon-border bg-carbon-raised/80 backdrop-blur-sm">
                    <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                    <span className="text-slate-400 text-sm font-medium">Native for</span>
                    <span className="text-white font-semibold text-sm">{tags[tagIndex]}</span>
                </div>

                {/* Main headline */}
                <h1 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-white leading-[1.05] mb-6">
                    Your agent learns your codebase.{' '}
                    <span className="gradient-text">And remembers it.</span>
                </h1>

                {/* Subhead */}
                <p className="text-base sm:text-lg md:text-xl text-slate-400 max-w-2xl mx-auto mb-8 leading-relaxed">
                    Persistent neural memory for AI agents. Local-first synapse layer that cuts token costs{' '}
                    <span className="text-white font-semibold">12–50×</span>.
                    Built-in install doctor, Obsidian-style graph view, and honest benchmarks — measured, not marketed.
                </p>

                {/* CTA buttons */}
                <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-12">
                    <a
                        href="#install"
                        className="btn-primary flex items-center gap-2 px-8 py-4 text-base"
                    >
                        <code className="font-mono text-sm bg-black/30 px-2 py-1 rounded overflow-auto">pip install neuralmind</code>
                    </a>
                    <a
                        href="https://github.com/dfrostar/neuralmind"
                        className="px-6 py-4 rounded-xl border border-carbon-border text-slate-300 hover:text-white hover:border-electric/40 transition-all font-medium flex items-center gap-2"
                    >
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                        </svg>
                        Source on GitHub
                    </a>
                    <a
                        href="/pricing"
                        className="px-6 py-4 rounded-xl border border-electric/40 text-white hover:bg-electric/10 transition-all font-medium flex items-center gap-2"
                    >
                        For teams →
                    </a>
                </div>

                {/* Stats */}
                <div className="flex flex-wrap justify-center gap-4 md:gap-8 mb-8">
                    {heroStats.map((stat) => (
                        <div key={stat.label} className="flex items-center gap-3 min-w-[120px] flex-1 justify-center">
                            <span className={`font-display text-2xl font-bold ${stat.highlight ? 'gradient-text' : 'text-white'}`}>
                                {stat.value}
                            </span>
                            <span className="text-slate-500 text-sm font-medium">{stat.label}</span>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
