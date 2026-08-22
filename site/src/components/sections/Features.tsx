'use client';

import Icon, { type IconName } from '@/components/ui/Icon';
import { withCode } from '@/lib/ticks';

// Copy is unchanged — every figure here is registered in site/claims.json and
// gated by tests/test_site_claims.py. What changed is `icon`: these were
// emoji (⚡🧬🔄📊🔬🧠🌐🎯🗑️🆓🔒🚀🛡️📤🤖), drawn by the reader's operating
// system in full colour at whatever weight it felt like, in the middle of an
// otherwise monochrome page.
const featureList: { icon: IconName; title: string; desc: string; badge: string }[] = [
    {
        icon: 'chip',
        title: 'Local Retrieval, No Model Call',
        desc: 'Recall is a local index lookup, not another round trip to a model. The ChromaDB-free TurboVec backend keeps 4-bit quantized vectors 8–16× smaller with fact recall 0.800 vs 0.744 for float32 — parity gated in CI.',
        badge: 'TurboVec',
    },
    {
        icon: 'synapse',
        title: 'Hebbian Synapse Layer',
        desc: 'Associations strengthen when you use them together — like a real hippocampus. Budget-neutral, no cost until it activates.',
        badge: 'Budget-neutral',
    },
    {
        icon: 'layers',
        title: 'Progressive L0–L3 Disclosure',
        desc: 'Retrieves the exact bytes needed. Never pastes the whole repo. 45–257× fewer tokens than full-file context across 40 pre-registered queries on four public repos.',
        badge: '45–257×',
    },
    {
        icon: 'dashboard',
        title: 'Team Dashboard',
        desc: 'Read-only web UI: synapse memory, ingestion status, savings, latency trends, community distribution, recent queries.',
        badge: 'New',
    },
    {
        icon: 'doc-code',
        title: 'Self-Documenting Code',
        desc: 'DocEvolver finds undocumented methods, generates JSDoc variants, evolves them against retrieval fitness. Winning variants patched back into source.',
        badge: 'Evolution',
    },
    {
        icon: 'doc-link',
        title: 'Business-Context Synapse Seeding',
        desc: 'seed_from_documents() builds deterministic, LLM-free associations between business documents (decisions, SOPs, meeting notes) and your code graph. Adjacency-matched compounds, title-reference cross-links.',
        badge: 'N-13',
    },
    {
        icon: 'hub',
        title: 'MCP Server',
        desc: 'First-class MCP integration. Works with Claude Code, Cursor, Cline, Continue, and any MCP-compatible agent.',
        badge: 'Universal',
    },
    {
        icon: 'tree',
        title: 'Ten-Language Code Graph',
        desc: 'tree-sitter indexes Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby, and PHP out of the box.',
        badge: '10 langs',
    },
    {
        icon: 'restore',
        title: 'Tool Output Recovery',
        desc: 'Caches dropped tool output from context windows. When your agent forgets, neuralmind remembers.',
        badge: 'Auto-recover',
    },
    {
        icon: 'key',
        title: 'Free Tier — Auto-Provisioned',
        desc: '`pip install neuralmind && neuralmind wakeup .` writes the license on first run. Zero signup wall. Default tier is "free", identity auto-issued.',
        badge: 'v1.7.0',
    },
    {
        icon: 'offline',
        title: '100% Local Engine',
        desc: 'NeuralMind makes zero network calls of its own — only the minimal relevant slice ever reaches your AI tool, never your whole codebase. No telemetry.',
        badge: 'Secure',
    },
    {
        icon: 'terminal',
        title: 'One-Command Project Init',
        desc: '`neuralmind init` auto-detects project structure, installs hooks, builds the index — all at once. Your project is ready in seconds.',
        badge: 'v2.0.0',
    },
    {
        icon: 'shield-check',
        title: 'Compliance Annotation Engine',
        desc: 'Scans code and docs for annotations across CMMC 2.0, NIST SP 800-53, SOX ITGC, HIPAA, SOC 2 and ISO 27001. Each framework carries its own marker on the line — `# NIST AC-1:`, `# CMMC AC.L2-3.1.1:`. Ingest CMMC assessment guides, export control mappings, gate CI on annotation health.',
        badge: 'v2.0.0',
    },
    {
        icon: 'export',
        title: 'Audit Export & CI/CD Check',
        desc: '`neuralmind export --controls` produces control-to-code mappings as CSV for evidence submission, or an SSP report with `--format pdf`. `neuralmind ci-check` gates builds on annotation health.',
        badge: 'v2.0.0',
    },
    {
        icon: 'report-query',
        title: 'Compliance Report MCP Tool',
        desc: '`neuralmind_compliance_report` surfaces live compliance stance from any MCP-compatible agent. Ask "are we compliant on access control?" and get an answer grounded in real annotations.',
        badge: 'v2.0.0',
    },
];

export default function Features() {
    return (
        <section id="features" className="relative py-20 md:py-28 px-4 md:px-6">
            <div className="max-w-6xl mx-auto">
                <header className="max-w-2xl mb-10 md:mb-14">
                    <span className="eyebrow block mb-4">Capabilities</span>
                    <h2 className="font-display text-3xl sm:text-4xl md:text-[2.75rem] font-semibold text-white tracking-tighter mb-4">
                        Features
                    </h2>
                    <p className="text-slate-400 text-base md:text-lg leading-relaxed">
                        Everything persistent memory should be — and nothing it shouldn&apos;t.
                    </p>
                </header>

                {/*
                    One ruled matrix rather than fifteen floating rounded boxes.
                    Shared hairlines let the grid read as a single specification
                    table, which is what a fifteen-item capability list actually
                    is; drop shadows and gaps at this count read as clutter.
                */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 border-t border-l border-carbon-border rounded-sm overflow-hidden">
                    {featureList.map((f) => (
                        <div
                            key={f.title}
                            className="group relative border-b border-r border-carbon-border p-6 lg:p-7 transition-colors duration-200 hover:bg-carbon-card"
                        >
                            <div className="flex items-center gap-3 mb-4">
                                <Icon
                                    name={f.icon}
                                    className="w-[1.375rem] h-[1.375rem] shrink-0 text-faint transition-colors duration-200 group-hover:text-electric"
                                />
                                <span className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-faint transition-colors duration-200 group-hover:text-faint">
                                    {f.badge}
                                </span>
                            </div>

                            <h3 className="font-display text-[1.0625rem] font-semibold text-white tracking-tight mb-2 text-balance">
                                {f.title}
                            </h3>
                            <p className="text-slate-400 text-[0.875rem] leading-relaxed">
                                {withCode(f.desc)}
                            </p>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
