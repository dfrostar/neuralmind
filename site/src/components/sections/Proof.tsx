import SectionHeader from '@/components/ui/SectionHeader';

const proofItems = [
    {
        title: 'Reproducible benchmark',
        status: 'have',
        desc: '40 pre-registered queries on 4 pinned OSS repos. Gold-file recall 93.6%, token reduction 46-259×. One command reruns it: python -m evals.public.run. Raw data committed in bench/public/results.json.',
        link: '/benchmark/',
        linkText: 'See the benchmark →',
    },
    {
        title: 'CI-gated regression floors',
        status: 'have',
        desc: 'Every PR asserts: token reduction ≥ 4.0×, faithfulness delta ≥ 0.0, synapse recall never lowers hit rate. Cannot silently regress. Floors are deliberately conservative — they absorb HNSW jitter on the tiny fixture.',
        link: 'https://github.com/dfrostar/neuralmind/blob/main/.github/workflows/ci-benchmark.yml',
        linkText: 'CI config on GitHub →',
    },
    {
        title: 'Production field report',
        status: 'have',
        desc: '48.8× token reduction on a ~9,300-node TypeScript SaaS codebase. Anonymized by request. Method, measurement, and before/after data published.',
        link: '/field-reports/measure-memory-across-a-refactor/',
        linkText: 'Read the field report →',
    },
    {
        title: 'User testimonials',
        status: 'missing',
        desc: 'None yet. If you use NeuralMind and want to share your numbers, email hello@neuralmind.uk — we will publish your results with attribution (or anonymized, your choice).',
        link: 'mailto:hello@neuralmind.uk',
        linkText: 'Share your results →',
    },
    {
        title: 'Side-by-side video demo',
        status: 'missing',
        desc: 'No video showing naive context dump vs NeuralMind on a real repo. Recording one is on the roadmap. The closest alternative: run the 30-second demo yourself.',
        link: 'https://github.com/dfrostar/neuralmind#-30-second-proof--see-the-memory-work',
        linkText: 'Run the 30-second demo →',
    },
    {
        title: 'Before/after screenshots',
        status: 'missing',
        desc: 'We have printed terminal output from the demo fixture, but no visual screenshot showing a real codebase context window before and after. This would make the value immediately obvious.',
        link: 'https://github.com/dfrostar/neuralmind/issues',
        linkText: 'Want to contribute? →',
    },
    {
        title: 'Named case studies',
        status: 'missing',
        desc: 'The one production field report is anonymized. If your team uses NeuralMind and is willing to be named, we will publish a full case study with your codebase size, token numbers, and workflow.',
        link: 'mailto:hello@neuralmind.uk',
        linkText: 'Become a case study →',
    },
    {
        title: 'User count / stars as social proof',
        status: 'partial',
        desc: 'GitHub stars exist but are not prominently displayed. No "X teams use this" claim because that number is not yet large enough to be meaningful. Honest alternative: publish your own benchmark result below.',
        link: '/measure-your-own/',
        linkText: 'Measure your own repo →',
    },
];

export default function Proof() {
    return (
        <section id="proof" className="relative py-16 md:py-32 px-4 md:px-6">
            <div className="max-w-6xl mx-auto">
                <SectionHeader eyebrow="Honest about proof" title="What we can prove, and what we can&apos;t">
                    Every claim on this site reproduces. But reproducibility isn&apos;t social proof — anyone can run
                    a benchmark on fixture data. Here is exactly what we have evidence for, and what we don&apos;t.
                </SectionHeader>

                <div className="grid md:grid-cols-2 gap-4">
                    {proofItems.map((item) => (
                        <div
                            key={item.title}
                            className={`rounded-card border p-6 md:p-7 ${
                                item.status === 'have'
                                    ? 'border-carbon-border bg-carbon-card'
                                    : item.status === 'partial'
                                    ? 'border-carbon-border bg-carbon-card'
                                    : 'border-carbon-line bg-carbon-raised'
                            }`}
                        >
                            <div className="flex items-center gap-3 mb-3">
                                <span
                                    className={`w-2.5 h-2.5 rounded-full ${
                                        item.status === 'have'
                                            ? 'bg-proton'
                                            : item.status === 'partial'
                                            ? 'bg-yellow-500'
                                            : 'bg-red-400'
                                    }`}
                                    aria-hidden="true"
                                />
                                <h3 className="font-display text-lg font-bold text-white">{item.title}</h3>
                            </div>
                            <p className="text-slate-400 text-sm leading-relaxed mb-4">{item.desc}</p>
                            {item.link && (
                                <a
                                    href={item.link}
                                    className="text-electric hover:text-electric-bright text-sm font-medium transition-colors"
                                >
                                    {item.linkText}
                                </a>
                            )}
                        </div>
                    ))}
                </div>

                {/* Brutal honesty box */}
                <div className="mt-12 rounded-card border border-carbon-line bg-carbon-raised p-6 md:p-8">
                    <h3 className="font-display text-lg font-semibold tracking-tight text-white mb-3">
                        The honest summary
                    </h3>
                    <div className="space-y-3 text-slate-400 text-sm leading-relaxed">
                        <p>
                            NeuralMind works. The benchmark proves it reproducibly on 4 repos with 40 queries. The
                            field report proves it on a real production codebase at 48.8×. CI gates prove it doesn&apos;t
                            regress.
                        </p>
                        <p>
                            But we don&apos;t have testimonials. We don&apos;t have a video. We don&apos;t have named case
                            studies. The biggest missing piece is <span className="text-white font-medium">social proof from real users</span> —
                            not benchmark numbers.
                        </p>
                        <p>
                            If you&apos;re evaluating NeuralMind, the honest path is:{' '}
                            <code className="font-mono text-[0.9em] text-slate-300">git clone</code>,{' '}
                            <code className="font-mono text-[0.9em] text-slate-300">neuralmind build .</code>,{' '}
                            <code className="font-mono text-[0.9em] text-slate-300">neuralmind benchmark .</code> —
                            and read your own number. That&apos;s the proof that actually matters.
                        </p>
                    </div>
                </div>
            </div>
        </section>
    );
}
