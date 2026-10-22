import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';

const GITHUB_URL = 'https://github.com/dfrostar/neuralmind';
const POST_COMMIT = '3fe5a61';

export const metadata = {
    title: 'NeuralMind + OpenAI Codex: MCP Setup & Token Savings Guide',
    description: 'Set up NeuralMind as an MCP server for OpenAI Codex: install it, register with any MCP client, measure L0–L3 token budgets and estimate their cost.',
    keywords: [
        'OpenAI Codex',
        'Codex CLI',
        'agent memory',
        'token reduction',
        'MCP server',
        'NeuralMind Codex',
        'local-first',
        'self-improving',
        'PostToolUse hooks',
        'NeuralMind',
    ],
    authors: [{ name: 'Darren Frost' }],
    creator: 'Darren Frost',
    publisher: 'NeuralMind',
    metadataBase: new URL('https://neuralmind.uk'),
    alternates: {
        canonical: '/publications/codex-setup',
    },
    openGraph: {
        title: 'How to Use NeuralMind with OpenAI Codex — Setup, Token Measurement, Savings',
        description: 'Step-by-step guide verified against the live codebase: install NeuralMind, register the MCP server with Codex, measure token budgets, and verify dollar savings.',
        url: 'https://neuralmind.uk/publications/codex-setup',
        siteName: 'NeuralMind',
        locale: 'en_US',
        type: 'article',
        publishedTime: '2026-07-26',
        modifiedTime: '2026-07-26',
        authors: ['Darren Frost'],
        tags: ['OpenAI Codex', 'Codex CLI', 'agent memory', 'token reduction', 'NeuralMind'],
        images: [
            {
                url: '/social-preview.png',
                width: 1200,
                height: 630,
                alt: 'NeuralMind — Code Memory for AI Coding Agents',
            },
        ],
    },
    twitter: {
        card: 'summary_large_image',
        title: 'How to Use NeuralMind with OpenAI Codex — Setup, Token Measurement, Savings',
        description: 'Step-by-step guide verified against the live codebase.',
        images: ['https://neuralmind.uk/social-preview.png'],
    },
    robots: {
        index: true,
        follow: true,
        googleBot: { index: true, follow: true },
    },
};

