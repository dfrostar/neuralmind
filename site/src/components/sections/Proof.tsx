import SectionHeader from '@/components/ui/SectionHeader';

// What exists, as evidence. Each item says what strength of claim it is.
const evidence = [
    {
        title: 'Reproducible public benchmark',
        kind: 'Reproducible',
        desc: '40 pre-registered queries on 4 pinned OSS repos: 95% mean gold-file recall at 46–263× fewer tokens than pasting every source file. One command reruns it — python -m evals.public.run — and the raw per-query data is committed.',
        link: '/benchmark/',
        linkText: 'See the benchmark →',
    },
    {
        title: 'CI-gated regression floors',
        kind: 'CI-gated',
        desc: 'Every PR asserts: token reduction ≥ 4.0× on the fixture, synapse recall never lowers hit rate, and the faithfulness delta against naive truncation stays above −0.10 — it currently measures −0.054, a loss we publish rather than hide.',
        link: 'https://github.com/dfrostar/neuralmind/blob/main/.github/workflows/ci-benchmark.yml',
        linkText: 'CI config on GitHub →',
    },
    {
        title: 'Production field report',
        kind: 'Field report',
        desc: '48.8× token reduction on a ~9,300-node TypeScript SaaS codebase through a major rebuild. One repo, maintainer-measured, anonymized by request — method and before/after data published.',
        link: '/field-reports/measure-memory-across-a-refactor/',
        linkText: 'Read the field report →',
    },
];

// What does not exist yet. Stated plainly rather than implied away.
const gaps = [
    'Testimonials from users outside the project',
    'Named case studies — the one field report is anonymized',
    'A side-by-side video of a real repo, before and after',
    'Adoption numbers large enough to be meaningful',
];

export default function Proof() {
    return (
        <section id="proof" className="relative py-16 md:py-32 px-4 md:px-6">
            <div className="max-w-6xl mx-auto">
                <SectionHeader eyebrow="Honest about proof" title="What we can prove, and what we can&apos;t yet">
                    Reproducibility is not social proof — anyone can benchmark fixture data. So here is
                    the evidence that exists, labelled by strength, and the evidence that doesn&apos;t.
                </SectionHeader>

                <div className="grid md:grid-cols-3 gap-4">
                    {evidence.map((item) => (
                        <div key={item.title} className="rounded-card border border-carbon-border bg-carbon-card p-6 md:p-7 flex flex-col">
                            <span className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-proton mb-3">
                                {item.kind}
                            </span>
                            <h3 className="font-display text-lg font-bold text-white mb-3">{item.title}</h3>
                            <p className="text-slate-400 text-sm leading-relaxed mb-4">{item.desc}</p>
                            <a
                                href={item.link}
                                className="mt-auto text-electric hover:text-electric-bright text-sm font-medium transition-colors"
                            >
                                {item.linkText}
                            </a>
                        </div>
                    ))}
                </div>

                <div className="mt-6 rounded-card border border-carbon-line bg-carbon-raised p-6 md:p-8 grid md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] gap-6 md:gap-10">
                    <div>
                        <h3 className="font-display text-lg font-semibold tracking-tight text-white mb-3">
                            What we don&apos;t have yet
                        </h3>
                        <ul className="space-y-2">
                            {gaps.map((gap) => (
                                <li key={gap} className="flex items-start gap-2.5 text-sm text-slate-400">
                                    <span className="mt-2 w-1.5 h-1.5 rounded-full bg-slate-500 shrink-0" aria-hidden="true" />
                                    {gap}
                                </li>
                            ))}
                        </ul>
                    </div>
                    <div className="space-y-3 text-slate-400 text-sm leading-relaxed">
                        <p>
                            The biggest missing piece is{' '}
                            <span className="text-white font-medium">social proof from real users</span>,
                            not another benchmark. So the honest way to evaluate NeuralMind is to{' '}
                            <code className="font-mono text-[0.9em] text-slate-300">pip install neuralmind</code>,{' '}
                            <code className="font-mono text-[0.9em] text-slate-300">neuralmind build .</code>,{' '}
                            <code className="font-mono text-[0.9em] text-slate-300">neuralmind benchmark .</code> — and
                            read your own number.
                        </p>
                        <p>
                            If you do, send it to{' '}
                            <a href="mailto:hello@neuralmind.uk" className="text-electric hover:text-electric-bright">
                                hello@neuralmind.uk
                            </a>
                            . We publish results attributed or anonymized — your choice — including the ones
                            that don&apos;t flatter us.{' '}
                            <a href="/measure-your-own/" className="text-electric hover:text-electric-bright">
                                How to measure your own →
                            </a>
                        </p>
                    </div>
                </div>
            </div>
        </section>
    );
}
