'use client';

import { useState, useEffect } from 'react';
import CommandLine from '@/components/ui/CommandLine';
import Icon from '@/components/ui/Icon';

const tags = ['Claude Code', 'Codex', 'Cursor', 'Cline', 'Continue', 'MCP'];

// Every figure here is registered in site/claims.json with its source and
// reproduction command, and gated by tests/test_site_claims.py.
//
// `evidence` is new, and it is presentational only — it labels which kind of
// claim each figure is, the same grading the Benchmarks table already applies.
// The site's own rule is that a CI gate and a per-repo mean are not the same
// strength of claim, so the hero should not render them identically.
const heroStats = [
    { label: 'Gold-file recall', value: '93.75%', evidence: 'mean, 79–100% per repo', figure: true },
    { label: 'vs. pasting files', value: '45–257×', evidence: 'fewer tokens', figure: true },
    { label: 'Pre-registered queries', value: '40', evidence: 'four public repos', figure: true },
    { label: 'Free tier', value: 'Auto-provisioned', evidence: 'no signup', figure: false },
];

// Real commands, verified against neuralmind/cli.py. Nothing here prints
// fabricated output — the terminal shows the three calls you actually make.
const session = [
    { prompt: '$', cmd: 'pip install neuralmind' },
    { prompt: '$', cmd: 'neuralmind build .' },
    { prompt: '$', cmd: 'neuralmind query "where is auth handled?"' },
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
        <section className="relative overflow-hidden pt-32 pb-16 md:pt-40 md:pb-20">
            {/* A 72px hairline grid, masked to fade out. Replaces three
                600–800px blurred blue/purple radial blobs. */}
            <div className="grid-bg absolute inset-0 -z-10" aria-hidden="true" />

            <div className="max-w-6xl mx-auto px-4 md:px-6">
                <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] gap-12 lg:gap-14 items-center">
                    {/* ── Copy ───────────────────────────────────────────── */}
                    <div>
                        <div className="inline-flex items-center gap-2.5 mb-8 pl-3 pr-4 py-1.5 rounded-full border border-carbon-border bg-carbon-raised">
                            <span className="w-1.5 h-1.5 rounded-full bg-proton" />
                            <span className="text-faint text-[0.8125rem]">Native for</span>
                            <span className="relative grid text-slate-100 font-medium text-[0.8125rem]">
                                {/* Every name stacked in one cell: the widest sets the
                                    width, so the pill never resizes mid-rotation. */}
                                {tags.map((tag, i) => (
                                    <span
                                        key={tag}
                                        aria-hidden={i !== tagIndex}
                                        className={`col-start-1 row-start-1 transition-opacity duration-500 ${
                                            i === tagIndex ? 'opacity-100' : 'opacity-0'
                                        }`}
                                    >
                                        {tag}
                                    </span>
                                ))}
                            </span>
                        </div>

                        <h1 className="font-display text-4xl sm:text-5xl lg:text-[3.5rem] font-semibold text-white leading-[1.04] tracking-tightest mb-6">
                            Your team uses Claude Code?{' '}
                            <span className="gradient-text">Now it remembers your codebase.</span>
                        </h1>

                        <p className="text-slate-400 text-base sm:text-lg leading-relaxed max-w-xl mb-9">
                            Persistent neural memory for AI agents. Your agent opens the right file
                            first — <span className="text-slate-100 font-medium">93.75% gold-file recall across 40
                            pre-registered queries on four public repos</span>, at 45–257× fewer tokens than
                            pasting those files in. Local-first, no telemetry.
                        </p>

                        <div className="flex flex-wrap items-center gap-3">
                            <CommandLine command="pip install neuralmind" />
                            <a href="/pricing" className="btn-primary py-3">
                                For teams
                                <Icon name="arrow-right" className="w-4 h-4" />
                            </a>
                            <a
                                href="https://github.com/dfrostar/neuralmind"
                                className="btn-secondary py-3"
                            >
                                <svg className="w-[1.125rem] h-[1.125rem]" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                                </svg>
                                Source
                            </a>
                        </div>
                    </div>

                    {/* ── Terminal ───────────────────────────────────────── */}
                    <div className="panel rounded-xl overflow-hidden shadow-2xl shadow-black/40">
                        <div className="flex items-center gap-2 px-4 py-3 border-b border-carbon-border bg-carbon-raised">
                            <span className="w-2.5 h-2.5 rounded-full bg-carbon-line" />
                            <span className="w-2.5 h-2.5 rounded-full bg-carbon-line" />
                            <span className="w-2.5 h-2.5 rounded-full bg-carbon-line" />
                            <span className="ml-2 font-mono text-[0.6875rem] text-faint tracking-wide">
                                your-repo — zsh
                            </span>
                        </div>
                        <div className="p-5 font-mono text-[0.8125rem] leading-loose">
                            {session.map((line) => (
                                <div key={line.cmd} className="flex gap-2.5">
                                    <span className="text-proton select-none shrink-0">{line.prompt}</span>
                                    <span className="text-slate-300 break-words">{line.cmd}</span>
                                </div>
                            ))}
                            <div className="flex gap-2.5 mt-1">
                                <span className="text-proton select-none shrink-0">$</span>
                                <span className="w-2 h-[1.1em] bg-slate-600 translate-y-[0.2em]" />
                            </div>
                        </div>
                    </div>
                </div>

                {/* ── Stats ──────────────────────────────────────────────── */}
                <dl className="grid grid-cols-2 lg:grid-cols-4 border-t border-l border-carbon-border rounded-sm overflow-hidden mt-14 md:mt-20">
                    {heroStats.map((stat) => (
                        <div key={stat.label} className="border-b border-r border-carbon-border px-5 py-6">
                            <dd
                                className={
                                    stat.figure
                                        ? 'metric text-2xl md:text-[1.75rem] text-white mb-2 leading-none'
                                        : 'font-display text-xl md:text-2xl font-semibold tracking-tight text-white mb-2 leading-none'
                                }
                            >
                                {stat.value}
                            </dd>
                            <dt className="text-slate-300 text-sm font-medium mb-1">{stat.label}</dt>
                            <p className="text-faint text-xs">{stat.evidence}</p>
                        </div>
                    ))}
                </dl>
            </div>
        </section>
    );
}