const MCP_SNIPPET = '{"mcpServers": {"neuralmind": {"command": "neuralmind-mcp", "args": ["."]}}}';

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
                            headline: 'How to Use NeuralMind with OpenAI Codex: Setup, Token Measurement, and Savings',
                            description: 'Step-by-step guide: install NeuralMind, register the MCP server with Codex (any MCP client), measure L0-L3 token budgets, run the self-improvement loop, and estimate what those tokens would cost.',
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
                                '@id': 'https://neuralmind.uk/publications/codex-setup',
                            },
                            keywords: ['OpenAI Codex', 'Codex CLI', 'agent memory', 'token reduction', 'NeuralMind'],
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
                        <span className="px-3 py-1 rounded-control bg-electric/10 text-electric text-xs font-mono">How-To Guide</span>
                        <span className="text-faint text-sm">July 26, 2026</span>
                    </div>
                    <h1 className="font-display text-3xl md:text-4xl font-bold text-white mb-4 leading-tight">
                        How to Use NeuralMind with OpenAI Codex
                    </h1>
                    <p className="text-lg text-body mb-2">
                        Setup, Token Measurement, and Savings
                    </p>
                    <p className="text-muted text-sm mb-4">
                        Verified against the live codebase. DeepSeek v4 Pro QA-corrected.
                    </p>
                    <div className="flex items-center gap-4 text-sm text-muted">
                        <span>Darren Frost (dfrostar)</span>
                    </div>
                </header>

                {/* Abstract */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Abstract</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-card p-6">
                        <p className="text-body leading-relaxed">
                            NeuralMind gives any AI coding agent a persistent memory layer — a learned, weighted graph of your codebase that cuts the tokens a code question costs at the retrieval stage: 51–242× fewer than pasting every source file on the public benchmark (v4.12.0), and 12–50× in field reports measured by <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded-control text-sm">neuralmind benchmark</code> before v4.5.0 against its fixed 50K-token estimate. This guide walks through using NeuralMind with OpenAI Codex CLI: one-time install, registering the MCP server (works with any MCP-compatible client, including Codex), daily wakeup/query commands, per-layer token measurement, the self-improvement loop, and honest scoping of what&apos;s measured vs. modeled. All claims are verified against the live codebase at commit {POST_COMMIT}. A DeepSeek v4 Pro QA sweep corrected several overclaims from the original draft — the corrections are flagged inline.
                        </p>
                    </div>
                </section>

                {/* Architecture */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Architecture</h2>
                    <div className="space-y-4 text-body leading-relaxed">
                        <p>
                            <strong className="text-white">The Two-Brain Model:</strong> Codex is the cortex (stateless reasoning over a working-memory window). NeuralMind is the hippocampus + associative cortex (persistent weighted graph of code nodes that learns by Hebbian co-activation, decays unused edges, and runs spreading activation for recall).
                        </p>
                        <p>
                            <strong className="text-white">Communication channels:</strong> MCP tools (19 tools, any agent), lifecycle hooks (SessionStart, UserPromptSubmit, PreCompact, PostToolUse), and the file activity watcher (always-on, per-project).
                        </p>
                        <p>
                            <strong className="text-white">The Codex relationship:</strong> Codex is MCP-compatible. NeuralMind ships an MCP server that exposes <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded-control text-sm">neuralmind_wakeup</code>, <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded-control text-sm">neuralmind_query</code>, and 17 other tools. Codex gains NeuralMind&apos;s retrieval and synapse capabilities by registering that MCP server — no Codex-specific code required.
                        </p>
                    </div>
                </section>

                {/* Procedures */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Procedures</h2>

                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">1. One-Time Setup (per repo)</h3>
                        <div className="bg-carbon rounded-control p-4 font-mono text-sm text-body mb-3">
                            <p>pip install neuralmind</p>
                            <p>cd /path/to/your-project</p>
                            <p>neuralmind build .                    # builds knowledge graph + vector index</p>
                            <p>neuralmind install-mcp --print       # print the MCP config snippet for Codex (or any MCP client)</p>
                        </div>
                        <p className="text-body text-sm mb-3">
                            <strong className="text-white">For Codex specifically:</strong> Codex isn&apos;t in the auto-detect list (Claude Code, Cursor, Cline, Claude Desktop, VS Code). Use <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded-control text-sm">neuralmind install-mcp --print</code> to emit the JSON snippet, then paste it into Codex&apos;s MCP server config. Any MCP-compatible client works the same way — the server is the same, only the config file differs.
                        </p>
                    </div>

                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">2. Daily Codex Workflow</h3>
                        <p className="text-body mb-3">
                            Once the MCP server is registered, Codex gains NeuralMind&apos;s tools. Start every session with a wakeup, then query as needed:
                        </p>
                        <div className="bg-carbon rounded-control p-4 font-mono text-sm text-body mb-3">
                            <p>codex&gt; neuralmind_wakeup(project_path=&quot;.&quot;)                # compact project overview, once per session</p>
                            <p>codex&gt; neuralmind_query(project_path=&quot;.&quot;, question=&quot;...&quot;)  # 670–961 mean tokens per question (public benchmark, v4.12.0)</p>
                            <p>codex&gt; neuralmind_skeleton(project_path=&quot;.&quot;, file_path=&quot;...&quot;) # file → skeleton (functions + rationales)</p>
                            <p>codex&gt; neuralmind_review(project_path=&quot;.&quot;, changed_files=[...]) # catch co-breaks</p>
                            <p>codex&gt; neuralmind_next_likely(project_path=&quot;.&quot;, from_node=&quot;...&quot;) # predict next file</p>
                        </div>
                        <p className="text-body text-sm">
                            <strong className="text-white">What Codex sees:</strong> Structured project context (identity, architecture, relevant modules, search hits) instead of raw file dumps. The wakeup loads a compact overview once per session (455 tokens in one field report; neuralmind benchmark prints yours); a query averaged 670–961 tokens per repo on the public benchmark at v4.12.0.
                        </p>
                    </div>

                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">3. Registering with Any MCP Client</h3>
                        <div className="bg-carbon rounded-control p-4 font-mono text-sm text-body mb-3">
                            <p>neuralmind install-mcp --all            # auto-detect Claude Code / Cursor / Cline / Claude Desktop / VS Code</p>
                            <p>neuralmind install-mcp --client cursor # target a specific client</p>
                            <p>neuralmind install-mcp --print          # emit JSON for any MCP client (Codex, Windsurf, custom)</p>
                        </div>
                        <p className="text-body text-sm">
                            <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded-control text-sm">--all</code> non-destructively merges a NeuralMind entry into each detected client&apos;s config. <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded-control text-sm">--print</code> is the escape hatch: it outputs the <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded-control text-sm">{MCP_SNIPPET}</code> snippet to paste into any MCP-compatible tool&apos;s config file.
                        </p>
                    </div>
                </section>

                {/* Token Measurement */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Token Measurement (L0-L3 Budgets)</h2>

                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">Measurement Stack</h3>
                        <div className="bg-carbon-card border border-carbon-border rounded-card p-4 mb-4">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-carbon-border">
                                        <th className="text-left py-2 text-muted font-medium">Layer</th>
                                        <th className="text-left py-2 text-muted font-medium">Content</th>
                                        <th className="text-left py-2 text-muted font-medium">Budget</th>
                                    </tr>
                                </thead>
                                <tbody className="text-body">
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
                        <p className="text-body text-sm">
                            <strong className="text-white">Wakeup:</strong> L0 + L1, capped by the budgets above, once per session. <strong className="text-white">Per-query:</strong> 670–961 mean tokens per repo on the public benchmark (v4.12.0). <strong className="text-white">Vs pasting every source file:</strong> 41,729–232,483 tokens on the same four repos.
                        </p>
                    </div>

                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">Tool-output compression (correction)</h3>
                        <p className="text-body mb-3">
                            Earlier versions of this guide described PostToolUse hooks that compress Read, Bash and Grep output, with reductions of up to ~88% and ~91% that were never measured. When the hooks were finally benchmarked against Claude Code’s documented hook protocol, they turned out not to shrink anything: Claude Code adds a hook’s output next to the tool result instead of replacing it, so they added tokens, and the Read hook never received Claude Code’s payload. The hooks no longer inject anything; the{' '}
                            <a href="https://docs.neuralmind.uk/benchmarks/compression.html" className="text-electric hover:text-electric-bright">compression benchmark</a>{' '}
                            has the measurements.
                        </p>
                        <p className="text-body text-sm">
                            The hooks are Claude Code-specific, so Codex never ran them. For Codex, token savings come from the MCP retrieval layer (wakeup/query) alone.
                        </p>
                    </div>

                    <div className="mb-8">
                        <h3 className="text-lg font-semibold text-white mb-3">Benchmark + Savings Commands</h3>
                        <div className="bg-carbon rounded-control p-4 font-mono text-sm text-body mb-3">
                            <p>neuralmind benchmark . --json          # wakeup, avg query, avg reduction</p>
                            <p>neuralmind benchmark . --quality       # MRR, answerability, recall@k</p>
                            <p>neuralmind probe . --sample-size 100   # self-probe on YOUR code</p>
                            <p>neuralmind savings . --cost --model claude-opus-4-8 --queries-per-day 100</p>
                        </div>
                        <p className="text-body text-sm">
                            <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded-control text-sm">neuralmind savings --cost</code> reads your local query event log and prints estimated dollar savings. The &quot;without NeuralMind&quot; cost is modeled from a fixed 50,000-token-per-query baseline; the &quot;with NeuralMind&quot; cost is measured from logged tokens.
                        </p>
                    </div>
                </section>

                {/* Self-Improvement Loop */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Self-Improvement Loop</h2>
                    <div className="space-y-4 text-body leading-relaxed">
                        <p>NeuralMind includes infrastructure for a self-improving / self-evolving product — autonomous signal → diagnose → experiment → promote/rollback loop.</p>
                        <p><strong className="text-white">What&apos;s wired:</strong></p>
                        <ul className="list-disc list-inside space-y-2 ml-4">
                            <li><strong className="text-white">Synapse learning (always-on):</strong> The file activity watcher records co-activations between code nodes. Hebbian reinforcement strengthens edges the agent actually traverses; half-life decay erodes unused edges (personal=30d, shared=60d, ephemeral=1d).</li>
                            <li><strong className="text-white">Fitness function:</strong> Multi-objective (MRR, answerability, recall@k) fitness scoring gated by a threshold. Auto-promote fires when fitness exceeds the threshold.</li>
                            <li><strong className="text-white">Tuner:</strong> Single-variable in trace fallback mode; live eval is multi-objective. Auto-tune is opt-in and capped at ±1 step per session.</li>
                            <li><strong className="text-white">Learned decay:</strong> Wired into <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded-control text-sm">reinforce()</code> — adjusts reinforcement magnitude based on how recently an edge was last traversed.</li>
                        </ul>
                        <p><strong className="text-white">The gap:</strong> The fitness function is effectively single-variable in trace fallback mode. Live eval is multi-objective but unmeasured in production. The &quot;self-evolving product&quot; is aspirational — the infrastructure is built, the tuning signal is weak in production.</p>
                    </div>
                </section>

                {/* Honest Scope */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Honest Scope — What&apos;s Measured vs. Modeled</h2>
                    <div className="space-y-4 text-body leading-relaxed">
                        <div className="bg-carbon-card border border-carbon-border rounded-card p-4">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-carbon-border">
                                        <th className="text-left py-2 text-muted font-medium">Claim</th>
                                        <th className="text-left py-2 text-muted font-medium">Basis</th>
                                        <th className="text-left py-2 text-muted font-medium">Confidence</th>
                                    </tr>
                                </thead>
                                <tbody className="text-body">
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2">51–242× fewer tokens than pasting every source file</td>
                                        <td className="py-2">Public benchmark, 40 pre-registered queries on 4 repos, v4.12.0 (python -m evals.public.run); retrieval stage only</td>
                                        <td className="py-2 text-proton">Measured</td>
                                    </tr>
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2">12–50× token reduction</td>
                                        <td className="py-2">Field reports measured by neuralmind benchmark before v4.5.0, against its fixed 50K-token estimate rather than a measured baseline; retrieval stage only</td>
                                        <td className="py-2 text-warn">Modeled</td>
                                    </tr>
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2">Wake-up tokens, once per session</td>
                                        <td className="py-2">L0+L1 in context_selector.py; 455 in one field report, printed by neuralmind benchmark for your repo</td>
                                        <td className="py-2 text-proton">Measured</td>
                                    </tr>
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2">670–961 mean tokens per question</td>
                                        <td className="py-2">Public benchmark, per repo, v4.12.0; ~830 on the 150-question retrieval eval; varies by graph size</td>
                                        <td className="py-2 text-proton">Measured</td>
                                    </tr>
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2">Read/Bash tool-output compression</td>
                                        <td className="py-2">Benchmarked: as shipped, the hooks added tokens instead of saving them; switched off</td>
                                        <td className="py-2 text-danger">Refuted</td>
                                    </tr>
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2">Dollar savings ($/day, $/mo)</td>
                                        <td className="py-2">With-NM measured from logged tokens; without-NM estimated</td>
                                        <td className="py-2 text-warn">Mixed</td>
                                    </tr>
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2">MRR / answerability / recall@k</td>
                                        <td className="py-2">Benchmark suite (neuralmind benchmark --quality)</td>
                                        <td className="py-2 text-proton">Measured</td>
                                    </tr>
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2">End-to-end cost per task</td>
                                        <td className="py-2">
                                            A pre-registered 20-task pilot, Claude Code with and without NeuralMind:{' '}
                                            <a href="/benchmark/#task-outcomes" className="text-electric hover:text-electric-bright">no difference</a>
                                        </td>
                                        <td className="py-2 text-danger">Not supported</td>
                                    </tr>
                                    <tr>
                                        <td className="py-2">Self-improving product</td>
                                        <td className="py-2">Infrastructure built; tuning signal weak in production</td>
                                        <td className="py-2 text-warn">Aspirational</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        <p>
                            <strong className="text-white">Bottom line:</strong> The savings are at the retrieval stage. On the public benchmark NeuralMind&apos;s context averaged 670–961 tokens per question, per repo, against 41,729–232,483 to paste every source file (51–242×, v4.12.0); the older 12–50× range comes from field reports measured by <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded-control text-sm">neuralmind benchmark</code> before v4.5.0 against its fixed 50K-token estimate. Total end-to-end reduction varies by workflow (how many Read/Bash calls, query volume, codebase shape). Codex and Claude Code users get the same retrieval-stage reduction: the Claude Code hooks add no compression on top (see the correction above). Whether it lowers what a task costs was measured once: a 20-task pilot found <a href="/benchmark/#task-outcomes" className="text-electric hover:text-electric-bright">no difference</a>.
                        </p>
                    </div>
                </section>

                {/* Tiers */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Tiers</h2>
                    <div className="space-y-4 text-body leading-relaxed">
                        <div className="bg-carbon-card border border-carbon-border rounded-card p-4">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-carbon-border">
                                        <th className="text-left py-2 text-muted font-medium">Tier</th>
                                        <th className="text-left py-2 text-muted font-medium">Price</th>
                                        <th className="text-left py-2 text-muted font-medium">Includes</th>
                                    </tr>
                                </thead>
                                <tbody className="text-body">
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2 font-semibold text-white">Free</td>
                                        <td className="py-2">$0</td>
                                        <td className="py-2">Auto-provisioned on first <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded-control text-sm">neuralmind wakeup .</code> (v1.7.0) — wakeup, query, search, synapses, build, benchmark, savings, review, all MCP tools, 1 seat</td>
                                    </tr>
                                    <tr className="border-b border-carbon-border/50">
                                        <td className="py-2 font-semibold text-white">Team</td>
                                        <td className="py-2">$29/user/mo</td>
                                        <td className="py-2">Governance (per-repo enable/disable, scope, weight threshold), immutable SHA-256 audit log, seat management (5-50 seats), self-hosted deployment, license management</td>
                                    </tr>
                                    <tr>
                                        <td className="py-2 font-semibold text-white">Enterprise</td>
                                        <td className="py-2">Custom</td>
                                        <td className="py-2">51+ seats, per-org assurance, custom contracts — contact hello@neuralmind.uk</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        <p className="text-sm text-muted">
                            <strong className="text-white">Free tier note:</strong> v1.7.0 flipped the default tier from &quot;team&quot; to &quot;free&quot; — on first <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded-control text-sm">neuralmind wakeup .</code>, a license.json is auto-written with no signup wall.
                        </p>
                    </div>
                </section>

                {/* Correction Log */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">DeepSeek QA Correction Log</h2>
                    <p className="text-body mb-4">This guide was corrected on 2026-07-26 after DeepSeek v4 Pro verification against the live codebase. The following claims were based on assumptions that didn&apos;t hold up:</p>
                    <div className="bg-carbon-card border border-carbon-border rounded-card p-4 mb-4">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-carbon-border">
                                    <th className="text-left py-2 text-muted font-medium">Original Claim</th>
                                    <th className="text-left py-2 text-muted font-medium">Correction</th>
                                    <th className="text-left py-2 text-muted font-medium">Status</th>
                                </tr>
                            </thead>
                            <tbody className="text-body">
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-2">&quot;install-mcp --all detects Codex&quot;</td>
                                    <td className="py-2">Codex is not in the auto-detect list (claude-code, cursor, cline, claude-desktop, vscode). Use --print for Codex.</td>
                                    <td className="py-2 text-danger">Refuted</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-2">&quot;PostToolUse hooks fire in Codex&quot;</td>
                                    <td className="py-2">Hooks are Claude Code-specific. Codex only gets the MCP retrieval layer.</td>
                                    <td className="py-2 text-danger">Refuted</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-2">&quot;12-50× total workflow reduction&quot;</td>
                                    <td className="py-2">12–50× is retrieval-stage only, from field reports measured before v4.5.0 against a fixed 50K-token estimate. Total reduction varies by workflow.</td>
                                    <td className="py-2 text-warn">Overclaim</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-2">&quot;88%/91% compression measured&quot;</td>
                                    <td className="py-2">Never measured. Once benchmarked, the hooks turned out to add tokens instead of saving them, and were switched off.</td>
                                    <td className="py-2 text-danger">Refuted</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-2">&quot;~800-1100 tokens per query&quot;</td>
                                    <td className="py-2">Modeled estimate using est_nodes * 2 formula. Actual varies by graph size and query.</td>
                                    <td className="py-2 text-warn">Modeled</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-2">&quot;Dollar savings are fully measured&quot;</td>
                                    <td className="py-2">With-NM is measured; without-NM (and therefore &quot;saved&quot;) is estimated from a 50K baseline.</td>
                                    <td className="py-2 text-warn">Overclaim</td>
                                </tr>
                                <tr>
                                    <td className="py-2">&quot;Self-improving product (in production)&quot;</td>
                                    <td className="py-2">Infrastructure is built; fitness signal is weak in production. Tuning is opt-in, capped.</td>
                                    <td className="py-2 text-warn">Aspirational</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </section>

                {/* Reference Implementation */}
                <section className="mb-10">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Reference Implementation</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-card p-6">
                        <ul className="space-y-3 text-sm text-body">
                            <li><strong className="text-white">Language:</strong> Python 3.10+ (stdlib-only)</li>
                            <li><strong className="text-white">Repo:</strong> <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">{GITHUB_URL}</a></li>
                            <li><strong className="text-white">Commit:</strong> <code className="text-electric-bright bg-carbon px-1.5 py-0.5 rounded-control">{POST_COMMIT}</code> (2026-07-26)</li>
                            <li>
                                <strong className="text-white">Key files:</strong>
                                <ul className="list-disc list-inside ml-4 mt-2 space-y-1 font-mono text-xs">
                                    <li>neuralmind/cli.py (3,364 lines — build, wakeup, query, savings, install-mcp)</li>
                                    <li>neuralmind/mcp_server.py (879 lines — 19 MCP tools)</li>
                                    <li>neuralmind/mcp_install.py (245 lines — client detection + registration)</li>
                                    <li>neuralmind/context_selector.py (993 lines — L0/L1/L2/L3 progressive disclosure)</li>
                                    <li>neuralmind/synapses.py (1,593 lines — Hebbian synapse store)</li>
                                    <li>neuralmind/hooks.py (544 lines — Claude Code hook integration)</li>
                                    <li>neuralmind/compressors.py (310 lines — Read/Bash/Grep compression)</li>
                                    <li>neuralmind/fitness.py (multi-objective fitness)</li>
                                    <li>neuralmind/tuner.py (denominator-safe, incumbent-guarded)</li>
                                </ul>
                            </li>
                        </ul>
                    </div>
                </section>

                {/* Footer */}
                <footer className="mt-12 pt-8 border-t border-carbon-border text-center">
                    <p className="text-faint text-sm mb-2">
                        This guide was verified against the live codebase and corrected by DeepSeek v4 Pro QA.
                    </p>
                </footer>
            </main>
            <Footer />
        </>
    );
}
