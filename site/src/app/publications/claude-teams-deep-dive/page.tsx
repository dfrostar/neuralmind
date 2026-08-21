import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';

const GITHUB_URL = 'https://github.com/dfrostar/neuralmind';
const POST_COMMIT = '3fe5a61';

export const metadata = {
    title: 'NeuralMind + Claude Teams: Procedures, Token Measurement, and Amnesia Prevention — NeuralMind',
    description: 'Deep-dive research report: how to use NeuralMind with Claude Code teams, measure token reduction, and eliminate agent amnesia via committed team memory bundles. Verified against the live codebase.',
    keywords: [
        'Claude Code team memory',
        'token reduction',
        'agent amnesia',
        'team memory bundle',
        'NeuralMind Claude',
        'MCP server',
        'Claude Code hooks',
        'synapse layer',
        'local-first',
        'NeuralMind',
    ],
    authors: [{ name: 'Darren Frost' }],
    creator: 'Darren Frost',
    publisher: 'NeuralMind',
    metadataBase: new URL('https://neuralmind.uk'),
    alternates: {
        canonical: '/publications/claude-teams-deep-dive',
    },
    openGraph: {
        title: 'NeuralMind + Claude Teams: Procedures, Token Measurement, and Amnesia Prevention',
        description: 'Deep-dive research report verified against the live codebase. How to use NeuralMind with Claude Code teams, measure token reduction, and eliminate agent amnesia.',
        url: 'https://neuralmind.uk/publications/claude-teams-deep-dive',
        siteName: 'NeuralMind',
        locale: 'en_US',
        type: 'article',
        publishedTime: '2026-07-26',
        modifiedTime: '2026-07-26',
        authors: ['Darren Frost'],
        tags: ['Claude Code', 'team memory', 'token reduction', 'agent amnesia', 'NeuralMind'],
    },
    twitter: {
        card: 'summary_large_image',
        title: 'NeuralMind + Claude Teams: Procedures, Token Measurement, and Amnesia Prevention',
        description: 'Deep-dive research report verified against the live codebase.',
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
                            headline: 'NeuralMind + Claude Teams: Procedures, Token Measurement, and Amnesia Prevention',
                            description: 'Deep-dive research report: how to use NeuralMind with Claude Code teams, measure token reduction, and eliminate agent amnesia via committed team memory bundles.',
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
                            datePublished: '2026-07-26',
                            dateModified: '2026-07-26',
                            mainEntityOfPage: {
                                '@type': 'WebPage',
                                '@id': 'https://neuralmind.uk/publications/claude-teams-deep-dive',
                            },
                            keywords: ['Claude Code', 'team memory', 'token reduction', 'agent amnesia', 'NeuralMind'],
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
                        <span className="px-3 py-1 rounded-lg bg-electric/10 text-electric text-xs font-mono">Research Report</span>
                        <span className="text-faint text-sm">July 26, 2026</span>
                    </div>
                    <h1 className="font-display text-3xl md:text-4xl font-bold text-white mb-4 leading-tight">
                        NeuralMind + Claude Teams
                    </h1>
                    <p className="text-lg text-slate-300 mb-2">
                        Procedures, Token Measurement, and Amnesia Prevention
                    </p>
                    <p className="text-slate-400 text-sm mb-4">
                        Verified against the live codebase. DeepSeek v4 Pro QA-corrected.
                    </p>
                    <div className="flex items-center gap-4 text-sm text-slate-400">
                        <span>Darren Frost (dfrostar)</span>
                        <span>•</span>
                        <a
                            href={`${GITHUB_URL}/blob/${POST_COMMIT}/docs/research/neuralmind-claude-teams-deep-dive-corrected.md`}
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
                            NeuralMind is a persistent memory layer that turns Claude (a stateless cortex) into an agent with long-term memory. This report provides a complete, citation-heavy reference for using NeuralMind with Claude Code teams: one-time setup, team memory publish/inherit workflows, daily usage patterns, token measurement at every layer, and the five mechanisms that eliminate agent amnesia. All claims are verified against the live codebase at commit {POST_COMMIT}. A DeepSeek v4 Pro QA sweep corrected multiple refuted and aspirational claims from the original draft — the corrections are flagged inline.
                        </p>
                    </div>
                </section>

                {/* Architecture */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Architecture</h2>
                    <div className="space-y-4 text-slate-300 leading-relaxed">
                        <p>
                            <strong className="text-white">The Two-Brain Model:</strong> Claude is the cortex (stateless reasoning over a working-memory window). NeuralMind is the hippocampus + associative cortex (persistent weighted graph of code nodes that learns by Hebbian co-activation, decays unused edges, and runs spreading activation for recall).
                        </p>
                        <p>
                            <strong className="text-white">Communication channels:</strong> MCP tools (15 tools, any agent), Claude Code lifecycle hooks (SessionStart, UserPromptSubmit, PreCompact, PostToolUse), and the file activity watcher (always-on, per-project).
                        </p>
                    </div>
                </section>

                {/* Procedures */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Procedures</h2>

                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">1. One-Time Setup (per repo)</h3>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 mb-3">
                            <p>pip install neuralmind</p>
                            <p>cd /path/to/your-project</p>
                            <p>neuralmind build .             # builds knowledge graph + vector index (1-3 min)</p>
                            <p>neuralmind install-hooks .     # registers PostToolUse + SessionStart + PreCompact hooks</p>
                            <p>neuralmind init-hook .         # auto-rebuild on every git commit</p>
                            <p>neuralmind watch . &           # always-on file watcher — the "brain" that learns</p>
                        </div>
                    </div>

                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">2. Team Memory Workflow (publish → inherit)</h3>
                        <p className="text-slate-300 mb-3">
                            <strong className="text-white">To publish</strong> (any team member, after the watcher has learned):
                        </p>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 mb-3">
                            <p>neuralmind memory publish .    # writes .neuralmind-team-memory.json at repo root</p>
                            <p>git add .neuralmind-team-memory.json && git commit -m "nm: publish team memory"</p>
                        </div>
                        <p className="text-slate-300 mb-3">
                            This exports the union of <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">personal</code> + <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">shared</code> namespaces (MAX-merged per-field) into a provenance-stamped bundle at the repo root. Capped at 5,000 strongest associations.
                        </p>
                        <p className="text-slate-300 mb-3">
                            <strong className="text-white">To inherit</strong> (automatically, zero manual steps):
                        </p>
                        <ul className="list-disc list-inside space-y-2 text-slate-300 ml-4 mb-4">
                            <li><strong className="text-white">Claude Code:</strong> SessionStart hook fires <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">maybe_import_team_memory()</code> — merges committed bundle into <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">shared</code> once per content hash.</li>
                            <li><strong className="text-white">Generic agents:</strong> <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">neuralmind build</code> triggers the same import seam.</li>
                            <li><strong className="text-white">Safety:</strong> Import only ever writes <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">shared</code>; MAX-merge can only raise weights; per-namespace decay erodes stale edges.</li>
                        </ul>
                    </div>

                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">3. Daily Claude Code Workflow</h3>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 mb-3">
                            <p>claude&gt; neuralmind_wakeup(project_path=".")                # ~400 tokens instead of 50K</p>
                            <p>claude&gt; neuralmind_query(project_path=".", question="...")  # ~800-1100 tokens</p>
                            <p>claude&gt; neuralmind_skeleton(project_path=".", file_path="...") # ~88% cheaper than Read</p>
                            <p>claude&gt; neuralmind_review(project_path=".")              # catch co-breaks</p>
                            <p>claude&gt; neuralmind_next_likely(project_path=".", from_node="...") # predict next file</p>
                        </div>
                    </div>
                </section>

                {/* Token Measurement */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Token Measurement</h2>

                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">Measurement Stack</h3>
                        <div className="bg-carbon-card border border-carbon-border rounded-xl p-4 mb-4">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-carbon-border">
                                        <th className="text-left py-2 text-slate-400 font-medium">Layer</th>
                                        <th className="text-left py-2 text-slate-400 font-medium">Content</th>
                                        <th className="text-left py-2 text-slate-400 font-medium">Budget</th>
                                    </tr>
                                </thead>
                                <tbody className="text-slate-300">
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2 font-mono text-electric-bright">L0 Identity</td>
                                        <td className="py-2">Project name, description, key facts</td>
                                        <td className="py-2 font-mono">~150 tok</td>
                                    </tr>
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2 font-mono text-electric-bright">L1 Summary</td>
                                        <td className="py-2">High-level architecture, main components</td>
                                        <td className="py-2 font-mono">~600 tok</td>
                                    </tr>
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2 font-mono text-electric-bright">L2 On-Demand</td>
                                        <td className="py-2">Specific communities/modules as needed</td>
                                        <td className="py-2 font-mono">~800 tok</td>
                                    </tr>
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2 font-mono text-electric-bright">L3 Search</td>
                                        <td className="py-2">Semantic search hits</td>
                                        <td className="py-2 font-mono">~1000 tok</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        <p className="text-slate-300 text-sm">
                            <strong className="text-white">Total wakeup:</strong> ~600 tok. <strong className="text-white">Per-query:</strong> ~500-1000 tok. <strong className="text-white">Vs full codebase:</strong> 50K+ tok loaded naively.
                        </p>
                    </div>

                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">Benchmark Commands</h3>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-sm text-slate-300 mb-3">
                            <p>neuralmind benchmark . --json          # wakeup, avg query, avg reduction</p>
                            <p>neuralmind benchmark . --quality       # MRR, answerability, recall@k</p>
                            <p>neuralmind probe . --sample-size 100   # self-probe on YOUR code</p>
                            <p>neuralmind savings . --cost --model claude-opus-4-8 --queries-per-day 100</p>
                        </div>
                    </div>

                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">Consumption-Side Compression</h3>
                        <div className="bg-carbon-card border border-carbon-border rounded-xl p-4 mb-4">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-carbon-border">
                                        <th className="text-left py-2 text-slate-400 font-medium">Tool</th>
                                        <th className="text-left py-2 text-slate-400 font-medium">Typical reduction</th>
                                        <th className="text-left py-2 text-slate-400 font-medium">Mechanism</th>
                                    </tr>
                                </thead>
                                <tbody className="text-slate-300">
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2 font-mono text-electric-bright">Read</td>
                                        <td className="py-2">Up to ~88%</td>
                                        <td className="py-2">File → skeleton (functions + rationales + call graph)</td>
                                    </tr>
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2 font-mono text-electric-bright">Bash</td>
                                        <td className="py-2">Up to ~91%</td>
                                        <td className="py-2">Keep errors + tail, drop middle</td>
                                    </tr>
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2 font-mono text-electric-bright">Grep</td>
                                        <td className="py-2">Capped</td>
                                        <td className="py-2">Max 25 matches, "N more hidden" pointer</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        <p className="text-slate-300 text-sm">
                            <strong className="text-white">Note:</strong> The 88%/91% figures are documentation claims, not measured benchmarks. Actual compression depends on file size (Read only fires on files ≥1500 chars) and content type. Combined retrieval + consumption 5-10× is a documentation claim without measured evidence.
                        </p>
                    </div>
                </section>

                {/* Amnesia Prevention */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Amnesia Prevention — Five Mechanisms</h2>

                    <div className="space-y-6 text-slate-300 leading-relaxed">
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">1. Persistent Synapse Store (synapses.py, SQLite)</h3>
                            <p>Learns weighted associations from how an agent actually uses the codebase. Time-based half-life decay: <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">weight × exp(−λ × age_days)</code>. Per-namespace half-lives: personal=30d, shared=60d, ephemeral=1d. Structural synapse seeding (v0.46.0) converts 1,903 code graph edges into synapse edges on every build.</p>
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">2. SessionStart Auto-Import (hooks.py:313-362)</h3>
                            <p>Fires on every new session: decay tick → team memory import → autotune (opt-in) → ephemeral cleanup → synapse export to auto-memory.</p>
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">3. Committed Team Memory Bundle</h3>
                            <p><code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">.neuralmind-team-memory.json</code> at repo root travels with <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">git clone</code>. New hire's agent inherits on first session — zero manual steps. MAX-merge only raises weights; per-namespace decay erodes stale edges.</p>
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">4. Synapse Memory Export (synapse_memory.py)</h3>
                            <p>Renders top pairs, hub nodes, and directional transitions as markdown. Written to both project-local <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded text-sm">.neuralmind/SYNAPSE_MEMORY.md</code> and Claude Code's auto-memory directory.</p>
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-white mb-2">5. Spreading Activation Injection (hooks.py:364-385)</h3>
                            <p>UserPromptSubmit hook runs spreading activation over the synapse graph for each prompt. Injects the top-8 most-associated nodes as additional context before Claude sees the prompt.</p>
                        </div>
                    </div>
                </section>

                {/* Self-Improvement Loop */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Self-Improvement Loop</h2>
                    <div className="space-y-4 text-slate-300 leading-relaxed">
                        <p>The Product Ops vision: NeuralMind as a self-improving / self-evolving product — autonomous signal → diagnose → experiment → promote/rollback loop.</p>
                        <p><strong className="text-white">What's wired (Wave 1-4):</strong></p>
                        <ul className="list-disc list-inside space-y-2 ml-4">
                            <li><strong className="text-white">Wave 2 (C1/A1/A2/B2/B3/G2):</strong> 6 modules shipped, 88 tests. All stdlib-only top-level, gated by env vars, fail-open.</li>
                            <li><strong className="text-white">Wave 3 (C2/C3/A3/A4):</strong> Fitness function, trace store, tuner (single-variable in trace fallback; live eval is multi-objective but unmeasured). A3 learned decay <strong className="text-white">is now wired</strong> (was dead code, patched).</li>
                            <li><strong className="text-white">Wave 4 (E1/E2/E3/E4+G4):</strong> Contribution scoring, merge semantics, peer review (threshold 0.70, auto_promote fires), staleness (constant-per-pass after C2 fix). G4 incremental extraction built + tested but not wired into build_graph().</li>
                        </ul>
                        <p><strong className="text-white">The gap:</strong> The fitness function is effectively single-variable in trace fallback mode. Live eval is multi-objective but unmeasured in production. Auto-tune is opt-in and capped at ±1 step per session. The "self-evolving product" is aspirational — the infrastructure is built, the tuning signal is weak in production.</p>
                    </div>
                </section>

                {/* Correction Log */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">DeepSeek QA Correction Log</h2>
                    <p className="text-slate-300 mb-4">This report was corrected on 2026-07-26 after DeepSeek v4 Pro verification against the live codebase. The following claims were based on outdated reference docs that described pre-fix states:</p>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-4 mb-4">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-carbon-border">
                                    <th className="text-left py-2 text-slate-400 font-medium">Original Claim</th>
                                    <th className="text-left py-2 text-slate-400 font-medium">Correction</th>
                                    <th className="text-left py-2 text-slate-400 font-medium">Status</th>
                                </tr>
                            </thead>
                            <tbody className="text-slate-300">
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-2">88%/91% compression (measured)</td>
                                    <td className="py-2">Only in docs, not benchmarked. Actual ratio varies by file size.</td>
                                    <td className="py-2 text-yellow-400">Aspirational</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-2">30-50x reduction (measured)</td>
                                    <td className="py-2">Modeled estimate with 50K default baseline.</td>
                                    <td className="py-2 text-yellow-400">Modeled</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-2">AUTO_PROMOTE_THRESHOLD = 0.75 (dead code)</td>
                                    <td className="py-2">Actual threshold = 0.70. auto_promote fires.</td>
                                    <td className="py-2 text-red-400">Refuted</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-2">"5x acceleration" (total speedup)</td>
                                    <td className="py-2">Parameter is 5.0, cumulative speedup is 16×.</td>
                                    <td className="py-2 text-yellow-400">Overclaim</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-2">learned_decay is dead code</td>
                                    <td className="py-2">Wired into reinforce() at synapses.py:600-607.</td>
                                    <td className="py-2 text-red-400">Refuted</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-2">Denominator bias exists</td>
                                    <td className="py-2">Fixed — uses len(fixture_queries).</td>
                                    <td className="py-2 text-red-400">Refuted</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-2">Fail-open fitness wipe</td>
                                    <td className="py-2">Guarded — doesn't persist 0.0.</td>
                                    <td className="py-2 text-red-400">Refuted</td>
                                </tr>
                                <tr>
                                    <td className="py-2">NaN leak via min()</td>
                                    <td className="py-2">Uses _clamp, all axes safe.</td>
                                    <td className="py-2 text-red-400">Refuted</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </section>

                {/* Reference Implementation */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Reference Implementation</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6">
                        <ul className="space-y-3 text-sm text-slate-300">
                            <li><strong className="text-white">Language:</strong> Python 3.10+ (stdlib-only)</li>
                            <li><strong className="text-white">Repo:</strong> <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">{GITHUB_URL}</a></li>
                            <li><strong className="text-white">Commit:</strong> <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded">{POST_COMMIT}</code> (2026-07-26)</li>
                            <li>
                                <strong className="text-white">Key files:</strong>
                                <ul className="list-disc list-inside ml-4 mt-2 space-y-1 font-mono text-xs">
                                    <li>neuralmind/context_selector.py (993 lines)</li>
                                    <li>neuralmind/synapses.py (1,593 lines)</li>
                                    <li>neuralmind/team_memory.py (366 lines)</li>
                                    <li>neuralmind/hooks.py (544 lines)</li>
                                    <li>neuralmind/mcp_server.py (879 lines)</li>
                                    <li>neuralmind/compressors.py</li>
                                    <li>neuralmind/learned_decay.py (139 lines, now wired)</li>
                                    <li>neuralmind/fitness.py (all 3 axes _clamp-safe)</li>
                                    <li>neuralmind/tuner.py (denominator-safe, incumbent-guarded)</li>
                                </ul>
                            </li>
                        </ul>
                    </div>
                </section>

                {/* Footer */}
                <footer className="mt-12 pt-8 border-t border-carbon-border text-center">
                    <p className="text-faint text-sm mb-2">
                        This report was verified against the live codebase and corrected by DeepSeek v4 Pro QA.
                    </p>
                    <a
                        href={`${GITHUB_URL}/blob/${POST_COMMIT}/docs/research/neuralmind-claude-teams-deep-dive-corrected.md`}
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
