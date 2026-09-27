import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import { getLatestRelease } from '@/lib/release';
import type { Metadata } from 'next';
import { pageMetadata } from '@/lib/seo';

export const metadata: Metadata = pageMetadata({
    path: '/team',
    title: 'Team Memory for AI Coding Agents — NeuralMind for Teams',
    description:
        'Shared codebase memory for Claude Code and MCP agents: it travels with git, admins govern what is shared, every change is hash-chain audited. Free at 1 seat.',
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
        body: 'Each developer’s synapse layer learns from their own work — which files get opened, edited and queried together. Personal associations stay on their machine.',
    },
    {
        n: '2',
        title: 'Publish through git',
        body: 'neuralmind memory publish writes the learned weights — never source code — to .neuralmind-team-memory.json at the repo root. It is a file in your repo, so it goes through code review like any other.',
    },
    {
        n: '3',
        title: 'Inherit on the next session',
        body: 'Teammates’ agents import the bundle automatically at session start or build, once per content hash. Imports can only raise a weight and land in a shared namespace that decays, so a stale bundle cannot permanently skew recall.',
    },
];

const governance = [
    {
        title: 'Publishing scope',
        body: 'Choose whether learned associations stay personal, go to the shared team graph, or both.',
        cmd: 'neuralmind team governance set-scope shared --admin you@yourco.com',
    },
    {
        title: 'Weight threshold',
        body: 'Only associations above a configurable weight graduate to shared memory, so one-off explorations never reach the team graph.',
        cmd: 'neuralmind team governance set-weight-threshold 0.3 --admin you@yourco.com',
    },
    {
        title: 'Review queue',
        body: 'Edges waiting to enter shared memory can be reviewed first, then approved or rejected one by one.',
        cmd: 'neuralmind memory review-list',
    },
    {
        title: 'Remove shared edges',
        body: 'Admins can pull any association out of the shared graph. Non-admins get a permission error, and every change is logged.',
        cmd: 'neuralmind team governance remove-edge <edge-id> --admin you@yourco.com',
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
    { feature: 'Governance: scope, threshold, review queue', free: true, team: true, enterprise: true },
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
                        teammate&apos;s agent inherits — through your git repo, with admin
                        controls over what gets shared and an audit trail of every change.
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
                        Governance built in, not bolted on
                    </h2>
                    <p className="text-slate-400 mb-8 max-w-3xl leading-relaxed">
                        Shared memory steers every teammate&apos;s agent, so admins decide what
                        reaches it.
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {governance.map((g) => (
                            <div key={g.title} className="bg-carbon-card border border-carbon-border rounded-xl p-6 flex flex-col min-w-0">
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
                                Every governance change and shared-memory mutation is recorded with the
                                acting user in an append-only log where each entry carries the SHA-256
                                of the one before it — so an edited or deleted entry breaks the chain.
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
