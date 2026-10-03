import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import type { Metadata } from 'next';
import { pageMetadata } from '@/lib/seo';

export const metadata: Metadata = pageMetadata({
    path: '/effectiveness',
    title: 'NeuralMind Results: Before & After on a Production Repo',
    description:
        'Field report: 48.8× fewer tokens per question on a ~9,300-node TypeScript codebase, synapse edges 36 → 135 across a rebuild — and what we can’t claim yet.',
});

const headlineStats = [
    { label: 'Token Reduction', value: '48.8×', detail: '1,033 tokens/query vs the fixed 50K-token estimate the CLI used before v4.5.0', gradient: true },
    { label: 'Wake-up Tokens', value: '455', detail: 'Per query, measured', gradient: false },
    { label: 'Personal Edges', value: '+275%', detail: '36 → 135 co-activations', gradient: false },
    { label: 'Communities', value: '810', detail: 'Architectural boundaries', gradient: false },
];

const beforeAfter = [
    { metric: 'Total nodes', before: '9,190', after: '9,293', change: '+103' },
    { metric: 'Communities', before: '—', after: '810', change: 'new' },
    { metric: 'Personal edges', before: '36', after: '135', change: '+275%' },
    { metric: 'Shared edges', before: '10,079', after: '10,183', change: '+104' },
    { metric: 'Shared edge weight', before: '2,774.73', after: '2,924.66', change: '+5.4%' },
    { metric: 'Wake-up tokens', before: '—', after: '455', change: '—' },
    { metric: 'Avg query tokens', before: '—', after: '1,033', change: '—' },
    { metric: 'Avg token reduction', before: '—', after: '48.8×', change: '—' },
];

const honestyGate = [
    {
        title: 'Self-improving',
        body: 'No production fitness data. Architecture is complete but gains are unmeasured.',
    },
    {
        title: 'Team memory that learns',
        body: 'No co-view signal yet. Structural seeds exist, but synaptic learning needs weeks of sessions.',
    },
    {
        // claims-guard:allow — this entry exists to disown the phrase, not to make it.
        title: 'Zero code egress',
        body: 'Overclaim. The agent layer still talks to its model. What NeuralMind itself does: transmits no repository content, and sends no telemetry.',
    },
];

