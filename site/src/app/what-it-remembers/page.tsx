import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import Callout from '@/components/ui/Callout';
import { blob } from '@/lib/evidence';
import { pageMetadata } from '@/lib/seo';
import { withCode } from '@/lib/ticks';
import type { Metadata } from 'next';

export const metadata: Metadata = pageMetadata({
    path: '/what-it-remembers',
    title: 'What NeuralMind Remembers, and What It Forgets',
    description:
        'Four questions about NeuralMind’s memory, answered from the code: your preferences, feature branches, non-Claude models, and code you haven’t touched.',
    keywords: [
        'NeuralMind memory',
        'AI coding agent memory limits',
        'branch-isolated memory',
        'Hebbian decay half-life',
        'Claude Code memory',
        'MCP code memory any model',
        'agent session recap',
    ],
    ogTitle: 'What NeuralMind remembers, and what it forgets',
    ogDescription:
        'Preferences, feature branches, other models, untouched code: what NeuralMind’s memory does with each, where the limit really is, and the command that shows it.',
});

// Every answer is drawn from the code it links, not from a summary of it.
// The decay figures in the last answer are asserted by
// tests/test_learned_decay.py::TestForgettingInPractice; if decay tuning
// changes, that test fails and this page has to change with it.
type Answer = {
    id: string;
    q: string;
    label: string;
    tone: 'design' | 'built' | 'partly';
    short: string;
    points: string[];
    limit: string;
    check: string[];
    sources: { label: string; href: string }[];
};

