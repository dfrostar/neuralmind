import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import Callout from '@/components/ui/Callout';
import EvidenceBadge from '@/components/ui/EvidenceBadge';
import Icon, { type IconName } from '@/components/ui/Icon';
import { headline, publicBenchmark, ratioRange, retrievalEval, taskOutcomePilot } from '@/lib/evidence';
import { getLatestRelease, tagAtLeast } from '@/lib/release';
import { pageMetadata } from '@/lib/seo';
import { withCode } from '@/lib/ticks';
import type { Metadata } from 'next';

export const metadata: Metadata = pageMetadata({
    path: '/whats-new',
    title: 'What’s New in NeuralMind',
    description:
        'Recent NeuralMind releases, and the guards that keep an agent’s changes consistent with your code: drift checks, stale decisions, blast radius.',
    keywords: [
        'NeuralMind release notes',
        'NeuralMind changelog',
        'code drift detection',
        'AI agent technical debt',
        'pattern drift pre-commit',
        'stale decision guard',
        'blast radius before a rename',
        'MCP server instructions',
    ],
    ogTitle: 'What’s new in NeuralMind',
    ogDescription:
        'What recent releases added, and how NeuralMind keeps an agent’s changes consistent with the code you already have.',
});

const DOCS = 'https://docs.neuralmind.uk';
const notes = (v: string) => `${DOCS}/releases/RELEASE_NOTES_v${v}.html`;
const link = 'text-electric hover:text-electric-bright transition-colors';

// What each guard does, said as what the code does. None of these carries a
// measured outcome: the one study of agent outcomes (the task-outcome pilot)
// found no difference, and the page says so below rather than implying one.
const guards: { name: string; since: string; body: string; cmd: string; href: string; doc: string }[] = [
    {
        name: 'A change that skips its siblings’ pattern is flagged before commit',
        since: '3.2.0',
        body: '`neuralmind drift` maps your staged diff onto the code graph, groups each changed function with its siblings, and flags one that leaves out something most of them do: the tenth handler that forgot the auth check the other nine make. Only code in the diff is judged. `neuralmind init-hook` wires it into `pre-commit`; it warns by default, and `--strict` blocks.',
        cmd: 'neuralmind drift . --staged',
        href: `${DOCS}/use-cases/review-before-push.html`,
        doc: 'Review before push',
    },
    {
        name: 'Decisions go stale when their code changes',
        since: '4.6.0',
        body: 'Record why the code is the way it is, with the files the decision governs. When a commit changes one of those files the decision is marked STALE, and the agent is warned before it edits. A reversed decision can be retracted so it stops reaching the agent (v4.16.0+).',
        cmd: 'neuralmind decisions record --title "Hash tokens before storing" --rationale "Leaked DB dumps" --files auth/tokens.py',
        href: `${DOCS}/use-cases/decision-memory-across-commits.html`,
        doc: 'Decision memory across commits',
    },
    {
        name: 'See what a change touches before you make it',
        since: '0.52.0',
        body: '`neuralmind impact` lists every caller, importer and subclass of a symbol from the static code graph, so a rename or a signature change reaches all of them instead of breaking the ones nobody remembered.',
        cmd: 'neuralmind impact verify_session',
        href: `${DOCS}/use-cases/blast-radius-before-a-rename.html`,
        doc: 'Blast radius before a rename',
    },
    {
        name: 'The files you usually change together, before you push',
        since: '0.39.0',
        body: '`neuralmind review` reads your diff and lists files that have been edited together with the ones you changed but are not in this diff, from what the synapse layer learned on your project.',
        cmd: 'neuralmind review . --base main',
        href: `${DOCS}/wiki/CLI-Reference.html#review-v0390`,
        doc: 'Co-change review in the CLI reference',
    },
    {
        name: 'Context that says when it is out of date',
        since: '4.17.0',
        body: 'Answers from a stale index carry one line saying so: when commits since the last build changed the project, or the background rebuild failed. Since v4.13.0 the index also rebuilds after pulls, merges, branch switches and rebases, not only after your own commits.',
        cmd: 'neuralmind init-hook .',
        href: `${DOCS}/use-cases/recover-from-a-stale-graph.html`,
        doc: 'Recover from a stale graph',
    },
];

