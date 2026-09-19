import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import { pageMetadata } from '@/lib/seo';
import type { Metadata } from 'next';

export const metadata: Metadata = pageMetadata({
    path: '/measure-your-own',
    title: 'Measure Your Own — NeuralMind',
    description:
        'Run the NeuralMind benchmark on your own codebase. One command, ~15 minutes, real numbers. No account, no signup, no cloud. Share your results and we will publish them.',
    keywords: [
        'AI coding agent benchmark',
        'token reduction measurement',
        'codebase context benchmark',
        'NeuralMind benchmark your repo',
        'AI agent memory measurement',
        'token cost reduction tool',
        'code intelligence benchmark',
        'context compression measurement',
    ],
    ogTitle: 'Measure Your Own — NeuralMind',
    ogDescription:
        'Run the NeuralMind benchmark on your own codebase. One command, ~15 minutes, real numbers. Share your results.',
});

const steps = [
    {
        step: '1',
        title: 'Clone and install',
        body: 'Get the source checkout. NeuralMind ships the benchmark harness in the repo, not the PyPI wheel, so you need a clone.',
        code: ['git clone https://github.com/dfrostar/neuralmind && cd neuralmind', 'pip install -e . tiktoken'],
    },
    {
        step: '2',
        title: 'Build your index',
        body: 'One command indexes your codebase. Tree-sitter parses the structure, TurboVec compresses embeddings 4-bit. Processing runs on your machine.',
        code: ['neuralmind build .'],
    },
    {
        step: '3',
        title: 'Run the benchmark',
        body: 'Compares NeuralMind against full-file context and ripgrep on your own queries. Reports gold-file recall and token cost together.',
        code: ['neuralmind benchmark .', '# or for JSON output:', 'neuralmind benchmark . --json'],
    },
    {
        step: '4',
        title: 'Read your number',
        body: 'The output shows: naive tokens, NeuralMind tokens, reduction ratio, and per-query recall. No cherry-picking — every query is reported.',
        code: null,
    },
    {
        step: '5',
        title: 'Share your results',
        body: 'Email hello@neuralmind.uk with your output. We will publish your results (attributed or anonymized, your choice). Help us build the social proof we do not have yet.',
        code: null,
    },
];

const whatYouGet = [
    {
        metric: 'Tokens/query',
        desc: 'Mean context size in tokens (tiktoken o200k_base). Compare NeuralMind vs naive full-file vs ripgrep.',
    },
    {
        metric: 'Reduction',
        desc: 'How many fewer tokens NeuralMind sends vs the naive baseline. 12-50× is the published real-repo range.',
    },
    {
        metric: 'Gold-file recall',
        desc: 'For each query: did the objectively-correct file land in the assembled context? Objective, no LLM judge.',
    },
    {
        metric: 'MRR',
        desc: 'Mean reciprocal rank of the gold file. 1.0 = always first; 0.5 = always second.',
    },
];

