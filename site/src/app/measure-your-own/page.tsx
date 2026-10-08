import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import { pageMetadata } from '@/lib/seo';
import type { Metadata } from 'next';

export const metadata: Metadata = pageMetadata({
    path: '/measure-your-own',
    title: 'Measure AI Agent Token Usage on Your Own Repo — NeuralMind',
    description:
        'Measure NeuralMind on your codebase: tokens per question, token reduction and retrieval recall on your own symbols. Three commands, about 15 minutes, no account.',
    keywords: [
        'measure Claude Code token usage',
        'AI coding agent benchmark',
        'token reduction measurement',
        'codebase context benchmark',
        'retrieval recall on your repo',
        'NeuralMind benchmark your repo',
        'context compression measurement',
    ],
    ogTitle: 'Measure NeuralMind on your own repo',
    ogDescription:
        'Three commands, about 15 minutes, on your machine: tokens per question, reduction, and recall on your own symbols. Share the output and we will publish it.',
});

// Every command is real and every sample output below is verbatim CLI output
// on psf/requests v2.32.3 (benchmark: NeuralMind v4.5.0; probe: v4.3.4). This page used to describe
// `neuralmind benchmark .` as comparing against ripgrep and reporting per-query
// recall, and showed an output format the CLI has never printed. It reports
// token reduction; recall on your own code comes from `neuralmind probe .`.
type Step = { step: string; title: string; body: string; code: string[]; output?: string[] };

const steps: Step[] = [
    {
        step: '1',
        title: 'Install',
        body: 'Measuring your own repo needs only the PyPI package — no clone. (A source checkout is needed only to rerun the public four-repo benchmark.)',
        code: ['pip install neuralmind'],
    },
    {
        step: '2',
        title: 'Build your index',
        body: 'tree-sitter parses the structure and embeddings are computed on your machine. The first build downloads a public embedding model once; after that nothing else is fetched.',
        code: ['cd /path/to/your-repo', 'neuralmind build .'],
    },
    {
        step: '3',
        title: 'Measure token reduction',
        body: 'Runs five generic code questions (or the ones in your .neuralmind.eval.yaml) and reports wake-up tokens, average tokens per question, and the reduction: your code — every code file the index covers, measured at the same ~4 characters per token as the context — over the tokens a question costs. It scales with your repo. The legacy line repeats the run against the fixed 50,000-token estimate releases before v4.5.0 used, so older numbers stay comparable.',
        code: ['neuralmind benchmark .', '# machine-readable:', 'neuralmind benchmark . --json'],
        output: [
            'Project: requests',
            'Baseline: measured: 94,069 tokens in 36 indexed code files',
            'Questions: generic',
            'Wake-up tokens: 510',
            'Avg query tokens: 1200.6',
            'Avg reduction: 78.6x',
            'Legacy reduction: 41.8x (vs the fixed 50K-token estimate used before v4.5.0)',
            'Summary: 78.6x average token reduction vs measured: 94,069 tokens in 36 indexed code files',
        ],
    },
    {
        step: '4',
        title: 'Check retrieval on your own code',
        body: 'Samples symbols from your index, asks for each one by its own description, and reports how often the right file comes back — plus the blind spots it could not find, by name. No labels or setup needed.',
        code: ['neuralmind probe .'],
        output: [
            'Sampled 50 of 801 indexed symbols, retrieval depth k=10',
            '  answerability  : 84%  (file found in top-10)',
            '  MRR            : 0.620',
            '  recall@1/3/5   : 0.460 / 0.780 / 0.820',
            '  blind spots    : 8',
        ],
    },
    {
        step: '5',
        title: 'Share your results',
        body: 'Emit a schema-ready submission and send it to us, or open a pull request against the community benchmarks. Nothing is uploaded — you choose what to paste, and whether it is attributed or anonymized.',
        code: ['neuralmind benchmark . --contribute'],
    },
];

const whatYouGet = [
    {
        metric: 'Tokens per question',
        desc: 'The mean context NeuralMind hands your agent for a code question, from benchmark. The hardest number on this page — it does not depend on any baseline.',
    },
    {
        metric: 'Reduction',
        desc: 'Your code over NeuralMind’s context: the measured size of every code file the index covers, divided by the tokens each question costs and averaged — on psf/requests, 94,069 tokens of code at ~1,200 a question, 78.6×. Docs and changelogs are left out, so prose can’t pad it. (The public benchmark’s 45.3× on the same repo is a different measurement — 14 pre-registered questions against non-test source only — so the two don’t compare directly.) Before v4.5.0 the CLI divided a fixed 50K-token estimate instead (41.8× on the same run); the community submissions so far (46× to 65.6×) and the 12–50× field-report range were measured that way.',
    },
    {
        metric: 'Answerability & recall@k',
        desc: 'From probe: how often the right file is in the top k when you ask for one of your own symbols.',
    },
    {
        metric: 'MRR and blind spots',
        desc: 'Mean reciprocal rank (1.0 means the right file always comes first), and the symbols the index could not retrieve — the list to fix first.',
    },
];

