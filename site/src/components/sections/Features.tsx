'use client';

const featureList = [
    {
        icon: '🧬',
        title: 'Hebbian Synapse Layer',
        desc: 'Associations strengthen when you use them together — like a real hippocampus. Budget-neutral, no cost until it activates.',
        badge: 'Budget-neutral',
    },
    {
        icon: '🔦',
        title: 'Cross-Cutting Discovery',
        desc: 'Grep finds the string; the graph finds the pattern. Surfaces every call site that shares a concern — and flags the outlier that skips it — so the case you\'d have missed gets caught before production, not after.',
        badge: 'Completeness',
    },
    {
        icon: '🔄',
        title: 'Progressive L0–L3 Disclosure',
        desc: 'Retrieves exact bytes needed. Never pastes the whole repo. 40–70× compression measured in CI.',
        badge: '40–70×',
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
        icon: '📊',
        title: 'Obsidian-Style Graph View',
        desc: 'Local web UI showing node relationships. Clickable, filterable, searchable. Runs entirely on localhost.',
        badge: 'Local',
    },
    {
        icon: '🗑️',
        title: 'Tool Output Recovery',
        desc: 'Caches dropped tool output from context windows. When your agent forgets, neuralmind remembers.',
        badge: 'Auto-recover',
    },
    {
        icon: '🔒',
        title: '100% Local Engine',
        desc: 'NeuralMind makes zero network calls of its own — only the minimal relevant slice ever reaches your AI tool, never your whole codebase. No telemetry.',
        badge: 'Secure',
    },
    {
        icon: '⚙️',
        title: 'Post-Commit Auto-Rebuild',
        desc: '`neuralmind init-hook .` sets a git hook. Every commit incrementally updates the index in seconds.',
        badge: 'Set & forget',
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
