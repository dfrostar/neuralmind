'use client';

import { useState } from 'react';

const faqs = [
    {
        q: 'How is this different from RAG?',
        a: 'RAG stores chunks and retrieves by similarity. NeuralMind learns HOW you use code — which functions you look at together, which modules correlate, which tools you run after reading what. That co-activation signal is what makes the synapse layer outperform plain RAG on real agent workloads.',
    },
    {
        q: 'Does it work with my agent?',
        a: 'Yes. NeuralMind exposes an MCP server, and we support Claude Code (hooks), Cursor, Cline, Continue, and any MCP-compatible agent. We also have an HTTP API and a CLI.',
    },
    {
        q: 'Does any code leave my machine?',
        a: 'NeuralMind itself makes no external calls — the graph, embeddings, and synapse store are all local, with zero telemetry. The only thing that leaves is the minimal context slice your AI agent (Claude Code, Cursor, etc.) sends to its own model on each query — which is exactly what NeuralMind shrinks 40–70× versus pasting whole files.',
    },
    {
        q: 'What is the CI-gated tuner?',
        a: 'A self-improvement engine landing in the next release: a population-based evolutionary search over NeuralMind\'s own retrieval parameters. Candidate configs are evaluated against your fixture queries by an independent quality harness. Promotion requires both harness pass AND beating the incumbent by a hysteresis margin. The daemon proposes; the harness disposes.',
    },
    {
        q: 'What does "free tier auto-provision" mean?',
        a: 'When you run `neuralmind wakeup .` for the first time, NeuralMind checks if a license file exists at `~/.config/neuralmind/license.json`. If not, it auto-issues a free license (tier="free", seats=1, expires="never") — no signup, no payment, no account. Your identity is created on first meaningful action.',
    },
    {
        q: 'Is NeuralMind free? What does the paid tier actually buy?',
        a: 'The MIT core is free forever — including all of the token compression; the 40–70× savings cost nothing. A 1-seat free license auto-issues the first time you run `neuralmind wakeup .`, no signup. NeuralMind Team ($29/user/mo, annual, 5–50 seats) adds what engineering organizations need on top: admin-controlled memory governance, a tamper-evident hash-chained audit log, seat management, and self-hosted deployment. You are paying for compliance and control, not for the compression.',
    },
    {
        q: 'What\'s the business case for a team?',
        a: 'Two lines: the measured token reduction (free, verify it on your own repo in ~15 minutes), and modeled productivity recovery — engineers stop losing hours to context-limit thrashing and re-prompting. We publish the full model with its assumptions, and the free assessment runs it in your numbers. If your workload is generation-heavy or prompt caching already covers you, we say so.',
    },
    {
        q: 'What languages does it support?',
        a: 'Ten out-of-the-box: Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby, and PHP. tree-sitter handles parsing.',
    },
    {
        q: 'How does team memory work?',
        a: 'A team\'s learned associations (which code goes with what) are committed to the repo as .neuralmind-team-memory.json. Every teammate\'s agent inherits it automatically on the next session — a new hire\'s agent starts already knowing "the auth handlers go with the JWT utils," instead of relearning from scratch. Zero manual steps, travels with git clone.',
    },
    {
        q: 'Why not just use Cursor / Windsurf / Aider memory?',
        a: 'They vendor-lock memory to their agent. NeuralMind is agent-agnostic. Memory persists across agent migrations, is inspectable, and belongs to you.',
    },
    {
        q: 'Explain "40–70× token reduction" more concretely',
        a: 'When your agent asks "How does auth work?", a naive approach pastes every file (~5K–30K tokens). NeuralMind retrieves L0 (symbol/structure) + L1 (docstrings/comment) + L2 (method body, selective) + L3 (only if hit-rate requires). Result: exact context needed, typically 500–800 tokens, measured in CI on every commit.',
    },
];

export default function FAQ() {
    const [openIndex, setOpenIndex] = useState<number | null>(null);

    return (
        <section id="faq" className="relative py-16 md:py-32 px-4 md:px-6">
            <div className="max-w-3xl mx-auto">
                <div className="text-center mb-12 md:mb-16">
                    <span className="text-electric text-sm font-semibold tracking-wider uppercase mb-3 block">
                        FAQ
                    </span>
                    <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
                        Common questions
                    </h2>
                </div>

                <div className="space-y-3">
                    {faqs.map((faq, i) => (
                        <div
                            key={i}
                            className="glow-card rounded-xl overflow-hidden"
                        >
                            <button
                                onClick={() => setOpenIndex(openIndex === i ? null : i)}
                                className="w-full px-6 py-5 flex items-center justify-between text-left"
                            >
                                <span className="font-semibold text-white pr-4">{faq.q}</span>
                                <svg
                                    className={`w-5 h-5 text-slate-400 shrink-0 transition-transform duration-200 ${
                                        openIndex === i ? 'rotate-180' : ''
                                    }`}
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                            </button>
                            {openIndex === i && (
                                <div className="px-6 pb-5 pt-0">
                                    <p className="text-slate-400 leading-relaxed text-sm">{faq.a}</p>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
