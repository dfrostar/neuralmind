import Callout from '@/components/ui/Callout';
import EvidenceBadge from '@/components/ui/EvidenceBadge';
import SectionHeader from '@/components/ui/SectionHeader';
import Stat, { StatGrid } from '@/components/ui/Stat';
import { disclosures, headline, publicBenchmark, ratio, taskOutcomePilot, taskOutcomeRerun } from '@/lib/evidence';
import { withCode } from '@/lib/ticks';

// The one evidence block on the homepage. It replaces three in a row
// (Benchmarks, Prove it, Proof) that each restated the headline. Numbers come
// from lib/evidence, which reads the committed runs and site/claims.json; the
// hero already carries the headline, so this block carries what backs it and
// what doesn't.

const DOCS = 'https://docs.neuralmind.uk/comparisons';

// Scoped to what the repo has measured. A row with no measurement says so
// rather than leaving a blank a reader could fill with a guess.
const comparisons = (found: string, grepFound: string) => [
    {
        name: 'NeuralMind',
        gets: 'A project map, the relevant symbols and their callers, plus links learned from use. Rebuilt by git hooks; says when it is stale.',
        measured: `Public benchmark: the gold file on ${found} queries.`,
        href: '/benchmark/',
        ours: true,
    },
    {
        name: 'Keyword search (ripgrep)',
        gets: 'Files that contain the question’s words, opened whole. Always current.',
        measured: `Same benchmark, top five files opened whole: the gold file on ${grepFound}, at more tokens on every repo.`,
        href: '/benchmark/',
    },
    {
        name: 'Vector RAG',
        gets: 'The chunks whose embeddings sit closest to the question.',
        measured: 'Same benchmark, NeuralMind’s own index alone: cheaper on all four repos, and it ranks the gold file higher on flask and rich. NeuralMind’s recall is at or above it on every repo.',
        href: `${DOCS}/vs-rag.html`,
    },
    {
        name: 'CLAUDE.md and rules files',
        gets: 'What you wrote by hand, current until the code moves on.',
        measured: 'Not benchmarked: a different job. They compose — CLAUDE.md can import the SYNAPSE_MEMORY.md NeuralMind exports.',
        href: `${DOCS}/vs-claude-code-native-memory.html`,
    },
    {
        name: 'Cursor and Windsurf memory',
        gets: 'Memories and an index inside one editor’s agent.',
        measured: 'Not benchmarked here. NeuralMind serves every MCP agent from one index in your repo.',
        href: `${DOCS}/vs-cursor-codebase.html`,
    },
    {
        name: 'codebase-memory-mcp',
        gets: 'A structural graph from one static binary, across far more languages, indexed faster.',
        measured: 'One retrieval head-to-head, June 2026 (NeuralMind v0.33.0), on requests and click only, not re-run since.',
        href: `${DOCS}/vs-codebase-memory-mcp.html`,
    },
];

