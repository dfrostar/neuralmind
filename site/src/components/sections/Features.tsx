// neuralmind:example-file — annotations here are syntax examples, not evidence.
import Icon, { type IconName } from '@/components/ui/Icon';
import { withCode } from '@/lib/ticks';

// Every figure here is registered in site/claims.json and gated by
// tests/test_site_claims.py; every command exists in neuralmind/cli.py.
//
// The list used to be twenty-two equal cards badged with the release that
// shipped them ("v2.0.0", "v3.13.0", a "New" that was months old). A release
// number tells a reader nothing about what a feature is for, so the cards are
// grouped by the job they do instead, and the badge says what kind of thing it
// is.
type Feature = { icon: IconName; title: string; desc: string; badge: string };
type Group = { id: string; heading: string; lede: string; features: Feature[] };

const groups: Group[] = [
    {
        id: 'memory',
        heading: 'Memory that learns how you work',
        lede: 'Associations strengthen when you use code together and fade when you stop — so recall reflects how your team actually works, not just what the files say.',
        features: [
            {
                icon: 'synapse',
                title: 'Hebbian synapse layer',
                desc: 'Files you open, edit and query together get a weighted edge; unused edges decay. Recall displaces the weakest hits one-for-one instead of adding to them, so it is budget-neutral by design.',
                badge: 'Budget-neutral',
            },
            {
                icon: 'recall',
                title: 'Session-start memory for Claude Code',
                desc: 'Learned hub files and associations are exported to `SYNAPSE_MEMORY.md`, which Claude Code loads at session start — your agent begins already oriented.',
                badge: 'Hooks',
            },
            {
                icon: 'cognition',
                title: 'Cognition loop',
                desc: '`neuralmind cognition-loop` runs one maintenance pass on demand: the synapse store’s half-life decay plus read-dedup cleanup. It never decays twice, so it’s safe for cron; Claude Code’s hooks already decay at every session start.',
                badge: 'Maintenance',
            },
            {
                icon: 'restore',
                title: 'Session summaries',
                desc: 'Periodic, semantically recallable digests of what an agent did, decided and touched — so the next session can pick up without re-reading the logs.',
                badge: 'Recall',
            },
            {
                icon: 'recall',
                title: 'Decision memory',
                desc: 'Architecture decisions stored with rationale, evidence, commit SHA, affected files and rejected alternatives — full-text searchable. When a commit changes a decision’s files after it was recorded, the post-commit hook from `neuralmind init-hook` marks it stale.',
                badge: 'Decisions',
            },
            {
                icon: 'shield-check',
                title: 'Stale-decision guard',
                desc: 'Before your agent edits a file, a PreToolUse hook surfaces any decision governing it that has gone stale or been invalidated — with the reason and how to restore one that still holds — so a retired decision can’t silently steer the edit.',
                badge: 'Guardrail',
            },
        ],
    },
    {
        id: 'context',
        heading: 'Context that costs less',
        lede: 'The agent gets a map, the relevant symbols and their call edges — not whole files — and asks for more depth only where it needs it.',
        features: [
            {
                icon: 'layers',
                title: 'Progressive L0–L3 disclosure',
                desc: 'Project map, then relevant clusters, then symbol detail, then search — only as deep as the question needs. 51–242× fewer tokens than full-file context across 40 pre-registered queries on four public repos.',
                badge: '51–242×',
            },
            {
                icon: 'layers',
                title: 'Hard context budget',
                desc: 'Set a per-query token budget and NeuralMind trims L3 → L2 → L1 to fit, so the context it hands over never exceeds it — useful for cost-controlled multi-agent workflows.',
                badge: 'Budget',
            },
            {
                icon: 'restore',
                title: 'Read dedup for repeat reads',
                desc: 'In Claude Code, a repeat read of a file your agent already has — same session, unchanged — comes back as a short stub instead of the whole file again. The next read is always full, and compaction resets it.',
                badge: 'Claude Code',
            },
            {
                icon: 'chip',
                title: 'Local retrieval, no model call',
                desc: 'Recall is a local index lookup, not another round trip to a model. The ChromaDB-free TurboVec backend keeps 4-bit vectors 8–16× smaller with fact recall 0.800 vs 0.744 for float32 — parity gated in CI.',
                badge: 'TurboVec',
            },
        ],
    },
    {
        id: 'stack',
        heading: 'Works with the stack you already run',
        lede: 'No new IDE, no model swap, no hosted service. NeuralMind sits between your agent and your code.',
        features: [
            {
                icon: 'hub',
                title: 'MCP server for any agent',
                desc: '`neuralmind install-mcp` registers the server with Claude Code — or Cursor, Cline, VS Code and Claude Desktop via `--client` — and Codex, Continue or any other MCP client points at `neuralmind-mcp`. One memory, every agent.',
                badge: 'MCP',
            },
            {
                icon: 'tree',
                title: 'Ten-language code graph',
                desc: 'Bundled tree-sitter indexes Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby and PHP out of the box — plus OpenAPI, SQL DDL and Protocol Buffers schemas.',
                badge: '10 langs',
            },
            {
                icon: 'terminal',
                title: 'One-command setup',
                desc: '`neuralmind init` scans your languages, builds the graph and embeddings, and starts the file watcher. `neuralmind doctor` verifies the install end to end.',
                badge: 'Setup',
            },
            {
                icon: 'dashboard',
                title: 'Graph view & dashboard',
                desc: '`neuralmind serve` opens a force-directed code graph with the synapse overlay, plus a read-only dashboard: memory health, ingestion, savings and latency trends.',
                badge: 'Local UI',
            },
            {
                icon: 'shield-check',
                title: 'Commit-time drift guard',
                desc: '`neuralmind init-hook .` adds a pre-commit check that flags code skipping a pattern its siblings share — the eleventh handler that forgot the auth check the other ten have.',
                badge: 'pre-commit',
            },
            {
                icon: 'doc-link',
                title: 'Business-context seeding',
                desc: 'Links decisions, SOPs and meeting notes to the code they describe with deterministic, LLM-free associations — so "why" questions reach the right files.',
                badge: 'Docs → code',
            },
            {
                icon: 'doc-code',
                title: 'Self-documenting code',
                desc: 'DocEvolver finds undocumented methods, generates doc-comment variants and keeps the ones that measurably improve retrieval.',
                badge: 'DocEvolver',
            },
        ],
    },
    {
        id: 'teams',
        heading: 'Built for teams and audits',
        lede: 'Memory your whole team inherits, with the controls and evidence a security review asks for — all evaluable free at one seat.',
        features: [
            {
                icon: 'hub',
                title: 'Team memory in git',
                desc: '`neuralmind memory publish` writes a learned-weights bundle (no source code) that you commit. Teammates inherit it on their next session — a fresh clone starts with the team’s intuition.',
                badge: 'git-native',
            },
            {
                icon: 'key',
                title: 'Governance & audit log',
                desc: 'Publishing honours the scope and weight threshold an admin sets, removing an association retracts it for every teammate, imported memory passes a review queue, and each publish, import, review and admin change lands in a hash-chained audit log you can verify and export.',
                badge: 'Free at 1 seat',
            },
            {
                icon: 'offline',
                title: 'Local-first engine',
                desc: 'By default NeuralMind sends no telemetry and transmits no repository content off your machine; your agent receives only the slice it asked for. One public model download on first build, pre-seedable for air-gapped installs.',
                badge: 'No telemetry',
            },
            {
                icon: 'shield-check',
                title: 'Compliance annotations',
                desc: 'Finds control annotations across CMMC 2.0, NIST SP 800-53, SOX ITGC, HIPAA, SOC 2 and ISO 27001 — `# NIST AC-1:`, `# CMMC AC.L2-3.1.1:` — and answers "are we covered on access control?" over MCP.',
                badge: 'Compliance',
            },
            {
                icon: 'export',
                title: 'Audit export & CI gate',
                desc: '`neuralmind export --controls` produces control-to-code mappings for evidence packages; `neuralmind ci-check` fails a build when annotation health drops.',
                badge: 'Evidence',
            },
        ],
    },
];

