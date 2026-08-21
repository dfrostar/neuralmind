import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';

const GITHUB_URL = 'https://github.com/dfrostar/neuralmind';
const POST_COMMIT = '31aac0e';

export const metadata = {
    title: 'Quality-Weighted Merge with Conflict-Driven Decay — NeuralMind',
    description: 'A method for resolving conflicting assertions in a distributed edge-weight graph. Each edge carries a quality score from reinforcement, recency, and conflict rate. The loser is excluded, forcing consensus.',
    keywords: [
        'defensive publication',
        'prior art',
        'edge-weight graph',
        'conflict resolution',
        'distributed consensus',
        'team memory',
        'Hebbian learning',
        'synaptic merge',
        'local-first',
        'NeuralMind',
    ],
    authors: [{ name: 'Darren Frost' }],
    creator: 'Darren Frost',
    publisher: 'NeuralMind',
    metadataBase: new URL('https://neuralmind.uk'),
    alternates: {
        canonical: '/publications/quality-weighted-merge',
    },
    openGraph: {
        title: 'Quality-Weighted Merge with Conflict-Driven Decay',
        description: 'A defensive publication establishing prior art for conflict resolution in local-first edge-weight graphs.',
        url: 'https://neuralmind.uk/publications/quality-weighted-merge',
        siteName: 'NeuralMind',
        locale: 'en_US',
        type: 'article',
        publishedTime: '2026-07-22',
        modifiedTime: '2026-07-22',
        authors: ['Darren Frost'],
        tags: ['defensive publication', 'prior art', 'edge-weight graph', 'conflict resolution', 'team memory'],
    },
    twitter: {
        card: 'summary_large_image',
        title: 'Quality-Weighted Merge with Conflict-Driven Decay',
        description: 'A defensive publication establishing prior art for conflict resolution in local-first edge-weight graphs.',
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
                            headline: 'Quality-Weighted Merge with Conflict-Driven Decay',
                            description: 'A method for resolving conflicting assertions in a distributed edge-weight graph. Each edge carries a quality score from reinforcement, recency, and conflict rate.',
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
                            datePublished: '2026-07-22',
                            dateModified: '2026-07-22',
                            mainEntityOfPage: {
                                '@type': 'WebPage',
                                '@id': 'https://neuralmind.uk/publications/quality-weighted-merge',
                            },
                            keywords: ['defensive publication', 'prior art', 'edge-weight graph', 'conflict resolution', 'team memory', 'Hebbian learning'],
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
                        <span className="text-faint text-sm">July 22, 2026</span>
                    </div>
                    <h1 className="font-display text-3xl md:text-4xl font-bold text-white mb-4 leading-tight">
                        Quality-Weighted Merge with Conflict-Driven Decay
                    </h1>
                    <p className="text-lg text-slate-300 mb-4">
                        A Method for Forcing Convergence in Distributed Edge-Weight Graphs
                    </p>
                    <div className="flex items-center gap-4 text-sm text-slate-400">
                        <span>Darren Frost (dfrostar)</span>
                        <span>•</span>
                        <a
                            href={`${GITHUB_URL}/blob/${POST_COMMIT}/docs/publications/defensive-quality-weighted-merge.md`}
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
                            A method for resolving conflicting assertions in a distributed edge-weight graph, wherein each edge carries a quality score computed from reinforcement frequency, recency of activation, and historical conflict rate, and wherein the loser of a conflict is excluded from the shared namespace, forcing the graph toward consensus without central coordination. Stale edges (inactive past a namespace-specific threshold) undergo accelerated decay via a constant per-pass factor that avoids compounding explosion. The algorithm is local-first, stdlib-only, and operates over a committed JSON bundle that propagates through version control.
                        </p>
                    </div>
                </section>

                {/* Background */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Background</h2>
                    <div className="space-y-4 text-slate-300 leading-relaxed">
                        <p>
                            Existing distributed knowledge graphs (Google Knowledge Graph, Wikidata, enterprise graph databases) rely on central curation or voting mechanisms to resolve conflicting assertions. These approaches fail in local-first, edge-compute scenarios:
                        </p>
                        <ul className="list-disc list-inside space-y-2 ml-4">
                            <li><strong className="text-white">Last-write-wins</strong> (default Git merge): discards contributor quality signal, rewards recency over accuracy.</li>
                            <li><strong className="text-white">MAX-merge</strong> (naive synaptic import): allows a single over-eager contributor to permanently distort shared recall.</li>
                            <li><strong className="text-white">Consensus voting</strong> (Raft/Paxos): requires online coordination — unusable in disconnected, git-clone-and-fork workflows.</li>
                        </ul>
                        <p>
                            Our approach: each edge carries its own quality signal, and conflict resolution is purely local — no coordinator, no quorum, no round-trips. The loser of each conflict is excluded, so the system converges to the highest-quality assertions without any node having global authority.
                        </p>
                    </div>
                </section>

                {/* Core Algorithm */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Core Algorithm</h2>

                    {/* Step 1 */}
                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">1. Edge Quality Scoring</h3>
                        <p className="text-slate-300 mb-3">
                            Each edge <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">e</code> in namespace <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">ns</code> is scored by a composite quality function:
                        </p>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 mb-3">
                            <p>score(e) = w<sub>r</sub> × reinforcement(e) + w<sub>t</sub> × recency(e) − w<sub>c</sub> × conflict_rate(e)</p>
                        </div>
                        <p className="text-slate-300 mb-3">where:</p>
                        <ul className="list-disc list-inside space-y-2 text-slate-300 ml-4 mb-4">
                            <li><code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">reinforcement(e) = log1p(activation_count) / log1p(30)</code> — saturates at ~1.0 after 30 activations</li>
                            <li><code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">recency(e) = exp(−0.693 × days_since_last_activation / 30.0)</code> — 30-day half-life</li>
                            <li><code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">conflict_rate(e) = conflict_count / max(1, total_comparisons)</code> — [0.0, 1.0]</li>
                        </ul>
                        <p className="text-slate-300 mb-3">
                            Default weights: <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">w<sub>r</sub> = 0.4</code>, <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">w<sub>t</sub> = 0.35</code>, <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">w<sub>c</sub> = 0.25</code>. Theoretical maximum is 0.75 (achievable when activation_count ≥ 30 and edge was just activated). In practice, most edges score below 0.70.
                        </p>

                        {/* Classification bands */}
                        <div className="bg-carbon-card border border-carbon-border rounded-xl p-4 mb-4">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-carbon-border">
                                        <th className="text-left py-2 text-slate-400 font-medium">Score</th>
                                        <th className="text-left py-2 text-slate-400 font-medium">Action</th>
                                    </tr>
                                </thead>
                                <tbody className="text-slate-300">
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2 font-mono text-electric-bright">≥ 0.70</td>
                                        <td className="py-2">Auto-promote to <code className="text-electric-bright bg-carbon px-1 rounded text-xs">shared</code> namespace</td>
                                    </tr>
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2 font-mono text-electric-bright">[0.30, 0.70)</td>
                                        <td className="py-2">Retain as neutral (survives import, but doesn't win conflicts against ≥0.70 edges)</td>
                                    </tr>
                                    <tr>
                                        <td className="py-2 font-mono text-electric-bright">&lt; 0.30</td>
                                        <td className="py-2">Reject (excluded from <code className="text-electric-bright bg-carbon px-1 rounded text-xs">shared</code>)</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        <p className="text-slate-300 text-sm">
                            <strong className="text-white">Peer review:</strong> Edges in the [0.30, 0.70) range are evaluated by <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-xs">PeerReviewGate</code> (E3) — a secondary gating mechanism that can auto-promote, reject, or queue for operator review based on additional heuristics.
                        </p>
                    </div>

                    {/* Step 2 */}
                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">2. Conflict Resolution</h3>
                        <p className="text-slate-300 mb-3">
                            When two bundles contain edges for the same <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">(source, target)</code> pair:
                        </p>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 mb-3 space-y-1 overflow-x-auto">
                            <p><span className="text-faint">resolve(existing, incoming):</span></p>
                            <p className="ml-4"><span className="text-faint">if</span> |existing.score − incoming.score| &lt; <span className="text-electric-bright">0.05</span> <span className="text-faint">AND</span> max(existing.score, incoming.score) &lt; <span className="text-electric-bright">0.30</span>:</p>
                            <p className="ml-8"><span className="text-faint">return</span> CONTEST  <span className="text-faint">→ escalate to review</span></p>
                            <p className="ml-4"><span className="text-faint">else:</span></p>
                            <p className="ml-8">winner = argmax(existing.score, incoming.score)</p>
                            <p className="ml-8"><span className="text-faint">return</span> winner  <span className="text-faint">→ loser is dropped</span></p>
                        </div>
                    </div>

                    {/* Step 3 */}
                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">3. Staleness Detection</h3>
                        <p className="text-slate-300 mb-3">
                            Edges inactive past a namespace-specific threshold undergo accelerated decay:
                        </p>
                        <div className="bg-carbon-card border border-carbon-border rounded-xl p-4 mb-3">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-carbon-border">
                                        <th className="text-left py-2 text-slate-400 font-medium">Namespace</th>
                                        <th className="text-left py-2 text-slate-400 font-medium">Stale after</th>
                                        <th className="text-left py-2 text-slate-400 font-medium">Decay factor per pass</th>
                                    </tr>
                                </thead>
                                <tbody className="text-slate-300">
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2 font-mono text-electric-bright">shared</td>
                                        <td className="py-2">30 days</td>
                                        <td className="py-2 font-mono">2<sup>(−5/30)</sup> ≈ 0.891</td>
                                    </tr>
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2 font-mono text-electric-branch">branch:*</td>
                                        <td className="py-2">14 days</td>
                                        <td className="py-2 font-mono">2<sup>(−5/14)</sup> ≈ 0.787</td>
                                    </tr>
                                    <tr>
                                        <td className="py-2 font-mono text-electric-bright">personal</td>
                                        <td className="py-2">60 days</td>
                                        <td className="py-2 font-mono">2<sup>(−5/60)</sup> ≈ 0.943</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        <p className="text-slate-300">
                            Decay is applied as a <strong className="text-white">constant per-pass factor</strong> (not a cumulative formula):
                        </p>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 mb-3">
                            <p><span className="text-faint">decay_factor</span> = 2<sup>(−fast_decay / half_life)</sup> = 2<sup>(−5/30)</sup> ≈ 0.891 <span className="text-faint">per pass</span></p>
                        </div>
                        <p className="text-slate-300">
                            After 30 daily passes: <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">0.891³⁰ = 2<sup>−5</sup> = 1/32</code> — exactly 5× normal decay, <strong className="text-white">no compounding explosion</strong>.
                        </p>
                    </div>
                </section>

                {/* Example */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Example Walkthrough</h2>
                    <p className="text-slate-300 mb-4">Two contributors, Alice and Bob, publish bundles containing overlapping edges.</p>

                    <div className="grid md:grid-cols-2 gap-4 mb-4">
                        <div className="bg-carbon-card border border-carbon-border rounded-xl p-4">
                            <h4 className="text-white font-semibold mb-2 text-sm">Alice's bundle</h4>
                            <pre className="font-mono text-xs text-slate-300 overflow-x-auto">
{`(source="auth/jwt.py",
 target="auth/handlers.py",
 weight=8.0,
 activation_count=40,
 conflicts=0, comparisons=1)`}
                            </pre>
                            <p className="text-electric-bright font-mono text-sm mt-2">Score: 0.743</p>
                        </div>
                        <div className="bg-carbon-card border border-carbon-border rounded-xl p-4">
                            <h4 className="text-white font-semibold mb-2 text-sm">Bob's bundle</h4>
                            <pre className="font-mono text-xs text-slate-300 overflow-x-auto">
{`(source="auth/jwt.py",
 target="auth/handlers.py",
 weight=2.0,
 activation_count=3,
 conflicts=1, comparisons=2)`}
                            </pre>
                            <p className="text-electric-bright font-mono text-sm mt-2">Score: 0.387</p>
                        </div>
                    </div>

                    <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 space-y-1 mb-4">
                        <p><span className="text-faint">Difference:</span> 0.743 − 0.387 = 0.356 (&gt; 0.05, no contest)</p>
                        <p><span className="text-faint">Winner:</span> Alice's edge (score 0.743)</p>
                        <p><span className="text-faint">Result:</span> Bob's edge is excluded from the <span className="text-electric-bright">shared</span> namespace</p>
                    </div>
                </section>

                {/* Properties */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Properties</h2>
                    <div className="space-y-6 text-slate-300 leading-relaxed">
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">Convergence</h3>
                            <p>Conflict resolution excludes the loser from the <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">shared</code> namespace — the winner survives, the loser is dropped. This forces the graph toward consensus: each conflict eliminates one conflicting assertion, monotonically reducing the set of competing edges.</p>
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">Eventual Consistency</h3>
                            <p>Bundle import is idempotent (tracked by content hash in <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">meta.team_bundle_imported_hash</code>). Given the same set of bundles, all replicas converge to the same state.</p>
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">Complexity</h3>
                            <ul className="list-disc list-inside space-y-1 ml-4">
                                <li><strong className="text-white">Scoring:</strong> O(|bundle|) — single pass</li>
                                <li><strong className="text-white">Conflict detection:</strong> O(|A| + |B|) — dict-indexed</li>
                                <li><strong className="text-white">Decay application:</strong> O(|stale|) — one UPDATE per stale edge</li>
                            </ul>
                        </div>
                    </div>
                </section>

                {/* Reference Implementation */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Reference Implementation</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6">
                        <ul className="space-y-3 text-sm text-slate-300">
                            <li><strong className="text-white">Language:</strong> Python 3.10+ (stdlib-only)</li>
                            <li><strong className="text-white">Repo:</strong> <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">{GITHUB_URL}</a></li>
                            <li><strong className="text-white">Commit:</strong> <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded">{POST_COMMIT}</code> (2026-07-22)</li>
                            <li>
                                <strong className="text-white">Files:</strong>
                                <ul className="list-disc list-inside ml-4 mt-2 space-y-1 font-mono text-xs">
                                    <li>neuralmind/contribution_scoring.py</li>
                                    <li>neuralmind/merge_semantics.py</li>
                                    <li>neuralmind/team_staleness.py</li>
                                </ul>
                            </li>
                        </ul>
                    </div>
                </section>

                {/* Prior Art */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Prior Art Statement</h2>
                    <p className="text-slate-300 leading-relaxed mb-4">
                        To the best of our knowledge, the specific combination of: (1) per-edge composite quality scoring (reinforcement × recency − conflict penalty), (2) loser-exclusion conflict resolution, (3) constant per-pass staleness decay (avoiding compounding explosion), and (4) integration with git-committed bundle propagation — has not been previously published in the context of local-first code intelligence systems.
                    </p>
                    <p className="text-slate-300 leading-relaxed">
                        Related work includes Hebbian learning (Hebb, 1949), gossip protocols (Demers et al., 1987), federated learning (McMahan et al., 2017), and Wikidata (Vrandečić, 2013).
                    </p>
                </section>

                {/* Footer */}
                <footer className="mt-12 pt-8 border-t border-carbon-border text-center">
                    <p className="text-faint text-sm mb-2">
                        This publication establishes prior art for the techniques described herein.
                    </p>
                    <a
                        href={`${GITHUB_URL}/blob/${POST_COMMIT}/docs/publications/defensive-quality-weighted-merge.md`}
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
