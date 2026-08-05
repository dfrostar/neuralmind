'use client';

const cards = [
    {
        audience: 'For the CFO',
        title: 'The savings are free',
        accent: 'text-proton',
        points: [
            'The 65.6× token compression ships in the free MIT core — the savings cost nothing, and you can measure them on your own repo in ~15 minutes.',
            'Modeled at 30 code questions per developer per day, a 50-developer team gets back ~$310/mo on inference alone (at 65.6×).',
            'The bigger line is time: ~$1,650/mo per 50-dev team recovered from context-limit thrashing and re-prompting, at a $50/hr fully-loaded rate.',
            'Sub-second queries (0.81s) mean no more waiting 8+ seconds per question. That compounds across every developer, every day.',
        ],
    },
    {
        audience: 'For the CTO',
        title: 'Fewer wrong answers, faster teams',
        accent: 'text-electric',
        points: [
            '100% gold-file recall on the public benchmark (requests, click).',
            'Team dashboard shows synapse memory health, ingestion status, savings, latency trends — all read-only, all local.',
            'Self-documenting code: DocEvolver finds undocumented methods and evolves JSDoc that actually improves retrieval.',
            '100% local with zero code egress — verifiable on the wire. Works with the agents you already run: Claude Code, Cursor, Cline, any MCP agent. No rip-and-replace.',
        ],
    },
];

export default function BusinessCase() {
    return (
        <section id="business-case" className="relative py-16 md:py-32 px-4 md:px-6">
            <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[700px] h-[500px] bg-proton/3 rounded-full blur-[200px] -z-10" />

            <div className="max-w-5xl mx-auto">
                <div className="text-center mb-12 md:mb-16">
                    <span className="text-proton text-sm font-semibold tracking-wider uppercase mb-3 block">
                        The business case
                    </span>
                    <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
                        The savings are free. The tier is control.
                    </h2>
                    <p className="text-slate-400 text-base sm:text-lg md:text-xl max-w-2xl mx-auto">
                        Dollar figures below are modeled, with published assumptions — the free
                        assessment runs the same model in your numbers.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6 mb-10">
                    {cards.map((card) => (
                        <div key={card.audience} className="glow-card rounded-2xl p-6 md:p-8">
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
