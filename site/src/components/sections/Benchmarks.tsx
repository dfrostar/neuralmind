'use client';

// Sourced in site/claims.json; gated by tests/test_site_claims.py. Each row
// says which kind of evidence it is — a CI gate, an on-demand reproduction, or
// a single-repo field report — because they are not the same strength of claim.
const dataPoints = [
    { metric: 'Gold-file recall', value: '93.75%', detail: '40 pre-registered queries, 4 pinned OSS repos (79–100% per repo)' },
    { metric: 'Tokens vs. pasting files', value: '45–257×', detail: 'same 40 queries; cheaper than ripgrep on every repo' },
    { metric: 'Learned recall', value: 'Never worse', detail: 'CI asserts synapse recall ≥ no-recall on the same warm graph, at a neutral token budget' },
    { metric: 'vs. naive truncation', value: 'Never worse', detail: 'CI asserts our selection beats truncation at an equal budget. Both magnitudes vary by repo — run them for yours' },
    { metric: 'Field report, one repo', value: '48.8×', detail: '~9,300-node private TypeScript codebase — method reproducible, not CI-gated' },
    { metric: 'Setup time', value: '~15 min', detail: 'one CLI command; post-commit hook keeps it current' },
];

export default function Benchmarks() {
    return (
        <section id="benchmarks" className="relative py-16 md:py-32 px-4 md:px-6">
            <div className="absolute top-1/3 right-0 w-[500px] h-[500px] bg-proton/3 rounded-full blur-[200px] -z-10" />

            <div className="max-w-5xl mx-auto">
                <div className="text-center mb-12 md:mb-16">
                    <span className="text-proton text-sm font-semibold tracking-wider uppercase mb-3 block">
                        Measured, not marketed
                    </span>
                    <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
                        Benchmarks
                    </h2>
                    <p className="text-slate-400 text-base sm:text-lg md:text-xl max-w-xl mx-auto">
                        Two of these are recomputed by CI on every commit; the rest reproduce from a
                        fresh clone with one command. Where a number comes from a single repo, it says so.
                        Run <code className="text-electric font-mono text-sm">neuralmind benchmark .</code> for your own.
                    </p>
                </div>

                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {dataPoints.map((dp) => (
                        <div
                            key={dp.metric}
                            className="glow-card rounded-2xl p-6"
                        >
                            <p className="text-slate-500 text-xs font-semibold uppercase tracking-wider mb-2">
                                {dp.metric}
                            </p>
                            <p className="font-display text-3xl font-bold text-white mb-1">{dp.value}</p>
                            <p className="text-slate-400 text-sm">{dp.detail}</p>
                        </div>
                    ))}
                </div>

                {/* Field report — hand-measured, deliberately outside the CI-gated tiles above */}
                <p className="mt-8 text-center text-slate-400 text-sm">
                    Plus one labeled <span className="text-slate-300">field report</span> (measured with the CLI, not CI-gated):{' '}
                    <span className="text-white font-semibold">48.8×</span> on a real ~9,300-node TypeScript SaaS
                    platform, through a major rebuild.{' '}
                    <a href="/field-reports/measure-memory-across-a-refactor/" className="text-electric hover:text-electric-bright transition-colors">
                        Read the field report →
                    </a>
                </p>

                {/* Demo callout */}
                <div className="mt-12 p-6 rounded-2xl border border-carbon-border bg-carbon-raised/50 flex flex-col md:flex-row items-center justify-between gap-4">
                    <div>
                        <h3 className="font-display text-xl font-bold text-white mb-1">See it in 30 seconds</h3>
                        <p className="text-slate-400 text-sm">
                            Clone the repo, run the demo, get numbers on YOUR codebase. Then email the
                            output to hello@neuralmind.uk with your team size for a free full spend model.
                        </p>
                    </div>
                    <a
                        href="https://github.com/dfrostar/neuralmind#-30-second-proof--see-the-memory-work"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn-primary text-sm whitespace-nowrap"
                    >
                        Run the demo
                    </a>
                </div>
            </div>
        </section>
    );
}
