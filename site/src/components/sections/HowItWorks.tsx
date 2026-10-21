import Icon, { type IconName } from '@/components/ui/Icon';
import SectionHeader from '@/components/ui/SectionHeader';
import { QUERY_EXCERPT } from '@/lib/capturedQuery';
import { withCode } from '@/lib/ticks';

// Every command named here exists in neuralmind/cli.py.
const steps: { icon: IconName; title: string; desc: string; tag: string }[] = [
    {
        icon: 'index',
        title: 'Index',
        desc: '`neuralmind build .` parses your repo with tree-sitter into a graph of functions, classes, imports and call edges, and embeds it on your machine. Ten languages plus JavaScript, no config.',
        tag: 'On your machine',
    },
    {
        icon: 'query',
        title: 'Query',
        desc: 'Your agent asks over MCP or a Claude Code hook and gets a project map, the relevant symbols and their callers, deeper only where the question needs it. A local index lookup, not another model call.',
        tag: 'L0–L3 disclosure',
    },
    {
        icon: 'recall',
        title: 'Remember',
        desc: 'A synapse layer links files you use together and re-ranks recall with those links next session. `neuralmind memory publish` writes them to a file you commit, so teammates start with them.',
        tag: 'Across sessions',
    },
];

// The quickstart: install, index, connect, keep fresh, measure. The comments
// are what each command does, not what it promises.
const QUICKSTART: { cmd: string; note: string }[] = [
    { cmd: 'pip install neuralmind', note: 'Python 3.10+' },
    { cmd: 'cd your-repo && neuralmind build .', note: 'first build downloads a public embedding model' },
    { cmd: 'neuralmind install-mcp', note: 'Claude Code; --client cursor | cline | vscode | claude-desktop' },
    { cmd: 'neuralmind init-hook .', note: 'rebuild after commits, pulls, checkouts and rebases' },
    { cmd: 'neuralmind benchmark .', note: 'your own tokens-per-question, on your code' },
];

const tone = {
    head: 'text-ink',
    hit: 'text-body',
    cut: 'text-faint',
} as const;

export default function HowItWorks() {
    return (
        <section id="how-it-works" className="relative py-20 md:py-28 px-4 md:px-6">
            <div className="max-w-6xl mx-auto">
                <SectionHeader eyebrow="How it works" title="Index once. Every session starts oriented.">
                    Agents reason well over what is in the window and forget it when the session
                    ends, so each one pays again to find its way around the same repo. NeuralMind
                    keeps that map on your machine and answers from it.
                </SectionHeader>

                <ol className="grid grid-cols-1 md:grid-cols-3 border-t border-l border-carbon-border">
                    {steps.map((step, i) => (
                        <li key={step.title} className="border-b border-r border-carbon-border p-7 md:p-8">
                            <div className="flex items-center justify-between mb-6">
                                <Icon name={step.icon} className="w-6 h-6 text-electric" />
                                <span className="font-mono text-xs text-faint tabular-nums">
                                    {String(i + 1).padStart(2, '0')} / {String(steps.length).padStart(2, '0')}
                                </span>
                            </div>
                            <h3 className="font-display text-xl font-semibold text-white tracking-tight mb-3">
                                {step.title}
                            </h3>
                            <p className="text-muted leading-relaxed text-body-sm mb-6">{withCode(step.desc)}</p>
                            <span className="inline-flex items-center gap-2 font-mono text-eyebrow uppercase tracking-eyebrow text-faint">
                                <span className="w-1 h-1 rounded-pill bg-proton" />
                                {step.tag}
                            </span>
                        </li>
                    ))}
                </ol>

                <div className="grid lg:grid-cols-2 gap-6 mt-10">
                    {/* ── Quickstart ─────────────────────────────────────── */}
                    <div id="quickstart" className="panel rounded-card p-6 md:p-7 scroll-mt-24 min-w-0">
                        <h3 className="font-display text-title-sm font-semibold text-white tracking-tight mb-1">
                            Quickstart
                        </h3>
                        <p className="text-muted text-sm mb-5">
                            Five commands. No account, no signup, no hosted service.
                        </p>
                        <ol className="space-y-3">
                            {QUICKSTART.map((s, i) => (
                                <li key={s.cmd} className="grid grid-cols-[1.75rem_minmax(0,1fr)] gap-x-2">
                                    <span className="font-mono text-xs text-faint tabular-nums pt-1">
                                        {String(i + 1).padStart(2, '0')}
                                    </span>
                                    <div className="min-w-0">
                                        <code className="block font-mono text-caption text-ink bg-carbon-raised border border-carbon-border rounded-control px-3 py-2 overflow-x-auto whitespace-nowrap select-all">
                                            {s.cmd}
                                        </code>
                                        <p className="text-faint text-caption mt-1">{s.note}</p>
                                    </div>
                                </li>
                            ))}
                        </ol>
                        <p className="text-muted text-sm mt-5">
                            Using Hermes? <code className="font-mono text-code-inline text-body">neuralmind install-hermes-plugin</code>.
                            Other MCP clients point at <code className="font-mono text-code-inline text-body">neuralmind-mcp</code>.{' '}
                            <a href="https://docs.neuralmind.uk/wiki/CLI-Reference" className="text-electric hover:text-electric-bright">
                                CLI reference →
                            </a>
                        </p>
                    </div>

                    {/* ── Real output ────────────────────────────────────── */}
                    <figure id="real-output" className="panel rounded-card overflow-hidden scroll-mt-24 min-w-0 flex flex-col">
                        <div className="flex items-center gap-2 px-4 py-3 border-b border-carbon-border bg-carbon-raised">
                            <span className="w-2.5 h-2.5 rounded-pill bg-carbon-line" />
                            <span className="w-2.5 h-2.5 rounded-pill bg-carbon-line" />
                            <span className="w-2.5 h-2.5 rounded-pill bg-carbon-line" />
                            <span className="ml-2 font-mono text-eyebrow text-faint tracking-wide">requests/src/requests — zsh</span>
                        </div>
                        <div className="p-5 font-mono text-caption leading-relaxed overflow-x-auto flex-1">
                            {QUERY_EXCERPT.map((line, i) => (
                                <p
                                    key={i}
                                    className={`${tone[line.tone ?? 'hit']} ${line.tone === 'head' ? 'mb-2' : ''} whitespace-pre-wrap break-words`}
                                >
                                    {line.text}
                                </p>
                            ))}
                        </div>
                        <figcaption className="px-5 py-3 border-t border-carbon-border bg-carbon-raised text-faint text-caption leading-relaxed">
                            Real output, trimmed where marked: psf/requests at the benchmark&rsquo;s pinned
                            commit, captured 2026-10-21. Every symbol listed is in{' '}
                            <span className="font-mono text-body">exceptions.py</span>, the file ripgrep&rsquo;s
                            five never opened.
                        </figcaption>
                    </figure>
                </div>
            </div>
        </section>
    );
}