// v4.16 to v4.23 on one screen, the same releases as the list below grouped
// by who they're for, the newest group first and full width. The evidence
// panel under these renders its numbers from lib/evidence, so a re-run
// benchmark changes them here too.
const glance: {
    title: string;
    icon: IconName;
    items: { text: string; version: string }[];
    note?: string;
    wide?: boolean;
}[] = [
    {
        title: 'The prompt block points at the code',
        icon: 'recall',
        items: [
            { text: 'The code comes before its tests, unless the prompt names a test', version: '4.23.0' },
            { text: 'A test that matches the prompt brings the code it tests', version: '4.23.0' },
            { text: 'The prompt hook answers within the Hermes plugin’s time limit on a large index', version: '4.23.0' },
        ],
        note: 'Measured offline, not in agent runs. The release notes give the numbers.',
        wide: true,
    },
    {
        title: 'AI agents on CUI code',
        icon: 'shield-check',
        items: [
            { text: 'One setting for the hardened configuration: `security.profile: cui`', version: '4.16.0' },
            { text: 'Signed audit checkpoints', version: '4.16.0' },
            { text: 'Audit records to syslog as they are written', version: '4.19.0' },
            { text: '`neuralmind hardening` checks a 17-rule baseline', version: '4.19.0' },
            { text: '`neuralmind data-locations` lists where the data is', version: '4.18.0' },
        ],
        note: 'These support controls in your system. Your assessor decides compliance.',
    },
    {
        title: 'Context you can trust',
        icon: 'index',
        items: [
            { text: 'An answer from a stale index says so', version: '4.17.0' },
            { text: 'A feature branch’s calls and memory stay on its branch', version: '4.22.0' },
            { text: '`neuralmind doctor` shows whether anything calls NeuralMind', version: '4.22.0' },
            { text: '`neuralmind demo` runs offline, straight after install', version: '4.19.0' },
        ],
    },
];

// Newest first. `version` decides the label: a release the build can't find
// yet shows as the next release, judged against the latest tag (no version is
// hardcoded on the page).
const releases: { version: string; title: string; points: string[] }[] = [
    {
        version: '4.23.0',
        title: 'The prompt block points at the code, not its tests',
        points: [
            'The block an agent gets with each prompt lists the code before its tests, unless the prompt names a test, and its excerpt quotes code. A prompt that only says how to run the tests no longer puts test files first.',
            'A test file that matches the prompt brings the code it tests into the block, found by name: `test_x.py` tests `x.py`.',
            'On a large index the prompt hook now answers within the Hermes plugin’s time limit. The loaded graph is cached, so a turn no longer reloads it from scratch.',
            'Measured offline, not in agent runs: the block by replaying it on held-out tasks, the hook by timing it. The release notes give the numbers, including where the change didn’t help.',
        ],
    },
    {
        version: '4.22.0',
        title: 'Doctor says whether anything calls NeuralMind',
        points: [
            '`neuralmind doctor` opens with a Wiring section (daemon, Git hooks, Hermes plugin, MCP registration per client), and each warning carries the command that fixes it.',
            '`neuralmind install-mcp --client hermes` registers the MCP server with Hermes-Agent, and a build ends with the commands for whatever isn’t wired yet.',
            'The call and import edges a build finds, and the memory file Claude Code loads, now follow the checkout. A feature branch’s calls no longer show up in recall on `main`.',
        ],
    },
    {
        version: '4.21.0',
        title: 'The MCP server says what it’s for',
        points: [
            'The server’s `initialize` reply tells the agent when to call `neuralmind_search` before Grep, and `tools/list` offers six tools by default instead of 28.',
            'The prompt block an agent gets includes the leading file’s code when one file clearly leads the match.',
            'An exploratory rerun of the pilot’s 20 tasks with this release found the agent’s behaviour unchanged: it still called no NeuralMind tool. The release notes say what it does and doesn’t change.',
            'Intel macOS works again with the default backend; installing there compiles `cryptography`. On Windows on ARM, use WSL 2 or the container image.',
        ],
    },
    {
        version: '4.20.0',
        title: 'Every number on this site, with its evidence',
        points: [
            'One proof page lists every figure the site quotes, where it was measured and the command that reproduces it, including where NeuralMind loses.',
            '/security starts with verifying a release: signed images, build-provenance attestations, SBOM and VEX.',
        ],
    },
    {
        version: '4.19.0',
        title: 'Audit records to your SIEM as they are written',
        points: [
            'Every audit record goes to syslog right after it is written, with an alert when one can’t be written.',
            'An OSCAL component definition for SP 800-53, and `neuralmind hardening`, which checks a host against a 17-rule baseline.',
            '`neuralmind demo` runs offline, straight after `pip install`.',
        ],
    },
    {
        version: '4.18.0',
        title: 'Every place NeuralMind keeps data',
        points: [
            '`neuralmind data-locations` lists everything NeuralMind writes for a project, in it and outside it, with the command that removes each.',
        ],
    },
    {
        version: '4.17.0',
        title: 'An answer from a stale index says so',
        points: ['Query, search and prompt context carry one line when the index is behind the code.'],
    },
    {
        version: '4.16.0',
        title: 'The CUI-enclave posture as one setting',
        points: [
            '`security.profile: cui` turns on OS-account identity, encrypted-storage checks and loopback-only serving together, and signed checkpoints make an audit log you can’t silently shorten.',
            'A reversed decision can be retracted so it stops reaching the agent.',
        ],
    },
    {
        version: '4.14.0',
        title: 'Check the learning on your own repo, and verify what you install',
        points: [
            '`neuralmind eval . --synapse-ab` runs your own questions with the synapse layer on and off and reports what it moved.',
            'Container images are signed, and the image, wheel and sdist carry build-provenance attestations.',
        ],
    },
    {
        version: '4.13.0',
        title: 'The index stays fresh after pulls, merges and rebases',
        points: ['Git hooks rebuild in the background after a pull, merge, branch switch or rebase, so the agent isn’t working from yesterday’s code.'],
    },
];