export default function MeasureYourOwnPage() {
    return (
        <>
            <Navbar />
            <main className="max-w-4xl mx-auto px-4 md:px-6 pt-32 pb-16">
                <script
                    type="application/ld+json"
                    dangerouslySetInnerHTML={{
                        __html: JSON.stringify({
                            '@context': 'https://schema.org',
                            '@type': 'HowTo',
                            name: 'Measure NeuralMind on your own codebase',
                            description:
                                'Install NeuralMind, index your repository, and measure tokens per question, token reduction, and retrieval recall on your own symbols — locally, in about fifteen minutes.',
                            step: steps.map((s) => ({
                                '@type': 'HowToStep',
                                position: parseInt(s.step),
                                name: s.title,
                                text: `${s.body} Command: ${s.code.filter((c) => !c.startsWith('#')).join(' && ')}`,
                            })),
                            tool: [{ '@type': 'HowToTool', name: 'neuralmind CLI (pip install neuralmind)' }],
                            totalTime: 'PT15M',
                        }),
                    }}
                />

                <header className="mb-12 pb-8 border-b border-carbon-border">
                    <div className="flex items-center gap-3 mb-4">
                        <span className="px-3 py-1 rounded-lg bg-proton/10 text-proton text-xs font-mono">
                            ~15 minutes
                        </span>
                        <span className="text-faint text-sm">No account · runs on your machine · no telemetry</span>
                    </div>
                    <h1 className="font-display text-3xl md:text-[2.75rem] font-bold text-white mb-5 leading-[1.08] tracking-tighter">
                        Measure it on your own repo
                    </h1>
                    <p className="text-lg text-slate-300 leading-relaxed mb-6">
                        The number that decides anything for you is the one from your codebase. Three
                        commands get it — and we want you to share it, good or bad.
                    </p>
                    <p className="text-slate-400 leading-relaxed">
                        We do not have testimonials yet. What we have is a benchmark that runs locally,
                        against your code, in about fifteen minutes. Run it and read your own number. If
                        it is good,{' '}
                        <a href="mailto:hello@neuralmind.uk" className="text-electric hover:text-electric-bright transition-colors">
                            tell us — we will publish it
                        </a>
                        . If it is not, tell us that too: we will explain why, or fix it.
                    </p>
                </header>

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
                                <div className="mt-auto space-y-2">
                                    <div className="bg-carbon rounded-lg p-4 font-mono text-xs text-slate-300 overflow-x-auto">
                                        {s.code.map((line) => (
                                            <p key={line} className={`whitespace-nowrap ${line.startsWith('#') ? 'text-faint' : ''}`}>
                                                <span className="text-faint select-none">{line.startsWith('#') ? '' : '$ '}</span>
                                                {line}
                                            </p>
                                        ))}
                                    </div>
                                    {s.output && (
                                        <div className="bg-carbon rounded-lg p-4 font-mono text-xs text-slate-400 overflow-x-auto">
                                            {s.output.map((line) => (
                                                <p key={line} className="whitespace-pre">{line}</p>
                                            ))}
                                            <p className="whitespace-pre mt-2 text-faint">{'# psf/requests v2.32.3 — yours will differ'}</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </section>

                <section className="mb-14">
                    <h2 className="font-display text-xl font-bold text-white mb-6">What you get</h2>
                    <dl className="grid sm:grid-cols-2 border-t border-l border-carbon-border rounded-sm overflow-hidden">
                        {whatYouGet.map((item) => (
                            <div key={item.metric} className="border-b border-r border-carbon-border p-6">
                                <dt className="font-display text-lg font-semibold tracking-tight text-white mb-2">
                                    {item.metric}
                                </dt>
                                <dd className="text-slate-400 text-sm leading-relaxed">{item.desc}</dd>
                            </div>
                        ))}
                    </dl>
                    <p className="text-slate-400 text-sm mt-4 leading-relaxed">
                        Want correctness scored as well as cost? The{' '}
                        <a href="/benchmark/" className="text-electric hover:text-electric-bright">public benchmark</a>{' '}
                        measures against every source file and scores gold-file recall on pre-registered
                        queries — it needs a source checkout because the harness ships in the repo.
                    </p>
                </section>

                <section className="rounded-card panel-accent p-6 md:p-7">
                    <h2 className="font-display text-lg font-semibold tracking-tight text-white mb-2">
                        Already run it?
                    </h2>
                    <p className="text-slate-400 text-sm leading-relaxed mb-4">
                        Send your output to hello@neuralmind.uk and we will publish it — attributed or
                        anonymized, your choice. The only requirement: it comes from your own codebase,
                        under your own run. We are building social proof the honest way, one real number
                        at a time.
                    </p>
                    <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
                        <a
                            href="mailto:hello@neuralmind.uk?subject=My%20NeuralMind%20benchmark"
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