export default function Features() {
    return (
        <section id="features" className="relative py-20 md:py-28 px-4 md:px-6">
            <div className="max-w-6xl mx-auto">
                <header className="max-w-2xl mb-10 md:mb-14">
                    <span className="eyebrow block mb-4">Capabilities</span>
                    <h2 className="font-display text-3xl sm:text-4xl md:text-[2.75rem] font-semibold text-white tracking-tighter mb-4">
                        What your agent gets
                    </h2>
                    <p className="text-slate-400 text-base md:text-lg leading-relaxed">
                        Persistent memory, cheaper context, and the controls a team needs — in one
                        local install.
                    </p>
                </header>

                <div className="space-y-14 md:space-y-16">
                    {groups.map((group) => (
                        <div key={group.id} id={`features-${group.id}`}>
                            <div className="max-w-3xl mb-6">
                                <h3 className="font-display text-xl md:text-2xl font-semibold text-white tracking-tight mb-2">
                                    {group.heading}
                                </h3>
                                <p className="text-slate-400 text-[0.9375rem] leading-relaxed">{group.lede}</p>
                            </div>

                            {/*
                                One ruled matrix per group rather than floating
                                rounded boxes: shared hairlines read as a
                                specification table, which is what a capability
                                list is.
                            */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 border-t border-l border-carbon-border rounded-sm overflow-hidden">
                                {group.features.map((f) => (
                                    <div
                                        key={f.title}
                                        className="group relative border-b border-r border-carbon-border p-6 lg:p-7 transition-colors duration-200 hover:bg-carbon-card"
                                    >
                                        <div className="flex items-center gap-3 mb-4">
                                            <Icon
                                                name={f.icon}
                                                className="w-[1.375rem] h-[1.375rem] shrink-0 text-faint transition-colors duration-200 group-hover:text-electric"
                                            />
                                            <span className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-faint">
                                                {f.badge}
                                            </span>
                                        </div>

                                        <h4 className="font-display text-[1.0625rem] font-semibold text-white tracking-tight mb-2 text-balance">
                                            {f.title}
                                        </h4>
                                        <p className="text-slate-400 text-[0.875rem] leading-relaxed">
                                            {withCode(f.desc)}
                                        </p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