const answers: Answer[] = [
    {
        id: 'preferences',
        q: 'Does NeuralMind remember my preferences?',
        label: 'No, by design',
        tone: 'design',
        short: 'No. It remembers your code, the decisions recorded about it, and what your last session was doing. It does not keep a profile of you or of how you like to work.',
        points: [
            '**The last session’s thread** (v4.8.0+). A fresh or cleared Claude Code session, and a Hermes-Agent session through its plugin, starts with a recap of the previous one: its first prompt and its last three, each credential-redacted and cut at 200 characters, and the files it edited. Say “remember this endpoint tomorrow” near the end of a session and tomorrow’s session sees it, labelled as context rather than an instruction. A recap older than 14 days isn’t shown (`NEURALMIND_SESSION_RECAP_MAX_AGE_DAYS`). The newest ten session records stay on disk, and `neuralmind recap --clear` deletes them.',
            '**Decisions about the code.** `neuralmind decisions record` stores a decision with its rationale and the files it governs. With `neuralmind init-hook .` installed, it goes STALE when a commit changes one of those files, and `neuralmind decisions query` finds it by meaning, not only by shared words. A project convention with a reason behind it belongs here.',
            '**Which files go together.** The synapse layer learns which files you edit and query together, per project.',
        ],
        limit: 'Nothing in NeuralMind stores preferences about you, such as formatting, tone, or habits that hold across projects. Its memory lives in each project’s `.neuralmind/` directory. Personal preferences belong in `CLAUDE.md`, your editor’s rules file or your agent’s own memory. NeuralMind writes its learned associations to `SYNAPSE_MEMORY.md`, which Claude Code loads beside them.',
        check: ['neuralmind recap .', 'neuralmind decisions query "why do we hash tokens?"'],
        sources: [
            { label: 'session_recap.py', href: blob('neuralmind/session_recap.py') },
            { label: 'memory/store.py', href: blob('neuralmind/memory/store.py') },
            {
                label: 'Pick up where you left off',
                href: 'https://docs.neuralmind.uk/use-cases/pick-up-where-you-left-off.html',
            },
        ],
    },
    {
        id: 'branches',
        q: 'Will a feature branch pollute the memory main uses?',
        label: 'Mostly not, since v0.24.0',
        tone: 'partly',
        short: 'Mostly not. On any branch other than the default, what NeuralMind learns from your work goes into that branch’s own memory namespace, with no setup, and since v4.22.0 the call graph and the memory file Claude Code loads follow the checkout too, so neither recall on the default branch nor that file sees a feature branch. The exception is call edges older releases seeded into the shared baseline, which fade on a 60-day half-life.',
        points: [
            'On a non-default branch, every association learned from use is written to `branch:<name>`. The default branch comes from `origin/HEAD`, or `main` / `master` when there is no remote. A detached HEAD writes to `personal`.',
            'Recall reads a weighted merge: the branch you are on at full weight, your `personal` memory at 0.8, and the team’s `shared` baseline and the code’s call graph at 0.5 each. On the default branch the active namespace is `personal` itself, so nothing changes until you branch.',
            'The call and import edges a build finds go into a `structural` namespace that every build replaces with the graph of the code checked out (v4.22.0+). A call you add on a feature branch is gone after the next build on the default branch.',
            'The memory file NeuralMind writes for Claude Code at session start (`SYNAPSE_MEMORY.md`) holds only what recall reads on the checkout: the branch’s own namespace, `personal`, `shared` and the call graph (v4.22.0+).',
            'The code index follows the checkout too: `neuralmind init-hook .` installs a post-checkout hook that rebuilds it after a branch switch (v4.13.0+).',
            'To pin a namespace instead, set `NEURALMIND_NAMESPACE`, or `memory_namespace` in `neuralmind-backend.yaml`.',
        ],
        limit: 'Call edges a branch’s build seeded into the `shared` baseline before v4.22.0 stay there, and in recall and the memory file, until they fade on its 60-day half-life. The memory file is written at session start, so after a mid-session checkout it shows the branch you started on. A branch’s learned memory is not folded into `personal` when the branch merges, so the default branch does not inherit it, and an abandoned branch’s namespace stays in the store until you drop it.',
        check: ['neuralmind memory inspect .', 'neuralmind memory reset . --namespace branch:feature-x'],
        sources: [
            { label: 'namespaces.py', href: blob('neuralmind/namespaces.py') },
            { label: 'synapses.py', href: blob('neuralmind/synapses.py') },
            {
                label: 'Branch-isolated memory',
                href: 'https://docs.neuralmind.uk/use-cases/branch-isolated-memory.html',
            },
        ],
    },
    {
        id: 'models',
        q: 'Is NeuralMind tuned for Claude?',
        label: 'The context isn’t; the integration is',
        tone: 'partly',
        short: 'Its context isn’t: every agent and every model gets the same plain text. Its integration is: Claude Code gets the most from it, because its hooks deliver that context without the agent having to ask.',
        points: [
            'NeuralMind picks context without a language model: from the code graph, a vector index built by a small local embedding model, and BM25. It returns plain text and Markdown with no model-specific prompt format, so the output is the same whichever model reads it.',
            'It reaches agents three ways: the MCP server for any MCP client, the CLI (pipe `neuralmind query` into any model, a local one included), and a Python API.',
            'Size comes from progressive disclosure, not from a per-model setting: a small wake-up context first, then the layers a question needs.',
        ],
        limit: 'Claude Code is the only agent tested end to end, and its hooks put the most in front of the model: memory at session start, recall on every prompt, the session recap and a stale-decision guard. Hermes-Agent gets the per-turn context and the recap through its plugin. Cursor, Cline, Continue and other MCP clients get only what the agent decides to call, and in a pre-registered 20-task pilot Claude Code never called NeuralMind’s MCP tools on its own. The retrieval benchmarks don’t depend on the model, since no model picks the context. How well a particular model uses that context has been measured only for Claude Code, in that pilot.',
        check: ['neuralmind wakeup . > CONTEXT.md', 'neuralmind query . "How does auth work?"'],
        sources: [
            { label: 'Any LLM walkthrough', href: 'https://docs.neuralmind.uk/use-cases/any-llm.html' },
            { label: 'Agent support table', href: blob('README.md') },
            { label: 'Task-outcome pilot', href: blob('bench/task_outcome/pilot/report.txt') },
        ],
    },
    {
        id: 'forgetting',
        q: 'Will it forget code I haven’t touched in a while?',
        label: 'Not the code; some associations',
        tone: 'partly',
        short: 'Not the code. The index, meaning every symbol, import and call edge and their embeddings, is rebuilt from your source and does not decay. What fades are learned associations, at a rate set by how often you used them.',
        points: [
            'Learned associations decay on a wall-clock half-life: 30 days by default for personal and branch memory, 60 for the team’s shared baseline, 1 day for session scratch.',
            'Each association learns its own half-life from how often it was reinforced, between 3 and 120 days. Used often, it outlasts the default; used rarely, it fades faster than the default. The longer it sits idle, the closer its rate gets back to the default.',
            'An association reinforced five or more times gets long-term status: it decays to a floor of 0.20 and is never pruned. Others are pruned below 0.01.',
            'Call and import edges are seeded into the shared baseline again on every build, so the structure of code you never edit comes back with each rebuild.',
        ],
        limit: 'Two weeks on the frontend weakens backend associations you had used only a handful of times, and ones you touched only a few times, weeks apart, are gone within five idle months. That costs re-ranking, not findability: the backend is still indexed and still found by search. What it loses is the extra weight recall gives files you have used together.',
        check: ['neuralmind synapse stats .', 'neuralmind memory inspect .'],
        sources: [
            { label: 'synapses.py', href: blob('neuralmind/synapses.py') },
            { label: 'learned_decay.py', href: blob('neuralmind/learned_decay.py') },
            { label: 'test_learned_decay.py', href: blob('tests/test_learned_decay.py') },
        ],
    },
];

