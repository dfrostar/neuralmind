import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';

const GITHUB_URL = 'https://github.com/dfrostar/neuralmind';
const IMPL_COMMIT = '4256418';

export const metadata = {
    title: 'Hebbian Co-Activation with LTP and Hub-Normalized Spreading Activation — NeuralMind',
    description: 'A learning loop for local-first code intelligence: debounced file-edit co-activation strengthens weighted edges, wall-clock half-life decay forgets, long-term potentiation preserves habits, and hub-normalized spreading activation recalls.',
    keywords: [
        'defensive publication',
        'prior art',
        'Hebbian learning',
        'spreading activation',
        'long-term potentiation',
        'code intelligence',
        'synapse graph',
        'co-activation',
        'half-life decay',
        'local-first',
        'NeuralMind',
    ],
    authors: [{ name: 'Darren Frost' }],
    creator: 'Darren Frost',
    publisher: 'NeuralMind',
    metadataBase: new URL('https://neuralmind.uk'),
    alternates: {
        canonical: '/publications/synapse-learning-loop',
    },
    openGraph: {
        title: 'Hebbian Co-Activation with LTP and Hub-Normalized Spreading Activation',
        description: 'A defensive publication establishing prior art for the NeuralMind synapse learning loop: ambient co-activation, half-life decay, LTP, and spreading-activation recall.',
        url: 'https://neuralmind.uk/publications/synapse-learning-loop',
        siteName: 'NeuralMind',
        locale: 'en_US',
        type: 'article',
        publishedTime: '2026-08-06',
        modifiedTime: '2026-08-06',
        authors: ['Darren Frost'],
        tags: ['defensive publication', 'prior art', 'Hebbian learning', 'spreading activation', 'long-term potentiation', 'code intelligence'],
    },
    twitter: {
        card: 'summary_large_image',
        title: 'Hebbian Co-Activation with LTP and Hub-Normalized Spreading Activation',
        description: 'A defensive publication establishing prior art for the NeuralMind synapse learning loop.',
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
                            headline: 'Hebbian Co-Activation with Long-Term Potentiation and Hub-Normalized Spreading Activation',
                            description: 'A learning loop for local-first code intelligence: debounced file-edit co-activation strengthens weighted edges, wall-clock half-life decay forgets, LTP preserves habits, and hub-normalized spreading activation recalls.',
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
                            datePublished: '2026-08-06',
                            dateModified: '2026-08-06',
                            mainEntityOfPage: {
                                '@type': 'WebPage',
                                '@id': 'https://neuralmind.uk/publications/synapse-learning-loop',
                            },
                            keywords: ['defensive publication', 'prior art', 'Hebbian learning', 'spreading activation', 'long-term potentiation', 'code intelligence'],
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
                        <span className="text-faint text-sm">August 6, 2026</span>
                    </div>
                    <h1 className="font-display text-3xl md:text-4xl font-bold text-white mb-4 leading-tight">
                        Hebbian Co-Activation with Long-Term Potentiation and Hub-Normalized Spreading Activation
                    </h1>
                    <p className="text-lg text-slate-300 mb-4">
                        A Learning Loop for Local-First Code Intelligence
                    </p>
                    <div className="flex items-center gap-4 text-sm text-slate-400">
                        <span>Darren Frost (dfrostar)</span>
                        <span>•</span>
                        <a
                            href={`${GITHUB_URL}/blob/main/docs/publications/defensive-synapse-learning-loop.md`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-electric hover:text-electric-bright transition-colors"
                        >
                            View source →
                        </a>
                    </div>
                </header>

                {/* Abstract */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Abstract</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6">
                        <p className="text-slate-300 leading-relaxed">
                            A method for learning and recalling associations between code entities from ambient developer activity, wherein file edits occurring in close temporal proximity are coalesced into co-activation batches that strengthen weighted edges between the touched entities (Hebbian reinforcement), wherein edge weights undergo wall-clock exponential half-life decay with per-namespace and per-edge learned rates, wherein frequently reinforced edges acquire long-term potentiation (a decay floor and prune immunity), and wherein recall is performed by hub-normalized spreading activation over the merged multi-namespace graph. The loop runs entirely locally over a SQLite store, requires no telemetry or central service, and supplies an AI coding agent with associative context the static call graph cannot express.
                        </p>
                    </div>
                </section>

                {/* Background */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Background</h2>
                    <div className="space-y-4 text-slate-300 leading-relaxed">
                        <p>
                            AI coding agents retrieve context by embedding similarity or static program analysis. Both miss the associations that only usage reveals:
                        </p>
                        <ul className="list-disc list-inside space-y-2 ml-4">
                            <li><strong className="text-white">Embedding retrieval</strong> surfaces textually similar code, not code that <em>changes together</em> — a config file and the handler that consumes it share no vocabulary.</li>
                            <li><strong className="text-white">Static graphs</strong> capture declared relations (calls, imports) but not workflow relations — the test fixture always edited alongside a parser, the migration that accompanies a model change.</li>
                            <li><strong className="text-white">Version-history mining</strong> captures coupled changes only at commit granularity, offline, and without decay — stale couplings persist forever.</li>
                        </ul>
                        <p>
                            Our approach observes the working session itself: edits within a debounce window co-activate; co-activation strengthens edges; disuse decays them; habitual pairs become durable via long-term potentiation; and recall spreads activation outward from query-relevant seed nodes across the learned graph.
                        </p>
                    </div>
                </section>

                {/* Core Algorithm */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Core Algorithm</h2>

                    <div className="mb-8">
                        <h3 className="font-display text-lg font-semibold text-white mb-3">1. Co-Activation Capture</h3>
                        <p className="text-slate-300 leading-relaxed mb-3">
                            A file-activity watcher coalesces filesystem edits into batches. Edits arriving within a debounce window (default <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">0.75 s</code>) of one another are grouped; a batch is flushed when the window goes quiet and delivered as a single co-activation event. Generated artifacts are excluded to prevent phantom edges. File deletions bypass the debounce and trigger <em>targeted accelerated decay</em> on the dead file&apos;s edges — stale memory pointing at refactored-away code is worse than no memory.
                        </p>
                    </div>

                    <div className="mb-8">
                        <h3 className="font-display text-lg font-semibold text-white mb-3">2. Hebbian Reinforcement</h3>
                        <p className="text-slate-300 leading-relaxed mb-3">
                            For a co-activation batch, every unordered pair of nodes receives a weight bump:
                        </p>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 mb-3 overflow-x-auto">
                            Δw = LEARNING_RATE × clamp(strength, 0, 2)&nbsp;&nbsp;&nbsp;# LEARNING_RATE = 0.30<br />
                            w&nbsp;&nbsp;← min(WEIGHT_CAP, w + Δw)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# WEIGHT_CAP = 1.0
                        </div>
                        <p className="text-slate-300 leading-relaxed">
                            Each node&apos;s activation counter increments in the <strong className="text-white">same transaction</strong> as the edge upserts — a partial commit would skew LTP gating. A separate <strong className="text-white">directed transition</strong> signal records sequential order (&quot;A was active, then B&quot;) for next-action prediction.
                        </p>
                    </div>

                    <div className="mb-8">
                        <h3 className="font-display text-lg font-semibold text-white mb-3">3. Wall-Clock Half-Life Decay</h3>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 mb-3 overflow-x-auto">
                            w(t) = w₀ · exp(−λ · age_days),&nbsp;&nbsp;&nbsp;λ = ln 2 / H
                        </div>
                        <p className="text-slate-300 leading-relaxed">
                            The half-life <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">H</code> resolves per namespace — <strong className="text-white">30 d</strong> personal/branch, <strong className="text-white">60 d</strong> shared team baseline, <strong className="text-white">1 d</strong> ephemeral scratch — with per-edge <em>learned</em> overrides adapted from reinforcement history. Weights below <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">0.01</code> are pruned. Age derives from the stored last-activation timestamp, so decay is a pure function of wall-clock time, not pass frequency.
                        </p>
                    </div>

                    <div className="mb-8">
                        <h3 className="font-display text-lg font-semibold text-white mb-3">4. Long-Term Potentiation</h3>
                        <p className="text-slate-300 leading-relaxed">
                            Edges reinforced at least <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">5</code> times acquire durability: decay is floored at <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">0.20</code> and pruning skips them. One-off coincidences fade completely; habitual associations survive vacations. The ephemeral namespace is exempt — session scratch must die.
                        </p>
                    </div>

                    <div className="mb-8">
                        <h3 className="font-display text-lg font-semibold text-white mb-3">5. Namespaced Storage with Merged Read</h3>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 mb-3 overflow-x-auto">
                            merged_weight = 1.0·w_active + 0.8·w_personal + 0.5·w_shared
                        </div>
                        <p className="text-slate-300 leading-relaxed">
                            Recent branch-local context always wins; the imported team baseline is never louder than the developer&apos;s own memory.
                        </p>
                    </div>

                    <div className="mb-8">
                        <h3 className="font-display text-lg font-semibold text-white mb-3">6. Hub-Normalized Spreading Activation</h3>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 mb-3 overflow-x-auto">
                            hub_factor = sqrt(HUB_DEGREE / degree) if degree &gt; 50 else 1.0<br />
                            propagated = energy × merged_weight × SPREAD_DECAY × hub_factor&nbsp;&nbsp;&nbsp;# SPREAD_DECAY = 0.6
                        </div>
                        <p className="text-slate-300 leading-relaxed">
                            Recall seeds the graph with query-relevant nodes and propagates energy outward for 2 hops by default; energies accumulate additively across paths; the top-K nodes (default 12, seeds excluded) become recall output. The <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">√(50/degree)</code> term suppresses runaway central nodes — a utility module touched by everything would otherwise dominate every recall. An attribution variant tracks per-namespace energy shares, explaining exactly which namespace produced each recalled node.
                        </p>
                    </div>
                </section>

                {/* Properties */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Properties</h2>
                    <div className="space-y-4 text-slate-300 leading-relaxed">
                        <p>
                            <strong className="text-white">Stability–plasticity balance.</strong> New associations form after a single co-activation yet vanish within weeks if never repeated; habitual associations (≥5 reinforcements) are permanent-but-quiet at worst.
                        </p>
                        <p>
                            <strong className="text-white">Bounded and convergent.</strong> Weights cap at 1.0; hub normalization bounds per-hop amplification to √d for degree d &gt; 50; with SPREAD_DECAY 0.6 and depth 2, activation strictly attenuates with distance.
                        </p>
                        <p>
                            <strong className="text-white">Deterministic decay.</strong> Running the decay pass hourly or weekly yields identical weights for identical timestamps — the model survives sleeping laptops, sporadic CI, and idle clones.
                        </p>
                        <p>
                            <strong className="text-white">Complexity.</strong> Reinforcement is O(k²) over a small human-editing batch in one transaction; decay is set-based SQL over all edges; spread is O(frontier × avg-degree) per hop, depth-bounded.
                        </p>
                    </div>
                </section>

                {/* Reference Implementation */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Reference Implementation</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6 text-slate-300 text-sm leading-relaxed">
                        <p className="mb-3">Python 3.10+ (stdlib-only for the synapse layer). Commit <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-xs">{IMPL_COMMIT}</code> (2026-08-06).</p>
                        <ul className="list-disc list-inside space-y-1">
                            <li><code className="text-electric-bright bg-carbon px-1 rounded text-xs">neuralmind/synapses.py</code> — reinforce(), decay(), _spread(), record_sequence(), namespace merge weighting</li>
                            <li><code className="text-electric-bright bg-carbon px-1 rounded text-xs">neuralmind/watcher.py</code> — debounced co-activation batching, deletion-triggered targeted decay</li>
                            <li><code className="text-electric-bright bg-carbon px-1 rounded text-xs">neuralmind/learned_decay.py</code> — per-edge learned half-life adaptation</li>
                            <li><code className="text-electric-bright bg-carbon px-1 rounded text-xs">tests/test_synapses.py</code>, <code className="text-electric-bright bg-carbon px-1 rounded text-xs">test_synapse_namespaces.py</code>, <code className="text-electric-bright bg-carbon px-1 rounded text-xs">test_watcher.py</code>, <code className="text-electric-bright bg-carbon px-1 rounded text-xs">test_learned_decay.py</code></li>
                        </ul>
                    </div>
                </section>

                {/* Prior Art Statement */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Prior Art Statement</h2>
                    <div className="space-y-4 text-slate-300 leading-relaxed">
                        <p>
                            To the best of our knowledge, the specific combination of debounce-windowed filesystem co-activation, capped Hebbian strengthening with transactional activation counting, wall-clock half-life decay with per-namespace policy and learned per-edge overrides, activation-count-gated long-term potentiation, hub-normalized spreading activation over a multiplier-merged multi-namespace graph, and deletion-triggered targeted decay — applied to context retrieval for AI coding agents in a local-first, telemetry-free system — has not been previously published. Related work:
                        </p>
                        <ul className="list-disc list-inside space-y-2 ml-4">
                            <li><strong className="text-white">Hebbian learning</strong> (Hebb, 1949) — the co-activation principle, without decay policy, LTP gating, or code-entity application</li>
                            <li><strong className="text-white">Long-term potentiation</strong> (Bliss &amp; Lømo, 1973) — biological analogue of the durability mechanism</li>
                            <li><strong className="text-white">Spreading activation</strong> (Collins &amp; Loftus, 1975) — semantic-network recall, without hub normalization or namespace merging</li>
                            <li><strong className="text-white">ACT-R declarative memory</strong> (Anderson &amp; Lebiere, 1998) — base-level activation with time decay, for cognitive modeling rather than code graphs learned from editor activity</li>
                            <li><strong className="text-white">Mining version histories</strong> (Zimmermann et al., 2004) — co-change coupling at commit granularity, offline, without decay or recall-time spread</li>
                        </ul>
                    </div>
                </section>

                <div className="border-t border-carbon-border pt-8 text-sm text-faint italic">
                    This publication establishes prior art for the techniques described herein. It is provided for defensive purposes and as technical documentation for the NeuralMind open-source project.
                </div>
            </main>
            <Footer />
        </>
    );
}
