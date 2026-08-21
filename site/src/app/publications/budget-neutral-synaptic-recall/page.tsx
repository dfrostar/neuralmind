import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';

const GITHUB_URL = 'https://github.com/dfrostar/neuralmind';
const IMPL_COMMIT = '89eff6c';
const SOURCE_PATH = 'docs/publications/defensive-budget-neutral-synaptic-recall.md';

export const metadata = {
    title: 'Budget-Neutral Synaptic Recall — NeuralMind',
    description: 'A method for injecting learned associative recall into an AI agent’s context window without increasing token cost: Hebbian co-activation, learned per-edge decay, hub-normalized spreading activation, and one-for-one displacement injection.',
    keywords: [
        'defensive publication',
        'prior art',
        'spreading activation',
        'Hebbian learning',
        'associative memory',
        'context window',
        'token reduction',
        'AI coding agent',
        'forgetting curve',
        'local-first',
        'NeuralMind',
    ],
    authors: [{ name: 'Darren Frost' }],
    creator: 'Darren Frost',
    publisher: 'NeuralMind',
    metadataBase: new URL('https://neuralmind.uk'),
    alternates: {
        canonical: '/publications/budget-neutral-synaptic-recall',
    },
    openGraph: {
        title: 'Budget-Neutral Synaptic Recall',
        description: 'A defensive publication establishing prior art for budget-neutral associative recall in AI agent context retrieval.',
        url: 'https://neuralmind.uk/publications/budget-neutral-synaptic-recall',
        siteName: 'NeuralMind',
        locale: 'en_US',
        type: 'article',
        publishedTime: '2026-08-07',
        modifiedTime: '2026-08-07',
        authors: ['Darren Frost'],
        tags: ['defensive publication', 'prior art', 'spreading activation', 'Hebbian learning', 'context retrieval'],
    },
    twitter: {
        card: 'summary_large_image',
        title: 'Budget-Neutral Synaptic Recall',
        description: 'A defensive publication establishing prior art for budget-neutral associative recall in AI agent context retrieval.',
        images: ['https://neuralmind.uk/social-preview.png'],
    },
    robots: {
        index: true,
        follow: true,
        googleBot: { index: true, follow: true },
    },
};

