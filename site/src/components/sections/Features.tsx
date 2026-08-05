'use client';

const featureList = [
    {
        icon: '⚡',
        title: 'Sub-Second Retrieval',
        desc: 'TurboVec backend: 0.81s per query on a 1,486-node repo. ChromaDB-free, 8× smaller index vectors (4-bit quantized).',
        badge: 'TurboVec',
    },
    {
        icon: '🧬',
        title: 'Hebbian Synapse Layer',
        desc: 'Associations strengthen when you use them together — like a real hippocampus. Budget-neutral, no cost until it activates.',
        badge: 'Budget-neutral',
    },
    {
        icon: '🔄',
        title: 'Progressive L0–L3 Disclosure',
        desc: 'Retrieves exact bytes needed. Never pastes the whole repo. 65.6× compression measured on a 241-node production codebase.',
        badge: '63.6×',
    },
    {
        icon: '📊',
        title: 'Team Dashboard',
        desc: 'Read-only web UI: synapse memory, ingestion status, savings, latency trends, community distribution, recent queries.',
        badge: 'New',
    },
    {
        icon: '🔬',
        title: 'Self-Documenting Code',
        desc: 'DocEvolver finds undocumented methods, generates JSDoc variants, evolves them against retrieval fitness. Winning variants patched back into source.',
        badge: 'Evolution',
    },
    {
        icon: '🧠',
        title: 'Business-Context Synapse Seeding',
        desc: 'seed_from_documents() builds deterministic, LLM-free associations between business documents (decisions, SOPs, meeting notes) and your code graph. Adjacency-matched compounds, title-reference cross-links.',
        badge: 'N-13',
    },
    {
        icon: '🌐',
        title: 'MCP Server',
        desc: 'First-class MCP integration. Works with Claude Code, Cursor, Cline, Continue, and any MCP-compatible agent.',
        badge: 'Universal',
    },
    {
        icon: '🎯',
        title: 'Ten-Language Code Graph',
        desc: 'tree-sitter indexes Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby, and PHP out of the box.',
        badge: '10 langs',
    },
    {
        icon: '🗑️',
        title: 'Tool Output Recovery',
        desc: 'Caches dropped tool output from context windows. When your agent forgets, neuralmind remembers.',
        badge: 'Auto-recover',
    },
    {
        icon: '🆓',
        title: 'Free Tier — Auto-Provisioned',
        desc: '`pip install neuralmind && neuralmind wakeup .` writes the license on first run. Zero signup wall. Default tier is "free", identity auto-issued.',
        badge: 'v1.7.0',
    },
    {
        icon: '🔒',
        title: '100% Local Engine',
        desc: 'NeuralMind makes zero network calls of its own — only the minimal relevant slice ever reaches your AI tool, never your whole codebase. No telemetry.',
        badge: 'Secure',
    },
    {
        icon: '🚀',
        title: 'One-Command Project Init',
        desc: '`neuralmind init` auto-detects project structure, installs hooks, builds the index — all at once. Your project is ready in seconds.',
        badge: 'v2.0.0',
    },
    {
        icon: '🛡️',
        title: 'Compliance Annotation Engine',
        desc: 'Scans code for `Compliance:` annotations, maps them to CMMC 2.0 / NIST SP 800-53 controls. Ingest CMMC assessment guides, export audit reports, gate CI on annotation health.',
        badge: 'v2.0.0',
    },
    {
        icon: '📤',
        title: 'Audit Export & CI/CD Check',
        desc: '`neuralmind export --audit` produces flat compliance reports (CSV/JSON) for evidence submission. `neuralmind ci-check` gates builds on annotation health.',
        badge: 'v2.0.0',
    },
    {
        icon: '🤖',
        title: 'Compliance Report MCP Tool',
        desc: '`neuralmind_compliance_report` surfaces live compliance stance from any MCP-compatible agent. Ask "are we compliant on access control?" and get an answer grounded in real annotations.',
        badge: 'v2.0.0',
    },
];

export default function Features() {
    return (
        <section id="features" className="relative py-16 md:py-32 px-4 md:px-6">
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-electric/3 rounded-full blur-[200px] -z-10" />

            <div className="max-w-5xl mx-auto">
                <div className="text-center mb-12 md:mb-16">
                    <span className="text-electric text-sm font-semibold tracking-wider uppercase mb-3 block">
                        Capabilities
                    </span>
                    <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
                        Features
                    </h2>
                    <p className="text-slate-400 text-base sm:text-lg md:text-xl max-w-xl mx-auto">
                        Everything persistent memory should be — and nothing it shouldn't.
                    </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-6">
                    {featureList.map((f) => (
                        <div
                            key={f.title}
                            className="glow-card rounded-2xl p-6 md:p-8 group"
                        >
                            <div className="flex items-start justify-between mb-3">
                                <span className="text-3xl">{f.icon}</span>
                                <span className="text-xs font-semibold uppercase tracking-wider text-electric bg-electric/10 px-3 py-1 rounded-full">
                                    {f.badge}
                                </span>
                            </div>
                            <h3 className="font-display text-xl font-bold text-white mb-2">{f.title}</h3>
                            <p className="text-slate-400 text-sm leading-relaxed">{f.desc}</p>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
