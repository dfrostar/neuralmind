import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import Callout from '@/components/ui/Callout';
import EvidenceBadge from '@/components/ui/EvidenceBadge';
import Stat, { StatGrid } from '@/components/ui/Stat';
import {
    GITHUB_URL,
    blob,
    claimedRatios,
    disclosures,
    headline,
    publicBenchmark,
    quotableClaims,
    ratio,
    ratioRange,
    retrievalEval,
    taskOutcomeHermes,
    taskOutcomePilot,
    type Figure,
    type RepoResult,
} from '@/lib/evidence';
import { pageMetadata } from '@/lib/seo';
import type { Metadata } from 'next';

const PUBLIC_MD = `${GITHUB_URL}/blob/main/docs/benchmarks/public.md`;
const RESULTS_JSON = `${GITHUB_URL}/blob/main/bench/public/results.json`;
const MANIFEST = `${GITHUB_URL}/blob/main/evals/public/manifest.json`;

export const metadata: Metadata = pageMetadata({
    path: '/benchmark',
    title: 'Code Retrieval Benchmark: Recall vs. Tokens — NeuralMind',
    description:
        'NeuralMind vs ripgrep, vector RAG and pasting files on 40 pre-registered queries, misses published — and a 20-task outcome pilot that found no difference.',
    keywords: [
        'AI coding agent benchmark',
        'gold-file recall',
        'token reduction benchmark',
        'reproducible retrieval benchmark',
        'code retrieval benchmark',
        'RAG vs grep for code',
        'RAG baseline comparison',
        'context compression measurement',
        'NeuralMind benchmark',
        'task-outcome benchmark',
        'coding agent pilot study',
    ],
    ogTitle: 'The NeuralMind Public Benchmark',
    ogDescription:
        '40 pre-registered queries on requests, click, flask and rich: the gold file found on all 40 at 51–242× fewer tokens than pasting files — and where NeuralMind still misses.',
});

/**
 * This page is the site's single proof page, and it types no measured number
 * by hand. The per-repo tables are bench/public/results.json, the headline and
 * the ledger are site/claims.json, and the 150-question figures are counted
 * from the retrieval eval's raw output — all through lib/evidence, at build
 * time. The ledger must cover every ratio claims.json lists: one it leaves out
 * fails the build (see LEDGER below), so a claim can't sit in the canon with
 * nowhere a reader can see where it came from.
 */

// Context for a repo's table that the run's numbers can't say themselves.
const REPO_NOTES: Record<string, string> = {
    click: 'echo-util, missed from the v4.6.0 run until v4.12.0, is found again.',
    flask: 'xfile-dispatch-context, missed in the v4.10.0 run, is found at v4.12.0. The plain vector baseline misses two of these ten queries.',
};

// What each ratio in claims.json is, in a reader's words. The numbers,
// evidence levels, sources and commands all come from claims.json.
const LEDGER: { figure: Figure; values: number[]; what: string }[] = [
    { figure: ratioRange(51, 242), values: [51, 242], what: 'Fewer tokens than pasting every source file, across the 40 public-benchmark queries (per repo in the tables above).' },
    { figure: ratioRange(31, 67), values: [31, 67], what: 'Fewer tokens than ripgrep opening its top five files whole, same queries. An agent that reads only the matching lines pays less than this baseline; that is not measured.' },
    { figure: ratio(78.6), values: [78.6], what: 'psf/requests v2.32.3, `neuralmind benchmark .` at v4.5.0: the measured code the index covers over the tokens each generic question cost.' },
    { figure: ratio(41.8), values: [41.8], what: 'The same requests run against the fixed 50K-token estimate: the legacy line the CLI prints beside the measured one.' },
    { figure: ratioRange(12, 50), values: [12, 50], what: 'Field reports measured by `neuralmind benchmark` before v4.5.0, against its fixed 50K-token estimate. A new run is not on this scale.' },
    { figure: ratio(48.8), values: [48.8], what: 'One field report: a ~9,300-node private TypeScript codebase through a major rebuild, against the fixed 50K-token estimate the CLI used before v4.5.0.' },
    { figure: ratio(65.6), values: [65.6], what: 'Community submission: a 241-node JavaScript project, against the fixed 50K-token estimate.' },
    { figure: ratio(46), values: [46], what: 'Community submission: a 1,626-node Python project, against the fixed 50K-token estimate.' },
    { figure: ratio(5.1), values: [5.1], what: 'The ~500-line CI fixture, measured at v4.3.4. It moves with retrieval changes; CI gates only the floor below.' },
    { figure: ratio(4.0, 1), values: [4.0], what: 'The CI regression floor on that fixture: the build fails below it.' },
    { figure: ratio(5.5), values: [5.5], what: 'Average reduction scripts/demo.sh prints across its three bundled-fixture queries.' },
    { figure: ratio(5.7), values: [5.7], what: 'One query in the same demo.' },
    { figure: ratioRange(8, 16), values: [8, 16], what: 'TurboVec’s 4-bit index vectors against float32: size, not tokens.' },
];