export default function Proof() {
    const floor = ratio(4.0, 1);
    const field = ratio(48.8);
    const synapse = headline('Synapse recall never lowers');
    const faithfulness = headline('Faithfulness vs naive truncation');
    const rows = comparisons(publicBenchmark.found('neuralmind'), publicBenchmark.found('ripgrep'));
    const pilot = taskOutcomePilot.figures;

    return (
        <section id="proof" className="relative py-20 md:py-28 px-4 md:px-6">
            <div className="max-w-6xl mx-auto">
                <SectionHeader title="Measured, with the misses published">
                    Every number says which kind of evidence it is: gated in CI on every PR,
                    reproducible from a fresh clone, a pilot, or one repo&rsquo;s field report. The
                    retrieval wins sit beside the task-outcome pilot that found no difference.
                </SectionHeader>

                {/* ── Public benchmark, per repo ─────────────────────────── */}
                <div className="flex flex-wrap items-baseline justify-between gap-3 mb-4">
                    <h3 className="font-display text-xl font-semibold text-white tracking-tight">
                        The public benchmark, per repo
                    </h3>
                    <EvidenceBadge level={headline('ripgrep (query keywords').evidence} />
                </div>
                <div className="overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0">
                    <table className="data-table min-w-[40rem]">
                        <caption className="sr-only">
                            Mean tokens per query and gold-file found counts, NeuralMind against ripgrep and pasting every file
                        </caption>
                        <thead>
                            <tr>
                                <th scope="col">Repo</th>
                                <th scope="col" className="num">Queries</th>
                                <th scope="col" className="num">NeuralMind tokens</th>
                                <th scope="col" className="num">ripgrep tokens</th>
                                <th scope="col" className="num">Every file</th>
                                <th scope="col" className="num">Found: NM / rg</th>
                            </tr>
                        </thead>
                        <tbody>
                            {publicBenchmark.repos.map((r) => {
                                const by = Object.fromEntries(r.rows.map((x) => [x.backend, x]));
                                return (
                                    <tr key={r.name}>
                                        <th scope="row">{r.name}</th>
                                        <td className="num">{r.queries}</td>
                                        <td className="num text-proton font-semibold">{by.neuralmind.tokens}</td>
                                        <td className="num">{by.ripgrep.tokens}</td>
                                        <td className="num">{by['full-file'].tokens}</td>
                                        <td className="num">
                                            {by.neuralmind.found} / {by.ripgrep.found}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
                <p className="mt-3 text-faint text-caption">
                    Mean tokens per query ({publicBenchmark.tokenizer}), from the committed run. Pre-registered
                    queries on pinned commits; a gold file is the definition site of the symbol asked about, so
                    there is no judge to argue with.{' '}
                    <a href="/benchmark/" className="link">
                        All four backends, MRR and the reproduce command
                    </a>
                </p>

                {/* ── Task outcomes, beside the retrieval wins ───────────── */}
                <div className="mt-8 rounded-card border border-warn/30 bg-warn/5 p-5 md:p-6">
                    <div className="flex flex-wrap items-center gap-3 mb-2">
                        <h3 className="font-display text-title-sm font-semibold text-white tracking-tight">
                            Task outcomes: a {pilot.tasks}-task pilot found no difference
                        </h3>
                        <EvidenceBadge level={taskOutcomePilot.evidence} />
                    </div>
                    <p className="text-body text-sm leading-relaxed">
                        Fewer tokens in the window isn&rsquo;t the same as a lower cost per task. In a pre-registered pilot, Claude Code
                        solved {pilot.tasks_solved.baseline} of {pilot.tasks} bug-fix tasks without NeuralMind and{' '}
                        {pilot.tasks_solved.neuralmind} with it, at a median per-task cost change of{' '}
                        {pilot.median_cost_change} (95% CI {pilot.cost_change_ci95}). The reason: in{' '}
                        {pilot.runs / 2} runs the agent never called NeuralMind&rsquo;s tools, and an exploratory
                        rerun with the change released in v{taskOutcomeRerun.figures.released_in}, which tells it when to, found the same.{' '}
                        <a href="/benchmark/#task-outcomes" className="link">
                            The pilot, its spec and every run
                        </a>
                    </p>
                </div>

                {/* ── Gates and the field report ─────────────────────────── */}
                <StatGrid className="grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 mt-12">
                    <Stat
                        label="Token-reduction floor"
                        value={floor.text}
                        note="On the ~500-line CI fixture; the build fails below it. A floor, not the headline."
                        evidence={floor.evidence}
                    />
                    <Stat
                        label="Learned recall"
                        value="Never lowers hit rate"
                        figure={false}
                        note="Synapse recall on vs off, at a neutral token budget, on the same fixture: it shows direction, not size."
                        evidence={synapse.evidence}
                    />
                    <Stat
                        label="Facts vs naive truncation"
                        value="+0.265"
                        note="At an equal token budget, measured with CI’s command on one machine at v4.12.0 (0.839 vs 0.574). CI fails below −0.10; v4.3.4 was a published loss."
                        evidence={faithfulness.evidence}
                    />
                    <Stat
                        label="Field report, one repo"
                        value={field.text}
                        note="A ~9,300-node private TypeScript codebase, against the fixed 50K-token estimate the CLI used before v4.5.0. Method reproducible, not CI-gated."
                        evidence={field.evidence}
                    />
                </StatGrid>
                <p className="mt-3 text-faint text-caption">
                    <a href="/field-reports/measure-memory-across-a-refactor/" className="link">
                        Read the field report, before-and-after numbers included
                    </a>
                </p>

                <Callout variant="not-measured" className="mt-10">
                    <ul className="space-y-2">
                        {disclosures.map((d) => (
                            <li key={d.claim}>
                                {d.claim}. <span className="text-faint">Measure it on your repo: </span>
                                <code className="font-mono text-code-inline text-body whitespace-nowrap">{d.reproduce}</code>
                            </li>
                        ))}
                        <li>
                            Testimonials, named case studies and adoption numbers: we don&rsquo;t have them yet.
                            The one field report is anonymized.
                        </li>
                    </ul>
                </Callout>

                {/* ── Comparison ─────────────────────────────────────────── */}
                <h3 className="font-display text-xl font-semibold text-white tracking-tight mt-16 mb-2">
                    How it compares
                </h3>
                <p className="text-muted text-sm mb-5 max-w-3xl">
                    Each row says only what has been measured here. Where nothing has, it says that.
                </p>
                <div className="overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0">
                    <table className="data-table min-w-[44rem]">
                        <caption className="sr-only">NeuralMind compared with other ways to give an agent codebase context</caption>
                        <thead>
                            <tr>
                                <th scope="col">Approach</th>
                                <th scope="col">What your agent gets</th>
                                <th scope="col">What&rsquo;s measured here</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((r) => (
                                <tr key={r.name} className={r.ours ? 'is-ours' : undefined}>
                                    <th scope="row">
                                        <a href={r.href} className="hover:text-electric">
                                            {r.name}
                                        </a>
                                    </th>
                                    <td>{r.gets}</td>
                                    <td>{r.measured}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* ── Your repo ──────────────────────────────────────────── */}
                <div className="mt-12 panel-accent rounded-card p-6 md:p-8 grid md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-6 items-center">
                    <div>
                        <h3 className="font-display text-xl font-semibold text-white tracking-tight mb-2">
                            The number that decides it is yours
                        </h3>
                        <p className="text-muted text-sm leading-relaxed">
                            {withCode(
                                'Run `neuralmind benchmark .` for tokens per question on your code, and `neuralmind eval . --synapse-ab` with your own questions to see whether learned recall helps on your repo.',
                            )}{' '}
                            <a href="/measure-your-own/" className="link">
                                How to measure your own
                            </a>
                        </p>
                    </div>
                    <div className="bg-carbon-raised rounded-control p-4 font-mono text-caption text-body overflow-x-auto">
                        {['pip install neuralmind', 'cd your-repo && neuralmind build .', 'neuralmind benchmark .'].map((line) => (
                            <p key={line} className="whitespace-nowrap">
                                <span className="text-faint select-none">$ </span>
                                {line}
                            </p>
                        ))}
                    </div>
                </div>
            </div>
        </section>
    );
}
