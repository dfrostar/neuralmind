import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';

const GITHUB_URL = 'https://github.com/dfrostar/neuralmind';
const CANONICAL = 'https://neuralmind.uk/field-reports/measure-memory-across-a-refactor/';
const WALKTHROUGH_URL = `${GITHUB_URL}/blob/main/docs/use-cases/measure-memory-across-a-refactor.md`;
const PUBLISHED = '2026-07-20';

export const metadata = {
    title: 'Field Report: AI Agent Memory Across a Major Refactor — 48.8× Token Reduction | NeuralMind',
    description:
        'Real-world case study: a ~9,300-node TypeScript SaaS platform rebuilt with NeuralMind watching — 48.8× token reduction, personal synapse edges 36→135. Full numbers, method, and a recipe to measure your own refactor.',
    keywords: [
        'AI coding agent memory',
        'token reduction case study',
        'AI agent refactoring',
        'context compression benchmark',
        'Hebbian synapse layer',
        'code intelligence field report',
        'LLM token cost reduction',
        'measure agent memory',
        'refactor with AI agent',
        'NeuralMind',
    ],
    authors: [{ name: 'Darren Frost' }],
    creator: 'Darren Frost',
    publisher: 'NeuralMind',
    metadataBase: new URL('https://neuralmind.uk'),
    alternates: {
        canonical: '/field-reports/measure-memory-across-a-refactor/',
    },
    openGraph: {
        title: 'Field Report: AI Agent Memory Across a Major Refactor',
        description:
            'A ~9,300-node TypeScript SaaS platform was rebuilt with NeuralMind watching: 48.8× token reduction, synapse edges 36→135. One repo, honestly measured — with the recipe to run it on yours.',
        url: CANONICAL,
        siteName: 'NeuralMind',
        locale: 'en_US',
        type: 'article',
        publishedTime: PUBLISHED,
        modifiedTime: PUBLISHED,
        authors: ['Darren Frost'],
        tags: ['field report', 'case study', 'token reduction', 'AI agent memory', 'refactoring'],
        images: [
            {
                url: '/social-preview.png',
                width: 1200,
                height: 630,
                alt: 'NeuralMind field report: AI agent memory across a major refactor',
            },
        ],
    },
    twitter: {
        card: 'summary_large_image',
        title: 'Field Report: AI Agent Memory Across a Major Refactor',
        description:
            '48.8× token reduction and synapse edges 36→135, measured across a real rebuild of a ~9,300-node TypeScript SaaS platform.',
        images: ['https://neuralmind.uk/social-preview.png'],
    },
    robots: {
        index: true,
        follow: true,
        googleBot: { index: true, follow: true },
    },
};

const numbers = [
    { metric: 'Total nodes', before: '9,190', after: '9,293', change: '+103' },
    { metric: 'Communities', before: '—', after: '810', change: 'new resolution — no comparable before' },
    { metric: 'Personal synapse edges', before: '36', after: '135', change: '+275%', highlight: true },
    { metric: 'Shared synapse edges', before: '10,079', after: '10,183', change: '+104' },
    { metric: 'Shared edge weight', before: '2,774.73', after: '2,924.66', change: '+5.4%', highlight: true },
    { metric: 'Wake-up tokens', before: '—', after: '455', change: '' },
    { metric: 'Avg query tokens', before: '—', after: '1,033', change: '' },
    { metric: 'Avg token reduction', before: '—', after: '48.8×', change: 'vs loading files naively', highlight: true },
    { metric: 'Full --force rebuild', before: '—', after: '326 s (~5.4 min)', change: 'incremental rebuilds ~30 s after' },
];

const provenance = [
    { metric: 'Total nodes, communities', command: 'neuralmind stats . --json' },
    { metric: 'Personal/shared edges, edge weight', command: 'neuralmind stats . — the Memory namespaces block' },
    { metric: 'Wake-up / query tokens, reduction', command: 'neuralmind benchmark .' },
    { metric: 'Rebuild time', command: 'timed neuralmind build . --force' },
    { metric: 'Synapses fired per query', command: 'neuralmind metrics .' },
    { metric: 'Real logged spend', command: 'neuralmind savings .' },
];