export default function MeasureYourOwnPage() {
    return (
        <>
            <Navbar />
            <main className="max-w-4xl mx-auto px-4 md:px-6 py-16">
                <script
                    type="application/ld+json"
                    dangerouslySetInnerHTML={{
                        __html: JSON.stringify({
                            '@context': 'https://schema.org',
                            '@type': 'HowTo',
                            name: 'Measure NeuralMind token reduction on your own codebase',
                            description:
                                'Step-by-step guide to running the NeuralMind benchmark on your own codebase. Measures token reduction, gold-file recall, and MRR against naive and ripgrep baselines.',
                            step: steps.map((s) => ({
                                '@type': 'HowToStep',
                                position: parseInt(s.step),
                                name: s.title,
                                text: s.body,
                            })),
                            tool: [{ '@type': 'HowToTool', name: 'neuralmind CLI' }],
                            totalTime: 'PT15M',
                        }),
                    }}
                />

                <header className="mb-12 pb-8 border-b border-carbon-border">
                    <div className="flex items-center gap-3 mb-4">
                        <span className="px-3 py-1 rounded-lg bg-proton/10 text-proton text-xs font-mono">
                            ~15 minutes
                        </span>
                        <span className="text-faint text-sm">No account · no cloud · no telemetry</span>
                    </div>
                    <h1 className="font-display text-3xl md:text-[2.75rem] font-bold text-white mb-5 leading-[1.08] tracking-tighter">
                        Measure your own
                    </h1>
                    <p className="text-lg text-slate-300 leading-relaxed mb-6">
                        The number that decides anything for you is the one from your
                        codebase. Here is how to get it — and why we want you to share it.
                    </p>
                    <p className="text-slate-400 leading-relaxed">
                        We do not have testimonials yet. We do not have a video demonstrating a before/after on a real user&rsquo;s
                        codebase. What we have is a reproducible benchmark that runs locally, on your machine, against your code, in about
                        fifteen minutes. Run it. Read your own number. If it is good,
                        <a href="mailto:hello@neuralmind.uk" className="text-electric hover:text-electric-bright transition-colors">
                            {' '}tell us — we will publish it
                        </a>
                        .
                    </p>
                </header>

                <section className="mb-14">
                    <h2 className="font-display text-xl font-bold text-white mb-2">The honest pitch</h2>
                    <div className="rounded-card border border-carbon-line bg-carbon-raised p-6 md:p-7 mb-6">
                        <p className="text-slate-400 text-sm leading-relaxed mb-4">
                            Anyone can run a benchmark on fixture data. That is why the public benchmark exists — because you should not
                            take any vendor&rsquo;s word for it. But a benchmark on your own repository, with your own queries, on your
                            own machine — that is the only number that actually tells you whether NeuralMind will help your workflow.
                        </p>
                        <p className="text-slate-400 text-sm leading-relaxed mb-4">
                            If you run it and the number is good, we want to publish it. Attributed or anonymized — your choice. We are
                            building the social proof we currently lack.
                        </p>
                        <p className="text-slate-400 text-sm leading-relaxed">
                            If you run it and the number is <em>not</em> good, we want to know that too. Email us the output and we will
                            tell you why, or fix it. That is the honest deal.
                        </p>
                    </div>
                </section>

                <section className="mb-14">
                    <h2 className="font-display text-xl font-bold text-white mb-6">Step by step</h2>
                    <div className="grid md:grid-cols-2 gap-4">
                        {steps.map((s) => (
                            <div key={s.step} className="card rounded-2xl p-6 flex flex-col min-w-0">
                                <div className="flex items-center gap-3 mb-3">
                                    <span className="w-7 h-7 rounded-md border border-carbon-line bg-carbon-raised flex items-center justify-center font-mono text-xs text-electric tabular-nums">
                                        {s.step}
                                    </span>
                                    <h3 className="font-display text-lg font-bold text-white">{s.title}</h3>
                                </div>
                                <p className="text-slate-400 text-sm mb-4">{s.body}</p>
                                {s.code ? (
                                    <div className="bg-carbon rounded-lg p-4 font-mono text-xs text-slate-300 overflow-x-auto mt-auto">
                                        {s.code.map((line) => (
                                            <p key={line} className="whitespace-nowrap">
                                                <span className="text-faint select-none">{line.startsWith('#') ? '' : '$ '}</span>
                                                {line}
                                            </p>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="mt-auto">
                                        {s.step === '4' && (
                                            <div className="bg-carbon rounded-lg p-4 font-mono text-xs text-slate-400 overflow-x-auto">
                                                <p className="whitespace-pre text-faint">{'# Example output:'}</p>
                                                <p className="whitespace-pre">{'  Naive:     41,729 tokens/query'}</p>
                                                <p className="whitespace-pre">{'  NeuralMind:    913 tokens/query'}</p>
                                                <p className="whitespace-pre">{'  Reduction:   45.7× fewer'}</p>
                                                <p className="whitespace-pre mt-2 text-faint">{'# This is the requests repo. Your number will differ.'}</p>
                                            </div>
                                        )}
                                        {s.step === '5' && (
                                            <a
                                                href="mailto:hello@neuralmind.uk"
                                                className="text-electric hover:text-electric-bright text-sm font-medium transition-colors"
                                            >
                                                Email your output →
                                            </a>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </section>

                <section className="mb-14">
                    <h2 className="font-display text-xl font-bold text-white mb-6">What you get</h2>
                    <dl className="grid sm:grid-cols-2 gap-4">
                        {whatYouGet.map((item) => (
                            <div key={item.metric} className="border-b border-r border-carbon-border p-6">
                                <dt className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-faint mb-3">
                                    {item.metric}
                                </dt>
                                <dd>
                                    <p className="text-white mb-2 leading-none font-display text-lg font-semibold tracking-tight">
                                        {item.metric}
                                    </p>
                                    <p className="text-slate-400 text-sm leading-relaxed">{item.desc}</p>
                                </dd>
                            </div>
                        ))}
                    </dl>
                </section>

                <section className="rounded-card panel-accent p-6 md:p-7">
                    <h2 className="font-display text-lg font-semibold tracking-tight text-white mb-2">
                        Already run it?
                    </h2>
                    <p className="text-slate-400 text-sm leading-relaxed mb-4">
                        Paste your output to hello@neuralmind.uk. We will publish it on this page (attributed or anonymized, your
                        choice). The only requirement: the output must be from your own codebase, under your own run. We are building
                        social proof the honest way — one real number at a time.
                    </p>
                    <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
                        <a
                            href="mailto:hello@neuralmind.uk"
                            className="text-electric hover:text-electric-bright transition-colors"
                        >
                            Share your results →
                        </a>
                        <a
                            href="/benchmark/"
                            className="text-electric hover:text-electric-bright transition-colors"
                        >
                            See the public benchmark →
                        </a>
                    </div>
                </section>
            </main>
            <Footer />
        </>
    );
}