// tests/test_learned_decay.py::TestForgettingInPractice asserts each row.
const decayCases = [
    { usage: 'Every day for ten days', learns: 'A half-life over 60 days', idle: 'Two idle weeks: above 80% of full weight' },
    { usage: 'Once a week, six times', learns: 'Long-term status (five uses or more)', idle: 'A year idle: held at the 0.20 floor' },
    { usage: 'Three times, a month apart', learns: 'A half-life under 15 days', idle: 'Two idle months: still kept; five: pruned' },
];

const TONES: Record<Answer['tone'], string> = {
    design: 'border-carbon-line text-body',
    built: 'border-success/30 bg-success/5 text-success',
    partly: 'border-warn/30 bg-warn/5 text-warn',
};

// **bold** lead-ins, then backtick code spans.
function rich(text: string) {
    const m = text.match(/^\*\*(.+?)\*\*\s*(.*)$/);
    if (!m) return withCode(text);
    return (
        <>
            <strong className="text-white font-semibold">{withCode(m[1])}</strong> {withCode(m[2])}
        </>
    );
}

const plain = (text: string) => text.replace(/\*\*|`/g, '');

const faqJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: answers.map((a) => ({
        '@type': 'Question',
        name: a.q,
        acceptedAnswer: { '@type': 'Answer', text: plain(`${a.short} ${a.limit}`) },
    })),
};

export default function WhatItRemembersPage() {
    return (
        <>
            <Navbar />
            <main className="max-w-4xl mx-auto px-4 md:px-6 pt-32 pb-16">
                <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }} />

                <header className="mb-12 pb-8 border-b border-carbon-border">
                    <h1 className="font-display text-3xl md:text-display font-bold text-white mb-5 leading-display tracking-tighter">
                        What NeuralMind remembers, and what it forgets
                    </h1>
                    <p className="text-lg text-body leading-relaxed mb-6">
                        Four questions people ask about NeuralMind&rsquo;s memory, answered from the code.
                        Each answer says what is built, where the limit really is, and the command that
                        shows it on your machine.
                    </p>
                    <nav aria-label="Questions on this page">
                        <ol className="space-y-2">
                            {answers.map((a, i) => (
                                <li key={a.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                                    <span className="font-mono text-xs text-faint tabular-nums">{i + 1}</span>
                                    <a href={`#${a.id}`} className="link">
                                        {a.q}
                                    </a>
                                    <span className="text-muted text-sm">{a.label}</span>
                                </li>
                            ))}
                        </ol>
                    </nav>
                </header>

                <div className="space-y-14">
                    {answers.map((a, i) => (
                        <section key={a.id} id={a.id} className="scroll-mt-28">
                            <div className="flex flex-wrap items-center gap-3 mb-3">
                                <span className="font-mono text-xs text-faint tabular-nums">{i + 1}</span>
                                <span className={`px-3 py-1 rounded-control border text-xs font-mono ${TONES[a.tone]}`}>
                                    {a.label}
                                </span>
                            </div>
                            <h2 className="font-display text-2xl font-bold text-white mb-4 tracking-tight">{a.q}</h2>
                            <p className="text-body text-lg leading-relaxed mb-6">{withCode(a.short)}</p>

                            <h3 className="label mb-3">How it works</h3>
                            <ul className="space-y-3 mb-6">
                                {a.points.map((p) => (
                                    <li key={p} className="text-muted leading-relaxed pl-4 border-l border-carbon-border">
                                        {rich(p)}
                                    </li>
                                ))}
                            </ul>

                            {a.id === 'forgetting' && (
                                <div className="mb-6 overflow-x-auto">
                                    <table className="data-table w-full text-sm">
                                        <caption className="text-left text-faint text-caption mb-2">
                                            One association, used on a schedule and then left idle. Each row is asserted
                                            by{' '}
                                            <a href={blob('tests/test_learned_decay.py')} className="link">
                                                tests/test_learned_decay.py
                                            </a>
                                            .
                                        </caption>
                                        <thead>
                                            <tr>
                                                <th scope="col">Used</th>
                                                <th scope="col">What it learns</th>
                                                <th scope="col">Then</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {decayCases.map((c) => (
                                                <tr key={c.usage}>
                                                    <th scope="row">{c.usage}</th>
                                                    <td>{c.learns}</td>
                                                    <td>{c.idle}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}

                            <Callout variant="caution" title="Where the limit is" className="mb-6">
                                {withCode(a.limit)}
                            </Callout>

                            <div className="grid sm:grid-cols-3 gap-4">
                                <div className="min-w-0 sm:col-span-2">
                                    <h3 className="label mb-3">Check it yourself</h3>
                                    <div className="bg-carbon-raised rounded-control p-4 font-mono text-xs text-body overflow-x-auto">
                                        {a.check.map((line) => (
                                            <p key={line} className="whitespace-nowrap">
                                                <span className="text-faint select-none">$ </span>
                                                {line}
                                            </p>
                                        ))}
                                    </div>
                                </div>
                                <div className="min-w-0">
                                    <h3 className="label mb-3">Read the source</h3>
                                    <ul className="space-y-1.5 text-sm">
                                        {a.sources.map((s) => (
                                            <li key={s.href}>
                                                <a href={s.href} className="link">
                                                    {s.label}
                                                </a>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        </section>
                    ))}
                </div>

                <section className="mt-16 rounded-card panel-accent p-6 md:p-7">
                    <h2 className="font-display text-lg font-semibold tracking-tight text-white mb-2">
                        Found an answer that doesn&rsquo;t match the code?
                    </h2>
                    <p className="text-muted text-sm leading-relaxed mb-4">
                        These answers are checked against the source they link. If one has drifted, tell us
                        and we will correct the page or the code, whichever is wrong.
                    </p>
                    <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
                        <a
                            href="https://github.com/dfrostar/neuralmind/issues"
                            className="link"
                        >
                            Open an issue
                        </a>
                        <a
                            href="https://docs.neuralmind.uk/wiki/Limits-and-Failure-Modes.html"
                            className="link"
                        >
                            Limits and failure modes
                        </a>
                    </div>
                </section>
            </main>
            <Footer />
        </>
    );
}
