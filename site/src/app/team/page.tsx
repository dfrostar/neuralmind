import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import { getLatestRelease } from '@/lib/release';
import type { Metadata } from 'next';
import { pageMetadata } from '@/lib/seo';

export const metadata: Metadata = pageMetadata({
    path: '/team',
    title: 'Team Memory for AI Coding Agents — NeuralMind for Teams',
    description:
        'Shared codebase memory for Claude Code and MCP agents: it travels with git, imports pass a review queue, admin changes are hash-chain audited. Free at 1 seat.',
    keywords: [
        'team memory for AI coding agents',
        'shared Claude Code memory',
        'Claude Code for teams',
        'AI agent governance',
        'hash-chained audit log',
        'self-hosted AI coding tools',
        'MCP server for teams',
    ],
});

// Every command below exists in neuralmind/cli.py or neuralmind/tier2/cli.py,
// with the arguments shown. This page previously advertised a `neuralmind seats
// --email … --org` syntax that has never existed, per-seat keypairs that do not
// exist (seat *manifests* and licenses are what is Ed25519-signed), and SSO /
// real-time sync as shipped Enterprise features — both are roadmap-only per
// commercial-terms.json.
const steps = [
    {
        n: '1',
        title: 'Learn locally',
        body: 'Each developer’s synapse layer learns from their own work — which files get opened, edited and queried together. It stays in the project’s local .neuralmind/ store until someone publishes it.',
    },
    {
        n: '2',
        title: 'Publish through git',
        body: 'neuralmind memory publish writes the project’s learned associations — weights between files, never source code — to .neuralmind-team-memory.json at the repo root. You commit it like any other file, so it goes through code review.',
    },
    {
        n: '3',
        title: 'Inherit on the next session',
        body: 'Teammates’ agents import the bundle automatically at session start or build, once per content hash. Each association is quality-scored: strong ones enter shared memory, borderline ones wait for review, weak ones are dropped. Shared weights decay, so a stale bundle cannot permanently skew recall.',
    },
];

// What governance does today, stated precisely. The review queue gates what an
// import brings into shared memory. Scope and weight threshold are admin-only,
// audited policy settings, but `memory publish` does not read them yet, and
// `team governance remove-edge` records the request without deleting the edge —
// so this page must not describe either as enforced.
const governance = [
    {
        title: 'Review queue for imported memory',
        status: 'Live',
        body: 'When a teammate’s bundle is imported, every association is quality-scored. Borderline ones wait in a queue until someone approves or rejects them; conflicts with what you already have are resolved by quality, not by whoever published last.',
        cmd: 'neuralmind memory review-list',
    },
    {
        title: 'Admin-only, audited settings',
        status: 'Live',
        body: 'Governance commands require an admin — non-admins get a permission error — and every change is written to the hash-chained audit log with the acting user.',
        cmd: 'neuralmind team governance status',
    },
    {
        title: 'Publishing scope and weight threshold',
        status: 'Roadmap',
        body: 'Admins can record whether associations should publish as personal, shared or both, and the minimum weight for sharing. Today these are audited policy settings; memory publish does not enforce them yet.',
        cmd: 'neuralmind team governance set-scope shared --admin you@yourco.com',
    },
];

const seatCommands = [
    { comment: '# Add a teammate (admin only)', cmd: 'neuralmind team seats add dev@yourco.com --admin you@yourco.com' },
    { comment: '# List seats', cmd: 'neuralmind team seats list --json' },
    { comment: '# Deactivate a seat — the audit trail is kept', cmd: 'neuralmind team seats remove former@yourco.com --admin you@yourco.com' },
    { comment: '# Reconcile seats from an Ed25519-signed manifest', cmd: 'neuralmind team seats sync seats-manifest.json --admin you@yourco.com' },
];

type Cell = string | boolean;
const comparison: { feature: string; free: Cell; team: Cell; enterprise: Cell }[] = [
    { feature: 'Team memory through git (memory publish)', free: true, team: true, enterprise: true },
    { feature: 'Import review queue + audited governance settings', free: true, team: true, enterprise: true },
    { feature: 'Hash-chained audit log, verify and export', free: true, team: true, enterprise: true },
    { feature: 'Self-hosted deployment', free: true, team: 'With deployment support', enterprise: true },
    { feature: 'Seats', free: '1', team: '5–50', enterprise: 'Custom' },
    { feature: 'Support', free: 'Community (GitHub)', team: 'Priority', enterprise: 'Custom SLA' },
    { feature: 'Billing', free: '—', team: 'Annual invoice', enterprise: 'Custom' },
    { feature: 'Onboarding', free: 'Self-serve', team: 'Self-serve', enterprise: 'Dedicated' },
];