export default async function WhatsNewPage() {
    const rel = await getLatestRelease();
    const released = (v: string) => tagAtLeast(rel.tag, v);
    const vsGrep = ratioRange(31, 67);
    const pilot = taskOutcomePilot;
    const vsGrepFound = headline('ripgrep (query keywords');
    // The pilot's NeuralMind arm: every task once per seed.
    const pilotRuns = pilot.figures.tasks * pilot.figures.seeds;
    const evalHits = retrievalEval.questions - retrievalEval.misses;

    return (
        <>
            <Navbar />
            <main className="max-w-4xl mx-auto px-4 md:px-6 pt-32 pb-16">
                <header className="mb-12 pb-8 border-b border-carbon-border">
                    <span className="eyebrow block mb-4">What&rsquo;s new</span>
                    <h1 className="font-display text-3xl md:text-display font-bold text-white mb-5 leading-display tracking-tighter">
                        Keep what your agent changes consistent with the code you have
                    </h1>
                    <p className="text-lg text-body leading-relaxed mb-6">
                        An agent working from a partial view of a codebase writes code that drifts from its
                        patterns, ignores decisions made for a reason, and misses the callers a change
                        breaks. That is technical debt someone pays for later. NeuralMind gives the agent the
                        project&rsquo;s structure and history, and checks changes against them. Here is what
                        does that, and what recent releases added.
                    </p>
                    <div className="panel rounded-card p-5 flex items-center justify-between flex-wrap gap-4">
                        <div>
                            <p className="eyebrow mb-1">Latest release</p>
                            <span className="text-electric-bright font-mono font-bold text-xl">{rel.tag}</span>
                            {rel.date && <span className="text-muted ml-3">Released {rel.date}</span>}
                        </div>
                        <div className="flex gap-4 text-sm">
                            <a href={rel.htmlUrl} target="_blank" rel="noopener noreferrer" className={link}>
                                Release notes →
                            </a>
                            <a href={rel.pypiUrl} target="_blank" rel="noopener noreferrer" className={link}>
                                PyPI →
                            </a>
                        </div>
                    </div>
                </header>

                <section id="guards" className="mb-16 scroll-mt-28">
                    <h2 className="font-display text-2xl font-bold text-white mb-2 tracking-tight">
                        Guards against drift and debt
                    </h2>
                    <p className="text-muted leading-relaxed mb-6">
                        Each works on your machine, from your repository, and each has a command that shows it.
                    </p>
                    <div className="space-y-4">
                        {guards.map((g) => (
                            <article key={g.name} className="panel rounded-card p-5 md:p-6">
                                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 mb-2">
                                    <h3 className="font-display text-title-sm font-semibold text-white tracking-tight">{g.name}</h3>
                                    <span className="font-mono text-eyebrow uppercase tracking-eyebrow text-faint">v{g.since}+</span>
                                </div>
                                <p className="text-muted text-sm leading-relaxed mb-4">{withCode(g.body)}</p>
                                <div className="bg-carbon rounded-control border border-carbon-border p-4 font-mono text-xs text-body overflow-x-auto">
                                    <p className="whitespace-nowrap">
                                        <span className="text-faint select-none">$ </span>
                                        {g.cmd}
                                    </p>
                                </div>
                                <a href={g.href} className={`inline-block mt-3 text-sm ${link}`}>
                                    {g.doc} →
                                </a>
                            </article>
                        ))}
                    </div>
                </section>

                <section id="releases" className="mb-16 scroll-mt-28">
                    <h2 className="font-display text-2xl font-bold text-white mb-2 tracking-tight">Recent releases</h2>
                    <p className="text-muted leading-relaxed mb-6">
                        v4.16 to v4.23 at a glance, then every release, newest first, with its full notes.
                    </p>
                    <div id="at-a-glance" className="mb-12 scroll-mt-28">
                        <div className="grid md:grid-cols-2 gap-4 mb-4">
                            {glance.map((g) => (
                                <article
                                    key={g.title}
                                    className={`panel rounded-card p-5 md:p-6 flex flex-col${g.wide ? ' md:col-span-2' : ''}`}
                                >
                                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-4">
                                        <Icon name={g.icon} className="w-6 h-6 text-electric shrink-0" />
                                        <h3 className="font-display text-title-sm font-semibold text-white tracking-tight">
                                            {g.title}
                                        </h3>
                                        {g.items.some((it) => !released(it.version)) && (
                                            <span className="font-mono text-eyebrow uppercase tracking-eyebrow text-faint">
                                                in the next release, on main now
                                            </span>
                                        )}
                                    </div>
                                    <ul className="space-y-3 flex-1">
                                        {g.items.map((it) => (
                                            <li key={it.text} className="flex items-baseline justify-between gap-4 text-sm leading-relaxed">
                                                <span className="text-body">{withCode(it.text)}</span>
                                                <a href={notes(it.version)} className={`font-mono text-eyebrow shrink-0 ${link}`}>
                                                    v{it.version}
                                                </a>
                                            </li>
                                        ))}
                                    </ul>
                                    {g.note && (
                                        <p className="text-faint text-caption mt-5 pt-4 border-t border-carbon-border">{g.note}</p>
                                    )}
                                </article>
                            ))}
                        </div>
                        <article className="panel rounded-card p-5 md:p-6">
                            <div className="flex items-center gap-3 mb-6">
                                <Icon name="dashboard" className="w-6 h-6 text-electric shrink-0" />
                                <h3 className="font-display text-title-sm font-semibold text-white tracking-tight">
                                    Evidence, not adjectives
                                </h3>
                            </div>
                            <div className="grid sm:grid-cols-2 gap-8 mb-6">
                                <div>
                                    <p className="metric text-4xl md:text-5xl font-bold text-proton mb-3">
                                        {publicBenchmark.found('neuralmind')}
                                    </p>
                                    <p className="text-body text-sm leading-relaxed mb-3">
                                        public-benchmark queries where NeuralMind found the file the fix changed.
                                        Keyword search with ripgrep:{' '}
                                        <span className="whitespace-nowrap">{publicBenchmark.found('ripgrep')}</span>.
                                    </p>
                                    <EvidenceBadge level={vsGrepFound.evidence} />
                                </div>
                                <div>
                                    <p className="metric text-4xl md:text-5xl font-bold text-proton mb-3">
                                        {pilot.figures.mcp_tool_calls} of {pilotRuns}
                                    </p>
                                    <p className="text-body text-sm leading-relaxed mb-3">
                                        pilot runs in which the agent called a NeuralMind tool. Cost per task showed no
                                        measurable difference: {pilot.figures.median_cost_change} (95% CI{' '}
                                        {pilot.figures.cost_change_ci95}).
                                    </p>
                                    <EvidenceBadge level={pilot.evidence} />
                                </div>
                            </div>
                            <p className="text-muted text-sm leading-relaxed pt-4 border-t border-carbon-border">
                                On a larger eval the right file is in the top five on{' '}
                                <span className="metric text-proton">
                                    {evalHits} of {retrievalEval.questions}
                                </span>{' '}
                                questions, and all {retrievalEval.misses} misses are published. Getting agents to use what
                                NeuralMind finds is the work now.
                            </p>
                        </article>
                        {/* A dated snapshot: its numbers are as of October 2026, unlike the panel above. */}
                        <p className="text-sm mt-4">
                            <a href="/slides/neuralmind-v4.16-v4.22.pdf" className={link}>
                                v4.16 to v4.22 as 20 slides, October 2026 (PDF) →
                            </a>
                        </p>
                    </div>
                    <ol className="space-y-8">
                        {releases.map((r) => (
                            <li key={r.version} className="pl-5 border-l border-carbon-border">
                                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-2">
                                    <span className="font-mono font-bold text-electric-bright">v{r.version}</span>
                                    {!released(r.version) && (
                                        <span className="font-mono text-eyebrow uppercase tracking-eyebrow text-faint">
                                            in the next release, on main now
                                        </span>
                                    )}
                                </div>
                                <h3 className="font-display text-title-sm font-semibold text-white tracking-tight mb-2">{r.title}</h3>
                                <ul className="space-y-2 mb-2">
                                    {r.points.map((p) => (
                                        <li key={p} className="text-muted text-sm leading-relaxed">
                                            {withCode(p)}
                                        </li>
                                    ))}
                                </ul>
                                <a href={notes(r.version)} className={`text-sm ${link}`}>
                                    v{r.version} release notes →
                                </a>
                            </li>
                        ))}
                    </ol>
                    <p className="text-muted text-sm mt-8">
                        Older releases:{' '}
                        <a href={`${DOCS}/about.html`} className={link}>
                            the full history
                        </a>
                        .
                    </p>
                </section>

                <section id="evidence" className="mb-16 scroll-mt-28">
                    <h2 className="font-display text-2xl font-bold text-white mb-2 tracking-tight">
                        What&rsquo;s measured, and what isn&rsquo;t
                    </h2>
                    <div className="space-y-4">
                        <Callout variant="evidence" title="Measured: the right code, in less context">
                            <p className="mb-2">
                                On the public benchmark NeuralMind finds the file a fix changed on{' '}
                                {publicBenchmark.found('neuralmind')} queries, where keyword ripgrep opening its top
                                five files whole finds {publicBenchmark.found('ripgrep')}, at {vsGrep.text} fewer
                                tokens. Forty queries is a small sample: on the {retrievalEval.questions}-question
                                retrieval eval the right file is in the top five for {retrievalEval.hitAt5}, and the{' '}
                                {retrievalEval.misses} misses are published.
                            </p>
                            <EvidenceBadge level={vsGrep.evidence} />
                        </Callout>
                        <Callout variant="caution" title="Not shown: that agents finish tasks faster">
                            <p className="mb-2">
                                A pre-registered pilot ran Claude Code on {pilot.figures.tasks} real bug fixes with
                                and without NeuralMind and found no difference: {pilot.figures.tasks_solved.neuralmind}{' '}
                                of {pilot.figures.tasks} solved either way, a median of{' '}
                                {pilot.figures.median_turns.neuralmind} turns with NeuralMind against{' '}
                                {pilot.figures.median_turns.baseline} without. The guards above are what NeuralMind
                                does to keep changes consistent with your code; how much that saves you later is not
                                measured.
                            </p>
                            <EvidenceBadge level={pilot.evidence} />
                        </Callout>
                    </div>
                    <p className="text-sm mt-4">
                        <a href="/benchmark/" className={link}>
                            Every number, with its source and the command that reproduces it →
                        </a>
                    </p>
                </section>

                <section className="rounded-card panel-accent p-6 md:p-7">
                    <h2 className="font-display text-lg font-semibold tracking-tight text-white mb-2">Try it on your repo</h2>
                    <p className="text-muted text-sm leading-relaxed mb-4">
                        Free at one seat, local, and no account. Build the index, wire the hooks, and the guards above
                        run on your next commit.
                    </p>
                    <div className="bg-carbon rounded-control border border-carbon-border p-4 font-mono text-xs text-body overflow-x-auto mb-4">
                        {['pip install neuralmind', 'neuralmind build .', 'neuralmind init-hook .'].map((c) => (
                            <p key={c} className="whitespace-nowrap">
                                <span className="text-faint select-none">$ </span>
                                {c}
                            </p>
                        ))}
                    </div>
                    <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
                        <a href="/measure-your-own/" className={link}>
                            Measure it on your own code →
                        </a>
                        <a href="/team/" className={link}>
                            For teams →
                        </a>
                    </div>
                </section>
            </main>
            <Footer />
        </>
    );
}