const jsonLd = {
    '@context': 'https://schema.org',
    '@graph': [
        {
            '@type': 'TechArticle',
            headline: 'Field Report: AI Agent Memory Across a Major Refactor',
            alternativeHeadline: '48.8× token reduction and synapse growth measured across a real rebuild',
            description:
                'Real-world case study measuring NeuralMind across a major internal rebuild of a private ~9,300-node TypeScript SaaS platform: 48.8× average token reduction, personal synapse edges 36→135, shared edge weight +5.4%.',
            author: {
                '@type': 'Person',
                name: 'Darren Frost',
                url: 'https://github.com/dfrostar',
            },
            publisher: {
                '@type': 'Organization',
                name: 'NeuralMind',
                url: 'https://neuralmind.uk',
            },
            datePublished: PUBLISHED,
            dateModified: PUBLISHED,
            mainEntityOfPage: { '@type': 'WebPage', '@id': CANONICAL },
            image: 'https://neuralmind.uk/social-preview.png',
            keywords: [
                'AI coding agent memory',
                'token reduction case study',
                'context compression',
                'Hebbian synapse layer',
                'refactoring',
            ],
            about: {
                '@type': 'SoftwareApplication',
                name: 'NeuralMind',
                url: GITHUB_URL,
            },
        },
        {
            '@type': 'BreadcrumbList',
            itemListElement: [
                { '@type': 'ListItem', position: 1, name: 'NeuralMind', item: 'https://neuralmind.uk/' },
                { '@type': 'ListItem', position: 2, name: 'Field Reports', item: 'https://neuralmind.uk/field-reports/' },
                { '@type': 'ListItem', position: 3, name: 'Memory Across a Major Refactor', item: CANONICAL },
            ],
        },
    ],
};

