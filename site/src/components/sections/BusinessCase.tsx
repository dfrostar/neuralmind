'use client';

import SectionHeader from '@/components/ui/SectionHeader';

// Dollar figures are modeled in docs/BUSINESS-CASE.md, assumptions published
// there. Quote its scenarios as written — the "$1,650/mo" that used to sit here
// was a math error the doc itself corrected on 2026-07-31.
const cards = [
    {
        audience: 'For the CFO',
        title: 'The savings are free',
        accent: 'text-proton',
        points: [
            'Token reduction ships in the free MIT core — the savings cost nothing, and you can measure them on your own repo in ~15 minutes.',
            'Modeled at 30 code questions per developer per day, a 50-developer team saves ~$310/mo on inference alone. The figure barely moves with the exact ratio — 48.8× and 65.6× (both against the fixed 50K-token estimate the CLI used before v4.5.0) differ by under 1% of the saving, because both already remove ~98% of the retrieval tokens.',
            'Time may be the bigger line, but it is modeled, not measured. The business case’s worked scenario — 15 developers each losing 15 minutes a day to context-limit thrashing — puts it at ~$4,125/mo at a $50/hr fully-loaded rate. How much of that NeuralMind wins back is what the free assessment measures in your team; we don’t claim a figure.',
            'Recall is a local index lookup, not another model call — nothing in the loop between "I need to know X" and "I know X" waits on an API.',
        ],
    },
    {
        audience: 'For the CTO',
        title: 'Fewer wrong turns, faster teams',
        accent: 'text-electric',
        points: [
            '97.5% mean gold-file recall across 40 pre-registered queries on four public repos — 90–100% per repo, with every miss published rather than dropped.',
            'Team memory travels with git: a new hire’s agent starts with the associations the team has already earned instead of relearning them.',
            'Read-only dashboard for synapse memory health, ingestion, savings and latency trends — local, no hosted service.',
            'By default NeuralMind sends no telemetry and transmits no repository content off your machine. It works with the agents you already run — Claude Code, Codex, Cursor, Cline, any MCP agent. No rip-and-replace.',
        ],
    },
];

export default function BusinessCase() {
    return (
        <section id="business-case" className="relative py-16 md:py-32 px-4 md:px-6">

            <div className="max-w-5xl mx-auto">
                <SectionHeader eyebrow="The business case" title="The savings are free. Teams pay for seats and support.">
                    Every feature runs free at one seat. Dollar figures below are modeled, with
                    published assumptions — the free assessment runs the same model in your numbers.
                </SectionHeader>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6 mb-10">
                    {cards.map((card) => (
                        <div key={card.audience} className="card rounded-2xl p-6 md:p-8">
                            <span className={`text-xs font-semibold uppercase tracking-wider ${card.accent} mb-2 block`}>
                                {card.audience}
                            </span>
                            <h3 className="font-display text-xl md:text-2xl font-bold text-white mb-4">{card.title}</h3>
                            <ul className="space-y-3">
                                {card.points.map((point) => (
                                    <li key={point} className="flex items-start gap-3 text-sm text-slate-300 leading-relaxed">
                                        <svg className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                        </svg>
                                        {point}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </div>

                <div className="flex flex-col sm:flex-row items-center justify-center gap-6 text-sm">
                    <a
                        href="https://github.com/dfrostar/neuralmind/blob/main/docs/BUSINESS-CASE.md"
                        className="text-electric hover:text-white transition-colors font-medium"
                    >
                        Read the full business case, assumptions included →
                    </a>
                    <a
                        href="#assessment"
                        className="text-proton hover:text-white transition-colors font-medium"
                    >
                        Get the numbers for your team →
                    </a>
                </div>
            </div>
        </section>
    );
}