export default function PublicationPage() {
    return (
        <>
            <Navbar />
            <main className="max-w-4xl mx-auto px-4 md:px-6 py-16">
                {/* JSON-LD Article Schema */}
                <script
                    type="application/ld+json"
                    dangerouslySetInnerHTML={{
                        __html: JSON.stringify({
                            '@context': 'https://schema.org',
                            '@type': 'Article',
                            headline: 'Budget-Neutral Synaptic Recall',
                            description: 'A method for injecting learned associative recall into an AI agent’s context window without increasing token cost: Hebbian co-activation, learned per-edge decay, hub-normalized spreading activation, and displacement injection.',
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
                            datePublished: '2026-08-07',
                            dateModified: '2026-08-07',
                            mainEntityOfPage: {
                                '@type': 'WebPage',
                                '@id': 'https://neuralmind.uk/publications/budget-neutral-synaptic-recall',
                            },
                            keywords: ['defensive publication', 'prior art', 'spreading activation', 'Hebbian learning', 'associative memory', 'context retrieval'],
                            about: {
                                '@type': 'SoftwareApplication',
                                name: 'NeuralMind',
                                url: 'https://github.com/dfrostar/neuralmind',
                            },
                        }),
                    }}
                />

                {/* Header */}
                <header className="mb-12 pb-8 border-b border-carbon-border">
                    <div className="flex items-center gap-3 mb-4">
                        <span className="px-3 py-1 rounded-lg bg-electric/10 text-electric text-xs font-mono">Defensive Publication</span>
                        <span className="text-faint text-sm">August 7, 2026</span>
                    </div>
                    <h1 className="font-display text-3xl md:text-4xl font-bold text-white mb-4 leading-tight">
                        Budget-Neutral Synaptic Recall
                    </h1>
                    <p className="text-lg text-slate-300 mb-4">
                        Displacement Injection with Learned Per-Edge Decay for AI Agent Context Retrieval
                    </p>
                    <div className="flex items-center gap-4 text-sm text-slate-400 mb-4">
                        <span>Darren Frost (dfrostar)</span>
                        <span>•</span>
                        <a
                            href={`${GITHUB_URL}/blob/main/${SOURCE_PATH}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-electric hover:text-electric-bright transition-colors"
                        >
                            View source →
                        </a>
                    </div>
                    <p className="text-sm text-slate-400 bg-carbon-card border border-carbon-border rounded-lg px-4 py-3">
                        <strong className="text-white">Companion publication:</strong> the learning loop that produces the graph this method retrieves from is specified in{' '}
                        <a href="/publications/synapse-learning-loop" className="text-electric hover:text-electric-bright transition-colors">
                            Hebbian Co-Activation with Long-Term Potentiation and Hub-Normalized Spreading Activation
                        </a>
                        . This publication is its retrieval-side complement — the novel claims here are the learned per-edge half-life and budget-neutral injection.
                    </p>
                </header>

                {/* Abstract */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Abstract</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6">
                        <p className="text-slate-300 leading-relaxed">
                            A method for injecting learned associative recall into an AI coding agent&apos;s context window without increasing its token cost. Code nodes co-activated by agent tool activity are linked by Hebbian reinforcement into a weighted undirected graph. Each edge decays along an exponential half-life that is itself learned per edge from reinforcement frequency and recency. At retrieval time, spreading activation propagates energy outward from the top vector-search hits across namespace-merged edge weights, with square-root hub normalization preventing high-degree utility nodes from dominating recall. The resulting energies are folded into the vector result set budget-neutrally: nodes already present are boosted and re-ranked, and the weakest vector hits are <strong className="text-white">displaced</strong> by strongly co-activated neighbors that vector search missed — the result count, and therefore the token budget, never grows. When the graph is cold, output is byte-identical to a build without the associative layer.
                        </p>
                    </div>
                </section>

                {/* Background */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Background</h2>
                    <div className="space-y-4 text-slate-300 leading-relaxed">
                        <p>
                            Retrieval for AI coding agents is dominated by flat top-k vector search. It fails in a specific, recurring way: the files an agent <em>actually uses together</em> are often lexically unrelated — a JWT verifier and the key-loading helper it depends on share no vocabulary — so vector search never co-surfaces them, and the agent re-discovers the association by trial and error in every session. Existing remedies each have a structural flaw in the agent setting:
                        </p>
                        <ul className="list-disc list-inside space-y-2 ml-4">
                            <li><strong className="text-white">Growing the context</strong>: every appended node costs tokens; associative recall that grows the prompt competes with the budget it is meant to protect.</li>
                            <li><strong className="text-white">Static code graphs</strong>: capture compile-time structure but not usage — fixtures, config, and docs co-used with code are invisible.</li>
                            <li><strong className="text-white">Fixed-rate memory decay</strong>: treats a load-bearing association reinforced daily the same as a one-off co-occurrence.</li>
                            <li><strong className="text-white">Naive spreading activation</strong>: without degree normalization, one high-degree utility node floods every recall.</li>
                        </ul>
                        <p>
                            Our approach learns associations from the agent&apos;s own tool telemetry, forgets them at a per-edge learned rate, recalls them by hub-normalized spreading activation, and injects them by <strong className="text-white">displacement</strong> rather than <strong className="text-white">addition</strong> — recall quality improves while the token budget stays fixed.
                        </p>
                    </div>
                </section>

                {/* Core Algorithm */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Core Algorithm</h2>

                    {/* Step 1 */}
                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">1. Hebbian Co-Activation Reinforcement</h3>
                        <p className="text-slate-300 mb-3">
                            Agent activity events yield a set of co-activated node ids. Every pairwise combination is reinforced as an undirected edge under canonical ordering (<code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">node_a &lt; node_b</code>):
                        </p>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 mb-3 space-y-1 overflow-x-auto">
                            <p>Δw = <span className="text-electric-bright">0.30</span> × clamp(strength, 0.0, 2.0)</p>
                            <p>weight(a,b) = min(<span className="text-electric-bright">1.0</span>, weight(a,b) + Δw)</p>
                            <p>activation_count(a,b) += 1</p>
                        </div>
                        <p className="text-slate-300">
                            Edge upserts and activation counters commit in one transaction — a partial commit would leave counters ahead of their edges and permanently skew long-term-potentiation gating.
                        </p>
                    </div>

                    {/* Step 2 */}
                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">2. Learned Per-Edge Half-Life Decay</h3>
                        <p className="text-slate-300 mb-3">
                            Weights decay by wall-clock exponential half-life: <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">w(t) = w₀ × exp(−λ × age_days)</code>, <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">λ = ln(2) / half_life_days</code>. Namespace defaults: personal/branch 30 days, shared 60, ephemeral 1. The half-life is then <strong className="text-white">learned per edge</strong>, recomputed inside the same transaction as each reinforcement:
                        </p>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 mb-3 space-y-1 overflow-x-auto">
                            <p>freq = activation_count / age_days</p>
                            <p>confidence = exp(−ln(2) × days_since_last / ns_default)</p>
                            <p>ratio = log1p(freq × age_days / <span className="text-electric-bright">10</span>)</p>
                            <p>learned = lo + (hi − lo) × ratio / (1 + ratio)</p>
                            <p>half_life = (1 − confidence) × ns_default + confidence × learned</p>
                        </div>
                        <p className="text-slate-300 mb-3">
                            bounded to <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">[3.0, 120.0]</code> days: a rarely-used edge never decays slower than a 3-day half-life, a heavily-used one never faster than 120.
                        </p>
                        <p className="text-slate-300">
                            <strong className="text-white">Long-term potentiation:</strong> edges with lifetime <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">activation_count ≥ 5</code> are floored at weight <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">0.20</code> during decay — proven associations fade but never vanish. Weights below <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">0.01</code> are pruned.
                        </p>
                    </div>

                    {/* Step 3 */}
                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">3. Hub-Normalized Spreading Activation</h3>
                        <p className="text-slate-300 mb-3">
                            Recall seeds energy at query-relevant nodes and propagates it outward for 2 hops. Edge weights merge across memory namespaces before propagation (active branch 1.0, personal 0.8, shared 0.5):
                        </p>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 mb-3 space-y-1 overflow-x-auto">
                            <p>hub_factor(n) = sqrt(<span className="text-electric-bright">50</span> / degree(n))  <span className="text-faint">if degree(n) &gt; 50 else 1.0</span></p>
                            <p>propagated = energy × merged_weight × <span className="text-electric-bright">0.6</span> × hub_factor</p>
                        </div>
                        <p className="text-slate-300">
                            The square-root form is deliberate: a linear penalty would mute hubs so hard they stop routing energy; <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">sqrt</code> keeps them useful as conduits while preventing dominance — a degree-200 node propagates at exactly 0.5×, a degree-5000 node at 0.1×.
                        </p>
                    </div>

                    {/* Step 4 */}
                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">4. Budget-Neutral Injection: Boost + Displacement</h3>
                        <p className="text-slate-300 mb-3">
                            Activation energies fold into the vector result list under a hard invariant — <strong className="text-white">the result count never grows</strong>:
                        </p>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 mb-3 space-y-1 overflow-x-auto">
                            <p><span className="text-faint">(a) BOOST:</span> score += <span className="text-electric-bright">0.3</span> × energy <span className="text-faint">for nodes already present; re-sort</span></p>
                            <p><span className="text-faint">(b) DISPLACE:</span> swap ≤ <span className="text-electric-bright">2</span> absent nodes with energy ≥ <span className="text-electric-bright">0.15</span></p>
                            <p className="ml-4"><span className="text-faint">in for the weakest vector hits, one-for-one; keep ≥ 1 original hit</span></p>
                        </div>
                        <p className="text-slate-300">
                            Because injection is one-for-one displacement, the context assembled downstream spends exactly the same token budget with or without the associative layer. When recall is unwired, disabled, or the graph is cold, output is <strong className="text-white">byte-identical</strong> to a build without a synapse store.
                        </p>
                    </div>
                </section>

                {/* Example */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Example Walkthrough</h2>
                    <p className="text-slate-300 mb-4">
                        An agent asks about authentication. Vector search returns 8 hits; the top 3 seed spreading activation with energy 1.0.
                    </p>

                    <div className="grid md:grid-cols-2 gap-4 mb-4">
                        <div className="bg-carbon-card border border-carbon-border rounded-xl p-4">
                            <h4 className="text-white font-semibold mb-2 text-sm">Missed by vector search</h4>
                            <pre className="font-mono text-xs text-slate-300 overflow-x-auto">
{`verify_token → load_keys
personal 0.9 × 1.0 = 0.9
degree 6 → hub_factor 1.0
1.0 × 0.9 × 0.6 = 0.54`}
                            </pre>
                            <p className="text-electric-bright font-mono text-sm mt-2">0.54 ≥ 0.15 → displaces weakest hit</p>
                        </div>
                        <div className="bg-carbon-card border border-carbon-border rounded-xl p-4">
                            <h4 className="text-white font-semibold mb-2 text-sm">Already in results (#7)</h4>
                            <pre className="font-mono text-xs text-slate-300 overflow-x-auto">
{`login → session.refresh
shared 0.5 × 0.5 = 0.25
1.0 × 0.25 × 0.6 = 0.15`}
                            </pre>
                            <p className="text-electric-bright font-mono text-sm mt-2">boost 0.3 × 0.15 = 0.045 → re-ranked up</p>
                        </div>
                    </div>

                    <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 space-y-1 mb-4">
                        <p><span className="text-faint">Result:</span> 8 hits in, 8 hits out — same token budget</p>
                        <p><span className="text-faint">Gained:</span> <span className="text-electric-bright">config/secrets.py::load_keys</span> — lexically unrelated to &quot;auth&quot;, learned from co-use</p>
                        <p><span className="text-faint">Dropped:</span> a docstring stub that matched on the word &quot;auth&quot;</p>
                    </div>
                </section>

                {/* Properties */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Properties</h2>
                    <div className="space-y-6 text-slate-300 leading-relaxed">
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">Budget Neutrality</h3>
                            <p>Injection is one-for-one displacement with a fixed result count, so total context tokens are invariant to the associative layer. Recall quality and token cost are decoupled: the graph learning more never makes the prompt bigger.</p>
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">Cold-Start Identity</h3>
                            <p>Every stage no-ops to the identity function when its input signal is absent. A fresh clone produces byte-identical retrievals to a build without the layer; the graph earns influence only through observed usage.</p>
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">Hub Resistance</h3>
                            <p>With <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">hub_factor = sqrt(50/degree)</code>, utility nodes remain traversable conduits but cannot flood the top-k.</p>
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">Complexity</h3>
                            <ul className="list-disc list-inside space-y-1 ml-4">
                                <li><strong className="text-white">Reinforcement:</strong> O(k²) edge upserts per k-node activity window, one transaction</li>
                                <li><strong className="text-white">Spread:</strong> O(E_frontier) per hop, depth fixed at 2</li>
                                <li><strong className="text-white">Injection:</strong> O(n log n) re-sort; displacement is O(1) bounded</li>
                            </ul>
                        </div>
                    </div>
                </section>

                {/* Reference Implementation */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Reference Implementation</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6">
                        <ul className="space-y-3 text-sm text-slate-300">
                            <li><strong className="text-white">Language:</strong> Python 3.10+ (stdlib-only synapse layer; SQLite storage)</li>
                            <li><strong className="text-white">Repo:</strong> <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">{GITHUB_URL}</a></li>
                            <li><strong className="text-white">Commit:</strong> <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded">{IMPL_COMMIT}</code> (2026-08-07)</li>
                            <li>
                                <strong className="text-white">Files:</strong>
                                <ul className="list-disc list-inside ml-4 mt-2 space-y-1 font-mono text-xs">
                                    <li>neuralmind/synapses.py</li>
                                    <li>neuralmind/learned_decay.py</li>
                                    <li>neuralmind/context_selector.py</li>
                                    <li>neuralmind/watcher.py</li>
                                </ul>
                            </li>
                        </ul>
                    </div>
                </section>

                {/* Prior Art */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Prior Art Statement</h2>
                    <p className="text-slate-300 leading-relaxed mb-4">
                        To the best of our knowledge, the specific combination of: (1) Hebbian edge learning driven by AI-agent tool telemetry, (2) per-edge learned exponential half-life blended by recency confidence toward a namespace default, (3) square-root hub-normalized spreading activation over namespace-merged edge weights, and (4) budget-neutral injection via score boost plus one-for-one displacement with a byte-identical cold-start guarantee — has not been previously published in the context of local-first code intelligence systems.
                    </p>
                    <p className="text-slate-300 leading-relaxed">
                        Related work includes the companion <a href="/publications/synapse-learning-loop" className="text-electric hover:text-electric-bright transition-colors">NeuralMind synapse learning loop publication</a> (Frost, 2026 — specifies the capture, reinforcement, LTP, and recall machinery this method builds on, but not learned per-edge half-lives or budget-neutral injection), Hebbian learning (Hebb, 1949), spreading activation in semantic memory (Collins &amp; Loftus, 1975; Anderson&apos;s ACT-R, 1983), spreading activation in information retrieval (Crestani, 1997), forgetting curves (Ebbinghaus, 1885), retrieval-augmented generation (Lewis et al., 2020), and LLM memory hierarchies (MemGPT — Packer et al., 2023).
                    </p>
                </section>

                {/* Footer */}
                <footer className="mt-12 pt-8 border-t border-carbon-border text-center">
                    <p className="text-faint text-sm mb-2">
                        This publication establishes prior art for the techniques described herein.
                    </p>
                    <a
                        href={`${GITHUB_URL}/blob/main/${SOURCE_PATH}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-electric hover:text-electric-bright text-sm transition-colors"
                    >
                        View on GitHub →
                    </a>
                </footer>
            </main>
            <Footer />
        </>
    );
}
