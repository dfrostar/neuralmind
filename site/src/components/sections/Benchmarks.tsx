'use client';

import SectionHeader from '@/components/ui/SectionHeader';

// Sourced in site/claims.json; gated by tests/test_site_claims.py. Each row
// says which kind of evidence it is — a CI gate, an on-demand reproduction, or
// a single-repo field report — because they are not the same strength of claim.
const dataPoints = [
    { metric: 'Gold-file recall', value: '93.75%', detail: '40 pre-registered queries, 4 pinned OSS repos (79–100% per repo)' },
    { metric: 'Tokens vs. pasting files', value: '45–257×', detail: 'same 40 queries; cheaper than ripgrep on every repo' },
    { metric: 'Learned recall', value: 'Never worse', detail: 'CI asserts synapse recall ≥ no-recall on the same warm graph, at a neutral token budget. On AVX-512 hosts it currently measures -1.75 pts and the gate fails: an open bug, not an allowance.' },
    { metric: 'vs. naive truncation', value: 'Never worse', detail: 'CI asserts our selection beats truncation at an equal budget. Both magnitudes vary by repo — run them for yours' },
    { metric: 'Field report, one repo', value: '48.8×', detail: '~9,300-node private TypeScript codebase — method reproducible, not CI-gated' },
    { metric: 'Setup time', value: '~15 min', detail: 'one CLI command; post-commit hook keeps it current' },
];

export default function Benchmarks() {
    return (
        <section id="benchmarks" className="relative py-20 md:py-28 px-4 md:px-6">
            <div className="max-w-6xl mx-auto">
                <SectionHeader eyebrow="Measured, not marketed" title="Benchmarks">
                    Two of these are recomputed by CI on every commit; the rest reproduce from a
                    fresh clone with one command. Where a number comes from a single repo, it says so.
                    Run <code className="font-mono text-[0.9em] text-electric-bright bg-electric/[0.07] rounded px-1 py-0.5">neuralmind benchmark .</code> for your own.
                </SectionHeader>

                {/* Same ruled matrix as the hero stats and the feature grid, so a
                    figure looks the same wherever it appears on the page. */}
                <dl className="grid sm:grid-cols-2 lg:grid-cols-3 border-t border-l border-carbon-border rounded-sm overflow-hidden">
                    {dataPoints.map((dp) => (
                        <div key={dp.metric} className="border-b border-r border-carbon-border p-6">
                            <dt className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-faint mb-3">
                                {dp.metric}
                            </dt>
                            <dd>
                                <p className={`text-white mb-2 leading-none ${
                                    /^[~\d]/.test(dp.value)
                                        ? 'metric text-[1.75rem]'
                                        : 'font-display text-2xl font-semibold tracking-tight'
                                }`}>
                                    {dp.value}
                                </p>
                                <p className="text-slate-400 text-sm leading-relaxed">{dp.detail}</p>
                            </dd>
                        </div>
                    ))}
                </dl>

                {/* Field report — hand-measured, deliberately outside the CI-gated tiles above */}
                <p className="mt-6 text-slate-400 text-sm max-w-3xl">
                    Plus one labeled <span className="text-slate-300">field report</span> (measured with the CLI, not CI-gated):{' '}
                    <span className="text-white font-semibold">48.8×</span> on a real ~9,300-node TypeScript SaaS
                    platform, through a major rebuild.{' '}
                    <a href="/field-reports/measure-memory-across-a-refactor/" className="text-electric hover:text-electric-bright transition-colors">
                        Read the field report →
                    </a>
                </p>

                {/* Demo callout */}
                <div className="mt-12 p-6 md:p-7 rounded-xl panel-accent flex flex-col md:flex-row md:items-center justify-between gap-5">
                    <div className="max-w-2xl">
                        <h3 className="font-display text-lg font-semibold tracking-tight text-white mb-1.5">See it in 30 seconds</h3>
                        <p className="text-slate-400 text-sm leading-relaxed">
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