function Mark({ value }: { value: Cell }) {
    if (value === true) return <span className="text-proton" aria-label="Included">✓</span>;
    if (value === false) return <span className="text-faint" aria-label="Not included">—</span>;
    return <span className="text-slate-300">{value}</span>;
}

export default async function TeamPage() {
    const rel = await getLatestRelease();
    const version = rel.tag;

    return (
        <>
            <Navbar />
            <main className="pt-32 pb-20 px-4 md:px-6">
                {/* Hero */}
                <section className="max-w-4xl mx-auto text-center mb-20">
                    <span className="eyebrow block mb-4">NeuralMind for teams</span>
                    <h1 className="font-display text-4xl md:text-5xl font-bold text-white mb-5 tracking-tight">
                        Team memory for AI coding agents
                    </h1>
                    <p className="text-lg text-slate-300 max-w-2xl mx-auto leading-relaxed">
                        What one developer&apos;s agent learns about the codebase, every
                        teammate&apos;s agent inherits — through your git repo, with a review
                        queue for what comes in and an audit trail of every admin change.
                    </p>
                    <p className="text-faint text-sm mt-5 max-w-2xl mx-auto">
                        Every feature on this page runs free at 1 seat, so you can evaluate it
                        before you buy. The Team license ($29/user/mo, 5–50 seats, annual) adds
                        seats and priority support.{' '}
                        <a href="/pricing" className="text-electric hover:text-electric-bright transition-colors underline">
                            See pricing →
                        </a>
                    </p>
                </section>

                {/* How team memory works */}
                <section className="max-w-5xl mx-auto mb-20">
                    <h2 className="font-display text-2xl md:text-3xl font-bold text-white mb-3">
                        How team memory works
                    </h2>
                    <p className="text-slate-400 mb-8 max-w-3xl leading-relaxed">
                        No relay, no hosted service, no server of ours in the path. The shared memory
                        is a file in your repository, so it travels with <code className="font-mono text-[0.9em] text-slate-300">git clone</code> and
                        inherits your existing review and access controls.
                    </p>
                    <ol className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {steps.map((step) => (
                            <li key={step.n} className="bg-carbon-card border border-carbon-border rounded-xl p-6">
                                <span className="w-7 h-7 rounded-md border border-carbon-line bg-carbon-raised flex items-center justify-center font-mono text-xs text-electric tabular-nums mb-4">
                                    {step.n}
                                </span>
                                <h3 className="text-white font-semibold mb-2">{step.title}</h3>
                                <p className="text-slate-400 text-sm leading-relaxed">{step.body}</p>
                            </li>
                        ))}
                    </ol>
                </section>

                {/* Governance */}
                <section className="max-w-5xl mx-auto mb-20">
                    <h2 className="font-display text-2xl md:text-3xl font-bold text-white mb-3">
                        Governance: what is enforced today
                    </h2>
                    <p className="text-slate-400 mb-8 max-w-3xl leading-relaxed">
                        Shared memory steers every teammate&apos;s agent, so what enters it is
                        screened and every admin action is on the record. Here is exactly what
                        runs now and what is still on the roadmap.
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {governance.map((g) => (
                            <div key={g.title} className="bg-carbon-card border border-carbon-border rounded-xl p-6 flex flex-col min-w-0">
                                <span className={`font-mono text-[0.6875rem] uppercase tracking-[0.12em] mb-3 ${g.status === 'Live' ? 'text-proton' : 'text-faint'}`}>
                                    {g.status}
                                </span>
                                <h3 className="text-white font-semibold mb-2">{g.title}</h3>
                                <p className="text-slate-400 text-sm leading-relaxed mb-4">{g.body}</p>
                                <div className="mt-auto bg-carbon rounded-lg px-4 py-3 font-mono text-xs text-slate-300 overflow-x-auto">
                                    <span className="text-faint select-none">$ </span>
                                    {g.cmd}
                                </div>
                            </div>
                        ))}
                    </div>
                </section>

                {/* Audit */}
                <section className="max-w-5xl mx-auto mb-20">
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6 md:p-8 grid md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-6 md:gap-10">
                        <div>
                            <h2 className="font-display text-2xl font-bold text-white mb-3">
                                An audit trail you can verify
                            </h2>
                            <p className="text-slate-400 text-sm leading-relaxed mb-3">
                                Every governance change and admin action is recorded with the acting
                                user in an append-only log where each entry carries the SHA-256 of the
                                one before it — so an edited or deleted entry breaks the chain.
                            </p>
                            <p className="text-slate-400 text-sm leading-relaxed">
                                Query-level events export as JSONL or CEF for your SIEM with{' '}
                                <code className="font-mono text-[0.9em] text-slate-300">neuralmind audit export</code>.
                            </p>
                        </div>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-xs text-slate-300 overflow-x-auto self-start">
                            <p className="text-faint"># Walk the hash chain</p>
                            <p><span className="text-faint select-none">$ </span>neuralmind team audit verify</p>
                            <p className="text-faint mt-3"># Hand it to your auditors</p>
                            <p><span className="text-faint select-none">$ </span>neuralmind team audit export --format csv --output audit.csv</p>
                        </div>
                    </div>
                </section>

                {/* Seats */}
                <section className="max-w-5xl mx-auto mb-20">
                    <h2 className="font-display text-2xl md:text-3xl font-bold text-white mb-3">
                        Seat management
                    </h2>
                    <p className="text-slate-400 mb-6 max-w-3xl leading-relaxed">
                        Seats are managed from the CLI and every change is logged. Rosters can be
                        reconciled from an Ed25519-signed manifest — the signature is checked before
                        anything changes — and adding a seat past your license limit fails instead of
                        silently over-provisioning.
                    </p>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6">
                        <div className="font-mono text-xs md:text-sm text-slate-300 space-y-1 overflow-x-auto">
                            {seatCommands.map((c, i) => (
                                <div key={c.cmd} className={i > 0 ? 'pt-3' : ''}>
                                    <p className="text-faint">{c.comment}</p>
                                    <p className="whitespace-nowrap">
                                        <span className="text-electric select-none">$ </span>
                                        {c.cmd}
                                    </p>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                {/* Comparison */}
                <section className="max-w-5xl mx-auto mb-20">
                    <h2 className="font-display text-2xl md:text-3xl font-bold text-white mb-3">
                        Free, Team and Enterprise
                    </h2>
                    <p className="text-slate-400 mb-6 max-w-3xl leading-relaxed">
                        The product features are not gated. The license buys seats beyond one,
                        support and procurement-friendly billing.
                    </p>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl overflow-x-auto">
                        <table className="w-full min-w-[36rem] text-sm">
                            <caption className="sr-only">What each NeuralMind tier includes</caption>
                            <thead>
                                <tr className="border-b border-carbon-border">
                                    <th scope="col" className="text-left py-3 px-4 text-slate-400 font-medium">Feature</th>
                                    <th scope="col" className="text-center py-3 px-4 text-slate-400 font-medium">Free (1 seat)</th>
                                    <th scope="col" className="text-center py-3 px-4 text-slate-400 font-medium">Team</th>
                                    <th scope="col" className="text-center py-3 px-4 text-slate-400 font-medium">Enterprise</th>
                                </tr>
                            </thead>
                            <tbody>
                                {comparison.map((row) => (
                                    <tr key={row.feature} className="border-b border-carbon-border/50 last:border-0">
                                        <th scope="row" className="text-left py-3 px-4 text-slate-300 font-normal">{row.feature}</th>
                                        <td className="text-center py-3 px-4"><Mark value={row.free} /></td>
                                        <td className="text-center py-3 px-4"><Mark value={row.team} /></td>
                                        <td className="text-center py-3 px-4"><Mark value={row.enterprise} /></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    <p className="text-faint text-sm mt-4">
                        On the roadmap, not available on any tier today: SSO / SAML, and real-time
                        cross-machine sync. Team memory syncs by commit and pull.
                    </p>
                </section>

                {/* CTA */}
                <section className="max-w-3xl mx-auto text-center">
                    <div className="panel-accent rounded-xl p-8">
                        <h2 className="font-display text-2xl font-bold text-white mb-3">
                            Evaluate it free, then talk to us about seats
                        </h2>
                        <p className="text-slate-400 mb-6">
                            Install the open-source core ({version}), run it on one repo with the
                            free 1-seat license, and contact us when the team wants more seats. There
                            is no self-serve checkout and no trial clock.
                        </p>
                        <div className="flex items-center justify-center gap-4 flex-wrap">
                            <a href="/pricing" className="btn-primary text-sm">
                                See pricing
                            </a>
                            <a
                                href="mailto:hello@neuralmind.uk?subject=NeuralMind%20Team%20seats"
                                className="btn-secondary text-sm"
                            >
                                hello@neuralmind.uk
                            </a>
                        </div>
                    </div>
                </section>
            </main>
            <Footer />
        </>
    );
}