export default function FieldReportPage() {
    return (
        <>
            <Navbar />
            <main className="max-w-4xl mx-auto px-4 md:px-6 py-16">
                <script
                    type="application/ld+json"
                    dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
                />

                {/* Header */}
                <header className="mb-12 pb-8 border-b border-carbon-border">
                    <div className="flex items-center gap-3 mb-4 flex-wrap">
                        <span className="px-3 py-1 rounded-lg bg-proton/10 text-proton text-xs font-mono">Field Report — not CI-gated</span>
                        <span className="text-faint text-sm">July 20, 2026</span>
                    </div>
                    <h1 className="font-display text-3xl md:text-4xl font-bold text-white mb-4 leading-tight">
                        Measuring AI agent memory across a major refactor
                    </h1>
                    <p className="text-lg text-slate-300 mb-4">
                        A ~9,300-node TypeScript SaaS platform was rebuilt with NeuralMind watching.
                        The memory didn&apos;t go stale — it grew into the new architecture. Here are the
                        numbers, where each one came from, and how to run the same measurement on your repo.
                    </p>
                    <div className="flex items-center gap-4 text-sm text-slate-400">
                        <span>Darren Frost (dfrostar)</span>
                        <span>•</span>
                        <a
                            href={WALKTHROUGH_URL}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-electric hover:text-electric-bright transition-colors"
                        >
                            Full walkthrough on GitHub →
                        </a>
                    </div>
                </header>

                {/* Headline stats */}
                <section className="mb-10">
                    <div className="grid sm:grid-cols-3 gap-4">
                        <div className="card rounded-2xl p-6">
                            <p className="text-faint text-xs font-semibold uppercase tracking-wider mb-2">Avg token reduction</p>
                            <p className="font-display text-3xl font-bold text-white mb-1">48.8×</p>
                            <p className="text-slate-400 text-sm">~1,033 tokens/query vs 50K+ naive</p>
                        </div>
                        <div className="card rounded-2xl p-6">
                            <p className="text-faint text-xs font-semibold uppercase tracking-wider mb-2">Personal synapse edges</p>
                            <p className="font-display text-3xl font-bold text-white mb-1">36 → 135</p>
                            <p className="text-slate-400 text-sm">the learning layer tracked the new code</p>
                        </div>
                        <div className="card rounded-2xl p-6">
                            <p className="text-faint text-xs font-semibold uppercase tracking-wider mb-2">Full rebuild</p>
                            <p className="font-display text-3xl font-bold text-white mb-1">326 s</p>
                            <p className="text-slate-400 text-sm">then back to ~30 s incremental</p>
                        </div>
                    </div>
                </section>

                {/* The setting */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">The setting</h2>
                    <div className="space-y-4 text-slate-300 leading-relaxed">
                        <p>
                            A private, mid-size TypeScript SaaS platform (~9,300 indexed nodes), maintained by
                            NeuralMind&apos;s own maintainer — see the honesty notes below. A major internal rebuild
                            (&quot;Phase 3 → Phase 4&quot;) landed a new backend module, a shared business-logic layer,
                            an admin UI, and end-to-end specs.
                        </p>
                        <p>
                            NeuralMind ran throughout with lifecycle hooks installed, so the synapse layer observed
                            the work as it happened. The repo is private, so the numbers are anonymized; every one
                            of them came from the shipped CLI.
                        </p>
                    </div>
                </section>

                {/* The numbers */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">The numbers</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-4 overflow-x-auto">
                        <table className="w-full text-sm min-w-[540px]">
                            <thead>
                                <tr className="border-b border-carbon-border">
                                    <th className="text-left py-2 text-slate-400 font-medium">Metric</th>
                                    <th className="text-right py-2 text-slate-400 font-medium">Before (Phase 3)</th>
                                    <th className="text-right py-2 text-slate-400 font-medium">After (Phase 4)</th>
                                    <th className="text-left py-2 pl-4 text-slate-400 font-medium">Change</th>
                                </tr>
                            </thead>
                            <tbody className="text-slate-300">
                                {numbers.map((row) => (
                                    <tr key={row.metric} className="border-b border-carbon-border/50 last:border-0">
                                        <td className="py-2 pr-4">{row.metric}</td>
                                        <td className="py-2 text-right font-mono">{row.before}</td>
                                        <td className={`py-2 text-right font-mono ${row.highlight ? 'text-electric-bright font-bold' : ''}`}>{row.after}</td>
                                        <td className={`py-2 pl-4 ${row.highlight ? 'text-white' : 'text-slate-400'}`}>{row.change}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>

                {/* Interpretation */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">What the numbers say</h2>
                    <div className="space-y-4 text-slate-300 leading-relaxed">
                        <p>
                            <strong className="text-white">48.8× token reduction.</strong> After the rebuild, an average
                            code question cost ~1,033 tokens of context instead of the 50K+ a naive &quot;load the
                            relevant files&quot; approach would spend. That is one repo&apos;s measured ratio from{' '}
                            <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">neuralmind benchmark .</code>,
                            consistent with the 12-50× real-repo range — not a universal guarantee.
                        </p>
                        <p>
                            <strong className="text-white">Personal synapse edges tripled (36 → 135).</strong> The Hebbian
                            synapse layer learned co-activations across the <em>new</em> code as it was being written
                            and queried. The memory didn&apos;t go stale through the rebuild; it grew into the new
                            architecture.
                        </p>
                        <p>
                            <strong className="text-white">Shared edge weight +5.4%.</strong> The static graph&apos;s
                            cross-links got denser as the new shared business-logic layer connected previously
                            separate areas — densification, not just growth: edge weight rose 5.4% on only
                            1.1% more nodes.
                        </p>
                        <p>
                            <strong className="text-white">Rebuild cost stayed flat.</strong> One full{' '}
                            <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">--force</code>{' '}
                            rebuild at 326 s to pick up the new structure, then incremental rebuilds back to ~30 s.
                            Re-indexing is not a tax you pay per edit.
                        </p>
                    </div>
                </section>

                {/* Provenance */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Where each number comes from</h2>
                    <p className="text-slate-300 mb-4 leading-relaxed">
                        Honesty first: the before/after table is <strong className="text-white">hand-assembled from the
                        output of several commands</strong> — there is no single{' '}
                        <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">neuralmind compare-phases</code>{' '}
                        command.
                    </p>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-4 overflow-x-auto">
                        <table className="w-full text-sm min-w-[480px]">
                            <thead>
                                <tr className="border-b border-carbon-border">
                                    <th className="text-left py-2 text-slate-400 font-medium">Metric</th>
                                    <th className="text-left py-2 text-slate-400 font-medium">Command</th>
                                </tr>
                            </thead>
                            <tbody className="text-slate-300">
                                {provenance.map((row) => (
                                    <tr key={row.metric} className="border-b border-carbon-border/50 last:border-0">
                                        <td className="py-2 pr-4">{row.metric}</td>
                                        <td className="py-2 font-mono text-xs text-electric-bright">{row.command}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>

                {/* Recipe */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Run the same measurement on your refactor</h2>
                    <div className="space-y-6">
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">1. Snapshot before you start</h3>
                            <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 overflow-x-auto">
                                <p>neuralmind stats . --json &gt; .neuralmind-before.json</p>
                                <p>neuralmind benchmark .      <span className="text-faint"># baseline reduction number</span></p>
                            </div>
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">2. Refactor with the memory watching</h3>
                            <p className="text-slate-300 mb-2 text-sm">
                                The synapse layer only learns from what it observes — install hooks <em>before</em> the work starts.
                            </p>
                            <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 overflow-x-auto">
                                <p>neuralmind install-hooks .</p>
                                <p>neuralmind watch &amp;   <span className="text-faint"># optional: always-on learning from edits</span></p>
                            </div>
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">3. Rebuild and snapshot after</h3>
                            <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 overflow-x-auto">
                                <p>time neuralmind build . --force</p>
                                <p>neuralmind stats . --json &gt; .neuralmind-after.json</p>
                            </div>
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">4. Re-benchmark and price it</h3>
                            <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 overflow-x-auto">
                                <p>neuralmind benchmark .   <span className="text-faint"># reduction on the post-refactor graph</span></p>
                                <p>neuralmind savings .     <span className="text-faint"># what your logged queries cost vs naive</span></p>
                            </div>
                        </div>
                        <p className="text-slate-300 leading-relaxed">
                            Diff the two JSON files. The interesting deltas: node count (did the graph track the new
                            code?), personal edges (did the memory learn the new co-activations?), shared edge weight
                            (did the graph get denser or just bigger?). The{' '}
                            <a href={WALKTHROUGH_URL} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">
                                full step-by-step walkthrough
                            </a>{' '}
                            lives in the docs.
                        </p>
                    </div>
                </section>

                {/* Honesty notes */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Honesty notes</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6 space-y-3 text-slate-300 leading-relaxed text-sm">
                        <p>
                            <strong className="text-white">One repo, one developer, measured by the maintainer on a private
                            codebase.</strong> It is an existence proof and a recipe, not an independent benchmark. You
                            cannot re-run it on the source repo — but you can run the identical method on yours,
                            which is the point.
                        </p>
                        <p>
                            <strong className="text-white">48.8× is a reduction in retrieval input tokens</strong>, not your
                            total LLM bill. For typical end-to-end agent sessions the realistic total-cost saving is
                            smaller — see the{' '}
                            <a href={`${GITHUB_URL}/blob/main/docs/HONEST-ASSESSMENT.md`} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">
                                honest assessment
                            </a>.
                        </p>
                        <p>
                            <strong className="text-white">The CI-gated, reproducible numbers</strong> live in{' '}
                            <a href={`${GITHUB_URL}/blob/main/docs/wiki/Benchmarks.md`} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">
                                Benchmarks &amp; Results
                            </a>{' '}
                            and on the{' '}
                            <a href="/#benchmarks" className="text-electric hover:text-electric-bright">
                                benchmarks section
                            </a>{' '}
                            of this site; this page is deliberately labeled a field report.
                        </p>
                    </div>
                </section>

                {/* CTA */}
                <footer className="mt-12 pt-8 border-t border-carbon-border text-center">
                    <p className="text-slate-400 mb-4">
                        Measure your own refactor — the whole recipe is four commands.
                    </p>
                    <div className="flex items-center justify-center gap-4 flex-wrap">
                        <a
                            href="https://pypi.org/project/neuralmind/"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn-primary text-sm"
                        >
                            pip install neuralmind
                        </a>
                        <a
                            href={WALKTHROUGH_URL}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-electric hover:text-electric-bright text-sm transition-colors"
                        >
                            Read the full walkthrough →
                        </a>
                    </div>
                </footer>
            </main>
            <Footer />
        </>
    );
}
