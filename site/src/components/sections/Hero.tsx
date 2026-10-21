import CommandLine from '@/components/ui/CommandLine';
import Icon from '@/components/ui/Icon';
import Stat, { StatGrid } from '@/components/ui/Stat';
import { QUERY_ID, QUERY_REPO, QUERY_TEXT } from '@/lib/capturedQuery';
import { headline, publicBenchmark, publicQuery, ratioRange, retrievalEval } from '@/lib/evidence';

const AGENTS = ['Claude Code', 'Codex', 'Cursor', 'Cline', 'Hermes', 'any MCP client'];

// The commands a reader runs to try it, verified against neuralmind/cli.py:
// install, index, register the MCP server with Claude Code (`--client` picks
// Cursor, Cline, VS Code or Claude Desktop instead), and install Claude Code's
// hooks. In the task-outcome pilot the agent never called the MCP tools; the
// hooks were how NeuralMind reached it, so they are part of the install.
const INSTALL = ['pip install neuralmind', 'neuralmind build .', 'neuralmind install-mcp', 'neuralmind install-hooks .'];

export default function Hero() {
    // Every figure below is read from the committed runs through lib/evidence,
    // which checks each ratio against site/claims.json at build time.
    const vsGrep = ratioRange(31, 67);
    const vsPaste = ratioRange(51, 242);
    const foundEvidence = headline('ripgrep (query keywords').evidence;
    const side = publicQuery(QUERY_REPO, QUERY_ID);

    return (
        <section className="relative overflow-hidden pt-28 pb-12 md:pt-36 md:pb-16 px-4 md:px-6">
            <div className="grid-bg absolute inset-0 -z-10" aria-hidden="true" />

            <div className="max-w-6xl mx-auto">
                <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,27rem)] gap-12 lg:gap-14 items-start">
                    {/* ── Copy ───────────────────────────────────────────── */}
                    <div>
                        <p className="eyebrow mb-4">
                            Persistent codebase memory · MCP server for Claude Code, Codex &amp; Cursor
                        </p>

                        <h1 className="font-display text-4xl sm:text-5xl lg:text-hero font-semibold text-white leading-display tracking-tightest mb-6">
                            Your coding agent forgets your codebase.{' '}
                            <span className="gradient-text">NeuralMind remembers it.</span>
                        </h1>

                        {/* tests/test_site_claims.py: the found count stays on one
                            line with ripgrep's, and the 150-question figure stays
                            in this file. */}
                        <p className="text-muted text-base sm:text-lg leading-relaxed max-w-xl mb-8">
                            A local index of your repo that hands your agent the right code first —{' '}
                            <span className="text-ink font-medium">the gold file on 40 of 40 public-benchmark queries, where keyword ripgrep opening its top five files whole found 32 of 40, at 31–67× fewer tokens than ripgrep</span>{' '}
                            and 51–242× fewer than pasting every source file. On a larger 150-question
                            eval it puts a gold file in the top five on 93.3%, and all 10 misses are
                            published. By default, no telemetry. MIT core, free at one seat.
                        </p>

                        <ol className="space-y-2 mb-8 max-w-md" aria-label="Install in four commands">
                            {INSTALL.map((cmd, i) => (
                                <li key={cmd} className="flex items-center gap-3">
                                    <span className="w-6 shrink-0 font-mono text-xs text-faint tabular-nums">
                                        {String(i + 1).padStart(2, '0')}
                                    </span>
                                    <CommandLine command={cmd} className="flex-1" />
                                </li>
                            ))}
                        </ol>

                        <div className="flex flex-wrap items-center gap-3">
                            <a href="/team" className="btn-primary py-3">
                                For teams
                                <Icon name="arrow-right" className="w-4 h-4" />
                            </a>
                            <a href="#quickstart" className="btn-secondary py-3">
                                Quickstart
                            </a>
                            <a href="https://github.com/dfrostar/neuralmind" className="btn-secondary py-3">
                                Source
                            </a>
                        </div>

                        <p className="mt-6 text-faint text-sm">
                            Works with {AGENTS.join(' · ')}
                        </p>
                    </div>

                    {/* ── The same question, two retrievers ──────────────── */}
                    <figure className="panel rounded-card overflow-hidden shadow-2xl shadow-black/40">
                        <div className="px-5 py-4 border-b border-carbon-border bg-carbon-raised">
                            <p className="eyebrow mb-2">Same question · {side.repo} @ {side.sha}</p>
                            <p className="text-white text-body-sm font-medium">&ldquo;{QUERY_TEXT}&rdquo;</p>
                            <p className="text-faint text-caption mt-1">
                                Gold file: <span className="font-mono text-body">{side.gold.join(', ')}</span>
                            </p>
                        </div>

                        {[
                            { name: 'ripgrep, top five files opened whole', r: side.ripgrep },
                            { name: 'neuralmind query', r: side.neuralmind },
                        ].map(({ name, r }) => (
                            <div key={name} className="px-5 py-4 border-b border-carbon-border last:border-b-0">
                                <div className="flex items-baseline justify-between gap-3 mb-2.5">
                                    <p className="font-mono text-caption text-ink">{name}</p>
                                    <p className="metric text-caption text-muted whitespace-nowrap">{r.tokens} tokens</p>
                                </div>
                                <ul className="flex flex-wrap gap-1.5 mb-2.5">
                                    {r.files.map((f) => (
                                        <li
                                            key={f}
                                            className={`font-mono text-eyebrow px-2 py-1 rounded-control border ${
                                                side.gold.includes(f)
                                                    ? 'border-proton/40 text-proton bg-proton/10'
                                                    : 'border-carbon-line text-muted'
                                            }`}
                                        >
                                            {f}
                                        </li>
                                    ))}
                                </ul>
                                <p className={`text-caption ${r.found ? 'text-proton' : 'text-danger'}`}>
                                    {r.found
                                        ? `Gold file found, ranked ${r.rank === 1 ? 'first' : `#${r.rank}`}`
                                        : 'Gold file not in the context'}
                                </p>
                            </div>
                        ))}

                        <figcaption className="px-5 py-3 bg-carbon-raised text-faint text-caption leading-relaxed">
                            One of the 40 queries, from the committed run (bench/public/results.json). The real{' '}
                            <a href="#real-output" className="text-electric hover:text-electric-bright">query output</a> is below.
                        </figcaption>
                    </figure>
                </div>

                {/* ── Stats ──────────────────────────────────────────────── */}
                <StatGrid className="grid-cols-2 lg:grid-cols-4 mt-14 md:mt-20">
                    <Stat
                        label="Gold file found"
                        value={publicBenchmark.found('neuralmind')}
                        note={`public-benchmark queries on ${publicBenchmark.repoNames.length} pinned repos; keyword ripgrep found ${publicBenchmark.found('ripgrep')}`}
                        evidence={foundEvidence}
                    />
                    <Stat
                        label="Fewer tokens vs ripgrep"
                        value={vsGrep.text}
                        note="same queries, against ripgrep opening its top five files whole"
                        evidence={vsGrep.evidence}
                    />
                    <Stat
                        label="Vs pasting every file"
                        value={vsPaste.text}
                        note="same queries; the easiest baseline to beat"
                        evidence={vsPaste.evidence}
                    />
                    <Stat
                        label="Top-5 hit rate"
                        value={retrievalEval.hitAt5}
                        note={`${retrievalEval.questions} questions on ${retrievalEval.repos} repos; all ${retrievalEval.misses} misses published`}
                        evidence={retrievalEval.evidence}
                    />
                </StatGrid>
                <p className="mt-4 text-faint text-caption">
                    Each reruns from a fresh clone with one command.{' '}
                    <a href="/benchmark/" className="text-electric hover:text-electric-bright">
                        Every number, its source and where NeuralMind loses →
                    </a>
                </p>
            </div>
        </section>
    );
}