export default function EffectivenessPage() {
    return (
        <>
            <Navbar />
            <main>
                <section className="relative pt-32 pb-16 md:py-40 px-4 md:px-6 overflow-hidden">
                    <div className="max-w-4xl mx-auto text-center">
                        <span className="text-electric text-sm font-semibold tracking-wider uppercase mb-3 block">
                            Field report · one repo · not CI-gated
                        </span>
                        <h1 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-white leading-[1.05] mb-6">
                            Before and after on a production codebase
                        </h1>
                        <p className="text-base sm:text-lg md:text-xl text-slate-400 max-w-2xl mx-auto mb-4 leading-relaxed">
                            A private CRM platform (TypeScript/React/Node), measured before and after a major
                            rebuild. Every number traces to a CLI command such as{' '}
                            <code className="font-mono text-electric text-sm">neuralmind benchmark .</code>
                        </p>
                        <p className="text-sm text-faint max-w-2xl mx-auto mb-8 leading-relaxed">
                            One repo, measured by the maintainer — reproducible in method, not in number.
                            For results anyone can rerun, see{' '}
                            <a href="/benchmark/" className="text-electric hover:text-electric-bright">the public benchmark</a>;
                            for the full write-up, the{' '}
                            <a href="/field-reports/measure-memory-across-a-refactor/" className="text-electric hover:text-electric-bright">field report</a>.
                        </p>
                    </div>
                </section>

                <section className="relative py-16 md:py-32 px-4 md:px-6">
                    <div className="max-w-5xl mx-auto">
                        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                            {headlineStats.map((s) => (
                                <div key={s.label} className="card rounded-2xl p-6">
                                    <p className="text-faint text-xs font-semibold uppercase tracking-wider mb-2">{s.label}</p>
                                    <p className={`font-display text-3xl font-bold mb-1 ${s.gradient ? 'gradient-text' : 'text-white'}`}>{s.value}</p>
                                    <p className="text-slate-400 text-sm">{s.detail}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                <section className="relative py-16 md:py-32 px-4 md:px-6">
                    <div className="max-w-5xl mx-auto">
                        <div className="text-center mb-12 md:mb-16">
                            <span className="text-electric text-sm font-semibold tracking-wider uppercase mb-3 block">Before / After</span>
                            <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">Phase 3 vs Phase 4</h2>
                            <p className="text-slate-400 text-base sm:text-lg md:text-xl max-w-xl mx-auto">
                                Full rebuild on a real production CRM codebase
                            </p>
                        </div>
                        <div className="card rounded-2xl p-6 md:p-8 overflow-hidden">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-carbon-border">
                                        <th className="text-left py-3 px-4 text-slate-400 font-medium">Metric</th>
                                        <th className="text-right py-3 px-4 text-slate-400 font-medium">Before</th>
                                        <th className="text-right py-3 px-4 text-slate-400 font-medium">After</th>
                                        <th className="text-right py-3 px-4 text-slate-400 font-medium">Change</th>
                                    </tr>
                                </thead>
                                <tbody className="text-slate-300">
                                    {beforeAfter.map((row, i) => (
                                        <tr key={row.metric} className={i < beforeAfter.length - 1 ? 'border-b border-carbon-border/50' : ''}>
                                            <td className="py-3 px-4">{row.metric}</td>
                                            <td className="py-3 px-4 text-right font-mono text-faint">{row.before}</td>
                                            <td className="py-3 px-4 text-right font-mono">{row.after}</td>
                                            <td className="py-3 px-4 text-right font-mono text-electric-bright">{row.change}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </section>

                <section className="relative py-16 md:py-32 px-4 md:px-6">
                    <div className="max-w-5xl mx-auto">
                        <div className="text-center mb-12 md:mb-16">
                            <span className="text-proton text-sm font-semibold tracking-wider uppercase mb-3 block">Build Performance</span>
                            <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
                                5.4 min full rebuild, then ~30s increments
                            </h2>
                        </div>
                        <div className="grid md:grid-cols-2 gap-4">
                            <div className="card rounded-2xl p-6">
                                <p className="text-faint text-xs font-semibold uppercase tracking-wider mb-2">Full Rebuild</p>
                                <p className="font-display text-3xl font-bold text-white mb-1">326s</p>
                                <p className="text-slate-400 text-sm">All nodes, edges, embeddings</p>
                            </div>
                            <div className="card rounded-2xl p-6">
                                <p className="text-faint text-xs font-semibold uppercase tracking-wider mb-2">Incremental (after)</p>
                                <p className="font-display text-3xl font-bold text-white mb-1">~30s</p>
                                <p className="text-slate-400 text-sm">Changed files + dependents only</p>
                            </div>
                        </div>
                    </div>
                </section>

                <section className="relative py-16 md:py-32 px-4 md:px-6">
                    <div className="max-w-3xl mx-auto">
                        <div className="text-center mb-12 md:mb-16">
                            <span className="text-proton text-sm font-semibold tracking-wider uppercase mb-3 block">Honesty Gate</span>
                            <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
                                What we cannot claim yet
                            </h2>
                        </div>
                        <div className="space-y-3">
                            {honestyGate.map((item) => (
                                <div key={item.title} className="card rounded-2xl p-6">
                                    <h3 className="font-display text-xl font-bold text-white mb-2">{item.title}</h3>
                                    <p className="text-slate-400 text-sm">{item.body}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                <section className="relative py-16 md:py-32 px-4 md:px-6">
                    <div className="max-w-5xl mx-auto">
                        <div className="card rounded-2xl p-6 md:p-8 flex flex-col md:flex-row items-center justify-between gap-6">
                            <div>
                                <h3 className="font-display text-2xl font-bold text-white mb-2">Measure your own</h3>
                                <p className="text-slate-400 text-sm">
                                    Run <code className="font-mono text-electric">neuralmind benchmark .</code> on your
                                    own codebase — about fifteen minutes, on your machine, with no account. Then
                                    email the output to{' '}
                                    <a href="mailto:hello@neuralmind.uk" className="text-electric hover:text-electric-bright">hello@neuralmind.uk</a>{' '}
                                    with your team size for a free full spend model.
                                </p>
                            </div>
                            <a
                                href="/measure-your-own/"
                                className="btn-primary text-sm whitespace-nowrap"
                            >
                                How to measure it
                            </a>
                        </div>
                    </div>
                </section>
            </main>
            <Footer />
        </>
    );
}