{
    const covered = new Set([...LEDGER.flatMap((l) => l.values), ...publicBenchmark.repos.map((r) => parseFloat(r.ratio.text))]);
    const missing = claimedRatios.filter((v) => !covered.has(v));
    if (missing.length) {
        throw new Error(`/benchmark leaves out ratios site/claims.json lists: ${missing.join(', ')}. Add each to LEDGER.`);
    }
}

const sourceHref = (source: string) => blob(source);

function Source({ figure }: { figure: Pick<Figure, 'source' | 'reproduce'> }) {
    return (
        <>
            <a href={sourceHref(figure.source)} target="_blank" rel="noopener noreferrer" className="link break-all">
                {figure.source}
            </a>
            <code className="block mt-1 font-mono text-caption text-faint break-all">{figure.reproduce}</code>
        </>
    );
}

function code(text: string) {
    return text.split('`').map((part, i) =>
        i % 2 === 1 ? (
            <code key={i} className="font-mono text-code-inline text-body">
                {part}
            </code>
        ) : (
            part
        ),
    );
}

const METHOD = [
    {
        decision: 'Real, recognizable repos',
        why: 'requests, click, flask and rich, pinned to release SHAs. Anyone can check out the commit and audit. No vendor fixture, no repos picked for being easy.',
    },
    {
        decision: 'Objective gold, no LLM judge',
        why: "Each query's gold file is the definition site of a named symbol, verifiable with one ripgrep command. A backend answers if and only if the gold file lands in its assembled context. Nothing to rig.",
    },
    {
        decision: 'Cost and correctness together',
        why: 'The headline is always recall at N× fewer tokens, never a lone ratio. A token-reduction number with no correctness number attached is meaningless.',
    },
    {
        decision: 'Strong baselines, disclosed',
        why: 'Not just whole-file dumps. A keyword baseline (ripgrep) and a vector baseline that returns the top 8 entries of NeuralMind’s own vector index — in effect, NeuralMind’s retrieval core in isolation. It sends a symbol’s name, module and docstring, not its code, so its token count is a floor: a chunk RAG that sends code bodies would pay more.',
    },
    {
        decision: 'Pre-registered queries',
        why: 'Every query is committed to the manifest before tuning, and every one is reported. Losses are shown, not dropped.',
    },
    {
        decision: 'Deterministic per machine',
        why: 'Synapse injection is off, the repos are pinned and nothing is sampled, so a re-run on the same machine is byte-identical. Across machines, recall and found-rate have come back identical. On the GitHub-hosted CI runners without AVX-512, token counts shift slightly, by up to 0.8% on a per-repo mean in this run, and so does the vector-RAG baseline’s MRR on click; an Apple M3, also without AVX-512, matched the committed run exactly.',
    },
];

function ResultTable({ repo }: { repo: RepoResult }) {
    return (
        <div className="overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0">
            <table className="data-table min-w-[34rem]">
                <caption className="sr-only">
                    {repo.name} at commit {repo.sha} — {repo.queries} pre-registered queries
                </caption>
                <thead>
                    <tr>
                        <th scope="col">Backend</th>
                        <th scope="col" className="num">Recall</th>
                        <th scope="col" className="num">Found</th>
                        <th scope="col" className="num">Tokens/query</th>
                        <th scope="col" className="num">MRR</th>
                    </tr>
                </thead>
                <tbody>
                    {repo.rows.map((row) => {
                        const nm = row.backend === 'neuralmind';
                        return (
                            <tr key={row.backend} className={nm ? 'is-ours' : undefined}>
                                <th scope="row">{row.backend}</th>
                                <td className={`num ${nm ? 'font-semibold' : ''}`}>{row.recall}</td>
                                <td className="num">{row.found}</td>
                                <td className={`num ${nm ? 'font-semibold' : ''}`}>{row.tokens}</td>
                                <td className="num">{row.mrr}</td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

export default function BenchmarkPage() {
    const vsGrep = ratioRange(31, 67);
    const vsPaste = ratioRange(51, 242);
    const grep = headline('ripgrep (query keywords');
    const pilot = taskOutcomePilot.figures;
    const usd = (v: number) => `$${v.toFixed(3)}`;
    const hermes = taskOutcomeHermes.figures;
    // The fewest one-sided tasks, all one way, that reach the pre-registered
    // p < 0.05 in an exact one-sided McNemar test (0.5^n < 0.05).
    const mcnemarFloor = Math.ceil(Math.log(0.05) / Math.log(0.5));

    // Where the bare vector baseline beats NeuralMind, read off the run.
    const row = (r: RepoResult, b: string) => r.rows.find((x) => x.backend === b)!;
    const ragRanksHigher = publicBenchmark.repos.filter((r) => parseFloat(row(r, 'embedding-rag').mrr) > parseFloat(row(r, 'neuralmind').mrr));
    const ragCheaper = publicBenchmark.repos.filter(
        (r) => parseFloat(row(r, 'embedding-rag').tokens.replace(/,/g, '')) < parseFloat(row(r, 'neuralmind').tokens.replace(/,/g, '')),
    );
    const list = (xs: string[]) => (xs.length > 1 ? `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}` : xs[0] ?? '');

    return (
        <>
            <Navbar />
            <main className="max-w-5xl mx-auto px-4 md:px-6 pt-32 pb-16">
                <script
                    type="application/ld+json"
                    dangerouslySetInnerHTML={{
                        __html: JSON.stringify({
                            '@context': 'https://schema.org',
                            '@type': 'Dataset',
                            name: 'NeuralMind public retrieval benchmark',
                            description:
                                'Gold-file recall and token cost for four retrieval backends across 40 pre-registered queries on four pinned open-source Python repositories (requests, click, flask, rich). Reproducible from a fresh clone: recall and found-rate exactly; token counts exactly on the same machine and within 0.8% per repo across the machines compared.',
                            url: 'https://neuralmind.uk/benchmark/',
                            license: 'https://opensource.org/licenses/MIT',
                            isAccessibleForFree: true,
                            creator: { '@type': 'Person', name: 'Darren Frost', url: 'https://github.com/dfrostar' },
                            publisher: { '@type': 'Organization', name: 'NeuralMind', url: 'https://neuralmind.uk' },
                            measurementTechnique:
                                'Definition-site oracle: a backend answers a query if and only if the gold file — the definition site of a named symbol, verified with ripgrep against the pinned commit — appears in its assembled context. No LLM judge.',
                            variableMeasured: [
                                { '@type': 'PropertyValue', name: 'gold-file recall', description: 'Share of a query’s gold files present in the assembled context.' },
                                { '@type': 'PropertyValue', name: 'found-rate', description: 'Share of queries where every gold file was retrieved.' },
                                { '@type': 'PropertyValue', name: 'mean tokens per query', unitText: 'tokens', description: 'Context size measured with tiktoken o200k_base.' },
                                { '@type': 'PropertyValue', name: 'MRR', description: 'Mean reciprocal rank of the gold file.' },
                            ],
                            distribution: [
                                { '@type': 'DataDownload', encodingFormat: 'application/json', contentUrl: RESULTS_JSON },
                            ],
                            citation: PUBLIC_MD,
                        }),
                    }}
                />

                {/* Header */}
                <header className="mb-12 pb-8 border-b border-carbon-border">
                    <div className="flex flex-wrap items-center gap-3 mb-4">
                        <EvidenceBadge level={grep.evidence} />
                        <span className="text-faint text-sm">
                            {publicBenchmark.repoNames.length} pinned repos, {publicBenchmark.total} pre-registered queries
                        </span>
                    </div>
                    <h1 className="font-display text-3xl md:text-display font-bold text-white mb-5 leading-display tracking-tighter">
                        The public benchmark
                    </h1>
                    <p className="text-lg text-body leading-relaxed mb-6">
                        How much context different approaches put in an agent&rsquo;s window to answer a
                        real code question, and whether the objectively correct file makes it in. Cost
                        and correctness are reported together, because a token-reduction number with no
                        correctness number attached is meaningless.
                    </p>
                    <p className="text-muted leading-relaxed">
                        Every query was registered before tuning, every miss is published, and every
                        number on this page is read from the committed run or from{' '}
                        <a href={blob('site/claims.json')} target="_blank" rel="noopener noreferrer" className="link">
                            site/claims.json
                        </a>{' '}
                        when the site is built.
                    </p>
                </header>

                {/* Reproduce */}
                <section className="mb-14">
                    <h2 className="font-display text-xl font-bold text-white mb-4">Rerun it yourself</h2>
                    <div className="rounded-card border border-carbon-border bg-carbon-card overflow-x-auto">
                        <pre className="font-mono text-caption leading-relaxed text-body p-5 whitespace-pre">
{`git clone `}<span className="text-ink">https://github.com/dfrostar/neuralmind</span>{` && cd neuralmind
pip install -e . tiktoken                            `}<span className="text-faint"># source checkout ships the harness</span>{`
NEURALMIND_ORT_THREADS=1 python -m evals.public.run  `}<span className="text-faint"># clones the pinned repos, prints the table</span>
                        </pre>
                    </div>
                    <p className="text-muted text-sm mt-4 leading-relaxed">
                        The harness lives in the source tree, not the PyPI wheel, so run it from a clone.
                        The repos are cloned at fixed commit SHAs and nothing in the run is random, so
                        recall and found-rate should match the tables below exactly. Token counts
                        can shift slightly between machines — CI runners without AVX-512 land up to
                        0.8% off on a per-repo mean;{' '}
                        <code className="font-mono text-code-inline text-body">NEURALMIND_ORT_THREADS=1</code> matches
                        CI&rsquo;s setup (
                        <a href={`${PUBLIC_MD}#how-exactly-a-re-run-reproduces`} target="_blank" rel="noopener noreferrer" className="link">
                            what moves, and the evidence
                        </a>
                        ). Raw per-query data is committed in{' '}
                        <a href={RESULTS_JSON} target="_blank" rel="noopener noreferrer" className="link">
                            bench/public/results.json
                        </a>
                        ; the query set is in{' '}
                        <a href={MANIFEST} target="_blank" rel="noopener noreferrer" className="link">
                            evals/public/manifest.json
                        </a>.
                    </p>
                </section>

                {/* Headline */}
                <section className="mb-14">
                    <h2 className="font-display text-xl font-bold text-white mb-2">What it comes to</h2>
                    <p className="text-muted mb-6 leading-relaxed">
                        Two kinds of result, side by side: retrieval, where NeuralMind gets the right code into
                        the window in far fewer tokens, and task outcomes, where a pre-registered pilot found it
                        made no difference.
                    </p>
                    <div className="grid lg:grid-cols-2 gap-6 items-start">
                        <div className="min-w-0">
                            <p className="label mb-3">Retrieval: what reaches the window</p>
                            <StatGrid className="grid-cols-2">
                                <Stat
                                    label="Gold file found"
                                    value={publicBenchmark.found('neuralmind')}
                                    note={`Keyword ripgrep, top five files whole: ${publicBenchmark.found('ripgrep')}.`}
                                    evidence={grep.evidence}
                                />
                                <Stat
                                    label="Fewer tokens vs ripgrep"
                                    value={vsGrep.text}
                                    note="The baseline closest to how an agent works."
                                    evidence={vsGrep.evidence}
                                />
                                <Stat
                                    label="Vs pasting every file"
                                    value={vsPaste.text}
                                    note={`${publicBenchmark.tokenRange('neuralmind')} mean tokens per question against ${publicBenchmark.tokenRange('full-file')}.`}
                                    evidence={vsPaste.evidence}
                                />
                                <Stat
                                    label="Top-5 hit rate"
                                    value={retrievalEval.hitAt5}
                                    note={`${retrievalEval.questions} questions on ${retrievalEval.repos} repos; ${retrievalEval.misses} misses, listed.`}
                                    evidence={retrievalEval.evidence}
                                />
                            </StatGrid>
                        </div>
                        <div className="min-w-0">
                            <p className="label mb-3">Task outcomes: does the agent do better</p>
                            <StatGrid className="grid-cols-2">
                                <Stat
                                    label="Tasks solved"
                                    value={`${pilot.tasks_solved.baseline} vs ${pilot.tasks_solved.neuralmind}`}
                                    note={`Of ${pilot.tasks}, without and with NeuralMind.`}
                                    evidence={taskOutcomePilot.evidence}
                                />
                                <Stat
                                    label="Cost per task"
                                    value={pilot.median_cost_change}
                                    note={`Median change with NeuralMind; 95% CI ${pilot.cost_change_ci95}.`}
                                    evidence={taskOutcomePilot.evidence}
                                />
                                <Stat
                                    label="Runs solved"
                                    value={`${pilot.runs_solved.baseline} vs ${pilot.runs_solved.neuralmind}`}
                                    note={`Of ${pilot.runs / 2} each, without and with.`}
                                    evidence={taskOutcomePilot.evidence}
                                />
                                <Stat
                                    label="NeuralMind tool calls"
                                    value={String(pilot.mcp_tool_calls)}
                                    note={`In ${pilot.runs / 2} runs with its ${pilot.mcp_tools_listed} MCP tools available.`}
                                    evidence={taskOutcomePilot.evidence}
                                />
                            </StatGrid>
                            <p className="mt-3 text-sm">
                                <a href="#task-outcomes" className="link">
                                    What the pilot found, and why
                                </a>
                            </p>
                        </div>
                    </div>
                </section>

                {/* Task outcomes */}
                <section id="task-outcomes" className="mb-14 scroll-mt-24">
                    <div className="flex flex-wrap items-center gap-3 mb-2">
                        <h2 className="font-display text-xl font-bold text-white">Task outcomes: a pilot found no difference</h2>
                        <EvidenceBadge level={taskOutcomePilot.evidence} />
                    </div>
                    <p className="text-muted mb-5 leading-relaxed">
                        Fewer tokens in the window isn&rsquo;t the same as a cheaper or better agent, so we
                        pre-registered a task-outcome benchmark and ran its pilot on {pilot.date}:{' '}
                        {pilot.tasks} real bug-fix tasks, Claude Code with and without NeuralMind, {pilot.seeds}{' '}
                        seeds each, {pilot.runs} runs. The claim it tested, that NeuralMind lowers cost per task
                        without solving fewer, is not supported.
                    </p>
                    <div className="overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0 mb-5">
                        <table className="data-table min-w-[30rem]">
                            <caption className="sr-only">Task-outcome pilot, baseline against NeuralMind</caption>
                            <thead>
                                <tr>
                                    <th scope="col">Per arm</th>
                                    <th scope="col" className="num">Without</th>
                                    <th scope="col" className="num">With NeuralMind</th>
                                </tr>
                            </thead>
                            <tbody>
                                {[
                                    ['Tasks solved', pilot.tasks_solved, (v: number) => `${v} of ${pilot.tasks}`],
                                    ['Runs solved', pilot.runs_solved, (v: number) => `${v} of ${pilot.runs / 2}`],
                                    ['Cost per solved task', pilot.cost_per_solved_task_usd, usd],
                                    ['Median turns per task', pilot.median_turns, String],
                                    ['Median explore calls before the first edit', pilot.median_explore_calls_before_first_edit, String],
                                ].map(([label, pair, fmt]) => {
                                    const p = pair as { baseline: number; neuralmind: number };
                                    const f = fmt as (v: number) => string;
                                    return (
                                        <tr key={label as string}>
                                            <th scope="row">{label as string}</th>
                                            <td className="num">{f(p.baseline)}</td>
                                            <td className="num">{f(p.neuralmind)}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                    <div className="space-y-4">
                        <Callout variant="caution" title="Why: the agent never asked">
                            In the {pilot.runs / 2} runs with NeuralMind, the agent called none of the{' '}
                            {pilot.mcp_tools_listed} MCP tools the server listed. It explored the code itself, as it
                            did without NeuralMind ({pilot.median_explore_calls_before_first_edit.neuralmind} explore
                            calls before the first edit in both arms). NeuralMind reached it only through its Claude
                            Code hooks, which ran in every one of those runs. Better retrieval doesn&rsquo;t help an
                            agent that never asks for it, and that, not retrieval quality, is what the pilot measured.
                        </Callout>
                        <Callout variant="note" title="What it can and can’t show">
                            It&rsquo;s a pilot: {pilot.tasks} tasks, one repository (NeuralMind&rsquo;s own), one agent
                            and model ({pilot.model}, Claude Code {pilot.claude_code}, NeuralMind {pilot.neuralmind}),
                            a cold index each run, and cost as Claude Code&rsquo;s estimate at API prices. It can rule
                            out a large saving (the interval excludes the 15% reduction the confirmatory run is sized
                            for), not a small one. The confirmatory run follows the same spec on new tasks, and is
                            published the same way, whatever it shows.
                        </Callout>
                    </div>
                    <p className="mt-4 text-sm flex flex-wrap gap-x-6 gap-y-2">
                        <a href={blob(taskOutcomePilot.source)} target="_blank" rel="noopener noreferrer" className="link">
                            Analyzer report
                        </a>
                        <a href={blob('bench/task_outcome/pilot/runs.jsonl')} target="_blank" rel="noopener noreferrer" className="link">
                            All {pilot.runs} runs
                        </a>
                        <a href={blob(taskOutcomePilot.spec)} target="_blank" rel="noopener noreferrer" className="link">
                            Pre-registered spec
                        </a>
                    </p>

                    <div id="task-outcomes-hermes" className="mt-12 scroll-mt-24">
                        <div className="flex flex-wrap items-center gap-3 mb-2">
                            <h3 className="font-display text-lg font-bold text-white">
                                The same tasks on a local model: {hermes.tasks_solved.neuralmind} vs{' '}
                                {hermes.tasks_solved.baseline}, not significant
                            </h3>
                            <EvidenceBadge level={taskOutcomeHermes.evidence} />
                        </div>
                        <p className="text-muted mb-5 leading-relaxed">
                            A second, separate pilot ran the same {hermes.tasks} tasks with a different agent:
                            Hermes-Agent v{hermes.hermes} driving {hermes.model} on one local GPU, {hermes.seeds}{' '}
                            seeds per arm, {hermes.runs} runs, finished {hermes.date}. NeuralMind reached it only
                            through its Hermes plugin (a context block on every prompt, the session recap, edit
                            learning); neither arm had an MCP server. A local model costs nothing per call, so the
                            primary endpoint is tasks solved. The claim it tested, that the model solves more of
                            these tasks with NeuralMind, is not supported.
                        </p>
                        <div className="overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0 mb-5">
                            <table className="data-table min-w-[30rem]">
                                <caption className="sr-only">Hermes pilot, baseline against NeuralMind</caption>
                                <thead>
                                    <tr>
                                        <th scope="col">Per arm</th>
                                        <th scope="col" className="num">Without</th>
                                        <th scope="col" className="num">With NeuralMind</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {[
                                        [`Tasks solved (most of ${hermes.seeds} seeds)`, hermes.tasks_solved, (v: number) => `${v} of ${hermes.tasks}`],
                                        ['Runs solved', hermes.runs_solved, (v: number) => `${v} of ${hermes.runs / 2}`],
                                        ['Median minutes per task', hermes.median_minutes, String],
                                        ['Median turns per task', hermes.median_turns, String],
                                        ['Runs that hit the timeout', hermes.runs_timed_out, String],
                                    ].map(([label, pair, fmt]) => {
                                        const p = pair as { baseline: number; neuralmind: number };
                                        const f = fmt as (v: number) => string;
                                        return (
                                            <tr key={label as string}>
                                                <th scope="row">{label as string}</th>
                                                <td className="num">{f(p.baseline)}</td>
                                                <td className="num">{f(p.neuralmind)}</td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                        <div className="space-y-4">
                            <Callout variant="note" title="Why two tasks aren’t enough">
                                {hermes.tasks_solved_by_one_arm_only.neuralmind} tasks were solved with NeuralMind
                                alone and {hermes.tasks_solved_by_one_arm_only.baseline} without it alone (one-sided
                                McNemar p = {hermes.mcnemar_p}), the lowest p that many can give. The pre-registered
                                test needs at least {mcnemarFloor}, all one way, to reach p &lt; 0.05. Tokens per task
                                changed by a median {hermes.median_tokens_change} with NeuralMind (95% CI{' '}
                                {hermes.tokens_change_ci95}): no measurable difference.
                            </Callout>
                            <Callout variant="caution" title="What it can and can’t show">
                                It&rsquo;s a pilot: {hermes.tasks} tasks from one repository (NeuralMind&rsquo;s own),
                                one model on one GPU, a fresh index each run (Hermes-Agent v{hermes.hermes},{' '}
                                {hermes.model}, NeuralMind {hermes.neuralmind}). In{' '}
                                {hermes.runs_judged_with_an_agent_command_running} of the {hermes.runs} runs, a
                                command the agent had started, usually the whole test suite, was still running when the
                                hidden tests judged the fix. The verdicts stand as recorded, and the harness now stops
                                such commands first. The machine&rsquo;s scheduled Hermes jobs were paused partway
                                through, with both arms run on both sides of the pause, which can move the minutes.
                            </Callout>
                        </div>
                        <p className="mt-4 text-sm flex flex-wrap gap-x-6 gap-y-2">
                            <a href={blob(taskOutcomeHermes.source)} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">
                                Analyzer report →
                            </a>
                            <a href={blob('bench/task_outcome/hermes-pilot/runs.jsonl')} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">
                                All {hermes.runs} runs →
                            </a>
                            <a href={blob(taskOutcomeHermes.spec)} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">
                                Pre-registered spec →
                            </a>
                        </p>
                    </div>
                </section>

                {/* Method */}
                <section className="mb-14">
                    <h2 className="font-display text-xl font-bold text-white mb-2">How it is built to be hard to dismiss</h2>
                    <p className="text-muted mb-6 leading-relaxed">
                        Six design decisions, each aimed at a specific way a vendor benchmark usually
                        fails.
                    </p>
                    <dl className="divide-y divide-carbon-border border-y border-carbon-border">
                        {METHOD.map((m) => (
                            <div key={m.decision} className="py-4 grid md:grid-cols-[13rem_1fr] gap-2 md:gap-6">
                                <dt className="text-white font-semibold text-sm">{m.decision}</dt>
                                <dd className="text-muted text-sm leading-relaxed">{m.why}</dd>
                            </div>
                        ))}
                    </dl>
                </section>

                {/* Results */}
                <section className="mb-14">
                    <h2 className="font-display text-xl font-bold text-white mb-2">Results, per repo</h2>
                    <p className="text-muted mb-8 leading-relaxed">
                        Tokenizer: <code className="font-mono text-code-inline text-body">{publicBenchmark.tokenizer}</code>.
                        Token counts are shown for every backend rather than a ratio, so the columns
                        compare directly, including where NeuralMind is the more expensive one.
                    </p>

                    <div className="space-y-10">
                        {publicBenchmark.repos.map((repo) => (
                            <article key={repo.name}>
                                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-1">
                                    <h3 className="font-mono text-base text-white">{repo.name}</h3>
                                    <span className="font-mono text-xs text-faint">@ {repo.sha}</span>
                                    <span className="text-faint text-sm">{repo.queries} queries</span>
                                    <span className="ml-auto font-mono text-sm text-proton">{repo.ratio.text} fewer tokens</span>
                                </div>
                                {REPO_NOTES[repo.name] && (
                                    <p className="text-muted text-sm mb-3 leading-relaxed">{REPO_NOTES[repo.name]}</p>
                                )}
                                <ResultTable repo={repo} />
                            </article>
                        ))}
                    </div>
                </section>

                {/* Where it loses */}
                <section id="where-it-loses" className="mb-14 scroll-mt-24">
                    <h2 className="font-display text-xl font-bold text-white mb-2">Where NeuralMind loses</h2>
                    <p className="text-muted mb-6 leading-relaxed">
                        Two loss modes, reported plainly. A benchmark that never reports a loss is not
                        evidence, it is advertising.
                    </p>
                    <div className="space-y-4">
                        <Callout variant="caution" title={`1 — Misses beyond these ${publicBenchmark.total} queries`}>
                            This run finds every gold file, but {publicBenchmark.total} queries is a small sample,
                            every earlier run had at least one miss, and the next code change can bring one back.
                            On the larger {retrievalEval.questions}-question retrieval eval ({retrievalEval.repos} repos,
                            including NeuralMind&rsquo;s own), the same build misses the gold file in the top five
                            on {retrievalEval.misses} questions, listed in{' '}
                            <a href={blob(retrievalEval.source)} target="_blank" rel="noopener noreferrer" className="link">
                                {retrievalEval.source}
                            </a>
                            . On NeuralMind&rsquo;s own repository, four of its six misses are files vector search
                            ranks outside the 20 candidates NeuralMind re-ranks.
                        </Callout>
                        <Callout variant="caution" title="2 — Token cost against a bare vector index">
                            The <code className="font-mono text-code-inline text-body">embedding-rag</code> baseline is the
                            top 8 entries of NeuralMind&rsquo;s own vector index, nothing added. It is cheaper on{' '}
                            {ragCheaper.length === publicBenchmark.repos.length ? `all ${ragCheaper.length} repos` : list(ragCheaper.map((r) => r.name))}
                            {ragRanksHigher.length > 0 && (
                                <>
                                    , and it still ranks the gold file higher on{' '}
                                    {list(
                                        ragRanksHigher.map(
                                            (r) => `${r.name} (MRR ${row(r, 'embedding-rag').mrr} against ${row(r, 'neuralmind').mrr})`,
                                        ),
                                    )}
                                </>
                            )}
                            . NeuralMind&rsquo;s recall is at or above it on every repo. Its token count is a floor:
                            it sends a symbol&rsquo;s name, module and docstring, not its code, where NeuralMind
                            spends the difference on a structured context (project map, the query&rsquo;s other
                            candidates, eight ranked hits) meant for answering rather than locating. If locating a
                            file is all you need, a bare vector index is cheaper.
                        </Callout>
                    </div>
                </section>

                {/* Not measured */}
                <section className="mb-14">
                    <h2 className="font-display text-xl font-bold text-white mb-4">What this does not measure</h2>
                    <Callout variant="not-measured">
                        <ul className="space-y-3">
                            {disclosures.map((d) => (
                                <li key={d.claim}>{d.claim}.</li>
                            ))}
                            <li>
                                End-to-end answer quality. Gold-file recall is deliberately a findability metric:
                                objective, no judge. An opt-in answerability arm grades real answers built from each
                                backend&rsquo;s window, with every transcript committed, but it is LLM-judged, so it
                                stays a labelled secondary signal and never the headline.
                            </li>
                            <li>
                                The synapse layer, in this run: its weights learn from how you work, so they
                                can&rsquo;t be part of a fixed public number, and injection is off above. CI asserts
                                its direction on a fixture;{' '}
                                <code className="font-mono text-code-inline text-body">neuralmind eval . --synapse-ab</code>{' '}
                                measures it on your repo.
                            </li>
                        </ul>
                    </Callout>
                </section>

                {/* Ledger */}
                <section id="every-number" className="mb-14 scroll-mt-24">
                    <h2 className="font-display text-xl font-bold text-white mb-2">Every number the site quotes</h2>
                    <p className="text-muted mb-6 leading-relaxed">
                        Rendered from{' '}
                        <a href={blob('site/claims.json')} target="_blank" rel="noopener noreferrer" className="link">
                            site/claims.json
                        </a>
                        , the file CI holds every page to: each figure with the kind of evidence it is, where it
                        was measured, and the command that reproduces it.
                    </p>
                    <div className="overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0">
                        <table className="data-table min-w-[44rem]">
                            <caption className="sr-only">Every ratio in site/claims.json, with its evidence level, source and reproduction command</caption>
                            <thead>
                                <tr>
                                    <th scope="col">Figure</th>
                                    <th scope="col">What it is</th>
                                    <th scope="col">Evidence</th>
                                    <th scope="col">Source and reproduce command</th>
                                </tr>
                            </thead>
                            <tbody>
                                {LEDGER.map((l) => (
                                    <tr key={l.figure.text}>
                                        <th scope="row" className="whitespace-nowrap">{l.figure.text}</th>
                                        <td>{code(l.what)}</td>
                                        <td>
                                            <EvidenceBadge level={l.figure.evidence} />
                                        </td>
                                        <td className="text-caption">
                                            <Source figure={l.figure} />
                                        </td>
                                    </tr>
                                ))}
                                {quotableClaims.map((c) => (
                                    <tr key={c.claim}>
                                        <th scope="row">—</th>
                                        <td>{c.claim}</td>
                                        <td>
                                            <EvidenceBadge level={c.evidence} />
                                        </td>
                                        <td className="text-caption">
                                            <Source figure={c} />
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>

                {/* Close */}
                <section className="rounded-card panel-accent p-6 md:p-7">
                    <h2 className="font-display text-lg font-semibold tracking-tight text-white mb-2">Run it on your own repo</h2>
                    <p className="text-muted text-sm leading-relaxed mb-4">
                        These four repos are public so the numbers can be audited. The number that decides
                        anything for you is the one from your codebase:{' '}
                        <code className="font-mono text-code-inline text-body">neuralmind benchmark .</code> prints it.
                    </p>
                    <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
                        <a href={PUBLIC_MD} target="_blank" rel="noopener noreferrer" className="link">
                            Full methodology and corpus notes
                        </a>
                        <a href="/measure-your-own/" className="link">
                            How to measure your own
                        </a>
                        <a href="/field-reports/measure-memory-across-a-refactor/" className="link">
                            A single-repo field report
                        </a>
                    </div>
                </section>
            </main>
            <Footer />
        </>
    );
}
