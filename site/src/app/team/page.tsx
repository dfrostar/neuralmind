import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import { getLatestRelease } from '@/lib/release';
import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Team & Enterprise — NeuralMind',
    description:
        'NeuralMind for teams: shared codebase intelligence, memory governance, seat management, Ed25519-signed manifests, and self-hosted deployment.',
};

const cardStyle: React.CSSProperties = {
    background: '#161b22',
    border: '1px solid #30363d',
    borderRadius: '0.75rem',
    padding: '1.5rem',
};

const headingStyle: React.CSSProperties = {
    fontFamily: 'var(--font-display), serif',
    fontWeight: 700,
    color: '#e1e4e8',
};

export default async function TeamPage() {
    const rel = await getLatestRelease();
    const version = rel.tag;

    return (
        <>
            <Navbar />
            <main className="pt-32 pb-20 px-4 md:px-6">
                {/* Hero */}
                <section className="max-w-4xl mx-auto text-center mb-20">
                    <h1
                        className="text-4xl md:text-5xl font-bold mb-4"
                        style={{ ...headingStyle, color: '#ffffff' }}
                    >
                        Built for Teams
                    </h1>
                    <p className="text-lg text-slate-300 max-w-2xl mx-auto">
                        Shared codebase intelligence that learns how your team works —
                        with governance controls over what each developer publishes to the shared memory.
                    </p>
                    <p className="text-faint text-sm mt-3">
                        Available in Team and Enterprise tiers •{' '}
                        <a
                            href="/pricing"
                            className="text-electric hover:text-electric-bright transition-colors underline"
                        >
                            See pricing →
                        </a>
                    </p>
                </section>

                {/* What Team Memory Means */}
                <section className="max-w-4xl mx-auto mb-16">
                    <h2
                        className="text-2xl font-bold mb-6"
                        style={headingStyle}
                    >
                        What Team Memory Means
                    </h2>
                    <p className="text-slate-300 mb-6 leading-relaxed">
                        NeuralMind&apos;s synapse layer learns associations between code nodes
                        from how your team actually uses the codebase. On Team and Enterprise,
                        these synapses can be shared — so a junior developer on Monday benefits
                        from a senior&apos;s discoveries on Friday.
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div style={cardStyle}>
                            <h3 className="text-white font-semibold mb-2 text-sm">
                                Synapse Sharing
                            </h3>
                            <p className="text-slate-400 text-sm leading-relaxed">
                                Shared memory lets team members build on each other&apos;s
                                codebase insights — patterns, gotchas, and architectural
                                decisions persist across sessions and across machines.
                            </p>
                        </div>
                        <div style={cardStyle}>
                            <h3 className="text-white font-semibold mb-2 text-sm">
                                Admin Governance
                            </h3>
                            <p className="text-slate-400 text-sm leading-relaxed">
                                Admins control what enters shared memory. Scope, weight
                                thresholds, and enforcement policies keep noise out of the
                                team graph.
                            </p>
                        </div>
                        <div style={cardStyle}>
                            <h3 className="text-white font-semibold mb-2 text-sm">
                                Audit Trail
                            </h3>
                            <p className="text-slate-400 text-sm leading-relaxed">
                                Every shared mutation is logged with actor attribution in an
                                append-only SHA-256 hash chain — tamper-evident and
                                exportable.
                            </p>
                        </div>
                    </div>
                </section>

                {/* Governance Controls */}
                <section className="max-w-4xl mx-auto mb-16">
                    <h2
                        className="text-2xl font-bold mb-6"
                        style={headingStyle}
                    >
                        Governance Controls
                    </h2>
                    <p className="text-slate-300 mb-6 leading-relaxed">
                        Team memory is powerful — which is why governance is built in from
                        the start, not bolted on later.
                    </p>

                    <div className="space-y-4">
                        <div
                            style={cardStyle}
                            className="flex items-start gap-4"
                        >
                            <div
                                className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                                style={{
                                    background: 'rgba(88, 166, 255, 0.1)',
                                    border: '1px solid rgba(88, 166, 255, 0.3)',
                                }}
                            >
                                <span className="text-electric font-mono text-sm">S</span>
                            </div>
                            <div>
                                <h3 className="text-white font-semibold mb-1">
                                    Scope: Personal / Shared / Both
                                </h3>
                                <p className="text-slate-400 text-sm leading-relaxed">
                                    Synapses are tagged with scope. Personal synapses stay
                                    on the local machine. Shared synapses propagate to the
                                    team graph. Admins enforce which scopes are allowed.
                                </p>
                            </div>
                        </div>

                        <div
                            style={cardStyle}
                            className="flex items-start gap-4"
                        >
                            <div
                                className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                                style={{
                                    background: 'rgba(88, 166, 255, 0.1)',
                                    border: '1px solid rgba(88, 166, 255, 0.3)',
                                }}
                            >
                                <span className="text-electric font-mono text-sm">W</span>
                            </div>
                            <div>
                                <h3 className="text-white font-semibold mb-1">
                                    Weight Threshold
                                </h3>
                                <p className="text-slate-400 text-sm leading-relaxed">
                                    Only synapses above a configurable weight threshold
                                    graduate to shared status. This prevents one-off
                                    explorations from polluting the team graph with noise.
                                </p>
                            </div>
                        </div>

                        <div
                            style={cardStyle}
                            className="flex items-start gap-4"
                        >
                            <div
                                className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                                style={{
                                    background: 'rgba(88, 166, 255, 0.1)',
                                    border: '1px solid rgba(88, 166, 255, 0.3)',
                                }}
                            >
                                <span className="text-electric font-mono text-sm">A</span>
                            </div>
                            <div>
                                <h3 className="text-white font-semibold mb-1">
                                    Admin Enforcement
                                </h3>
                                <p className="text-slate-400 text-sm leading-relaxed">
                                    Admins can review, promote, demote, or remove shared
                                    synapses. Enforcement can be strict (admin-approve-all)
                                    or permissive (auto-publish above threshold).
                                </p>
                            </div>
                        </div>

                        <div
                            style={cardStyle}
                            className="flex items-start gap-4"
                        >
                            <div
                                className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                                style={{
                                    background: 'rgba(88, 166, 255, 0.1)',
                                    border: '1px solid rgba(88, 166, 255, 0.3)',
                                }}
                            >
                                <span className="text-electric font-mono text-sm">M</span>
                            </div>
                            <div>
                                <h3 className="text-white font-semibold mb-1">
                                    Signed Manifests
                                </h3>
                                <p className="text-slate-400 text-sm leading-relaxed">
                                    All shared manifests are Ed25519-signed. Recipients
                                    verify signatures before accepting shared memory —
                                    preventing tampered or spoofed synapse graph entries.
                                </p>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Seat Management */}
                <section className="max-w-4xl mx-auto mb-16">
                    <h2
                        className="text-2xl font-bold mb-6"
                        style={headingStyle}
                    >
                        Seat Management
                    </h2>
                    <p className="text-slate-300 mb-6 leading-relaxed">
                        Add, remove, list, and sync seats programmatically. Every operation
                        is logged and verifiable.
                    </p>

                    <div
                        style={cardStyle}
                    >
                        <div className="font-mono text-sm text-slate-300 space-y-2">
                            <p className="text-faint"># Add a team member</p>
                            <p>
                                <span className="text-electric">$</span> neuralmind
                                seats add --email developer@team.org --role member
                            </p>
                            <p className="text-faint mt-4"># List active seats</p>
                            <p>
                                <span className="text-electric">$</span> neuralmind
                                seats list --format json
                            </p>
                            <p className="text-faint mt-4"># Remove a seat</p>
                            <p>
                                <span className="text-electric">$</span> neuralmind
                                seats remove --email former@team.org
                            </p>
                            <p className="text-faint mt-4"># Sync signed manifest</p>
                            <p>
                                <span className="text-electric">$</span> neuralmind
                                seats sync --verify-ed25519 --org acme-corp
                            </p>
                        </div>
                        <p className="text-faint text-xs mt-4">
                            Signed manifest verification uses Ed25519 key signatures.
                            Each seat has a unique keypair; the admin&apos;s public key
                            signs the manifest that travels with shared synapses.
                        </p>
                    </div>
                </section>

                {/* Feature Comparison */}
                <section className="max-w-4xl mx-auto mb-16">
                    <h2
                        className="text-2xl font-bold mb-6"
                        style={headingStyle}
                    >
                        Team vs Enterprise
                    </h2>
                    <div
                        style={cardStyle}
                        className="overflow-x-auto"
                    >
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-carbon-border">
                                    <th className="text-left py-3 px-4 text-slate-400 font-medium">
                                        Feature
                                    </th>
                                    <th className="text-center py-3 px-4 text-slate-400 font-medium">
                                        Team
                                    </th>
                                    <th className="text-center py-3 px-4 text-slate-400 font-medium">
                                        Enterprise
                                    </th>
                                </tr>
                            </thead>
                            <tbody className="text-slate-300">
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-3 px-4">Shared memory</td>
                                    <td className="text-center py-3 px-4 text-proton">✓</td>
                                    <td className="text-center py-3 px-4 text-proton">✓</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-3 px-4">Governance controls</td>
                                    <td className="text-center py-3 px-4 text-proton">✓</td>
                                    <td className="text-center py-3 px-4 text-proton">✓</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-3 px-4">Seat management</td>
                                    <td className="text-center py-3 px-4 text-proton">✓</td>
                                    <td className="text-center py-3 px-4 text-proton">✓</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-3 px-4">Ed25519 signed manifests</td>
                                    <td className="text-center py-3 px-4 text-proton">✓</td>
                                    <td className="text-center py-3 px-4 text-proton">✓</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-3 px-4">Self-hosted deployment</td>
                                    <td className="text-center py-3 px-4 text-faint">—</td>
                                    <td className="text-center py-3 px-4 text-proton">✓</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-3 px-4">SSO / SAML</td>
                                    <td className="text-center py-3 px-4 text-faint">—</td>
                                    <td className="text-center py-3 px-4 text-proton">✓</td>
                                </tr>
                                <tr className="border-b border-carbon-border/50">
                                    <td className="py-3 px-4">Real-time cross-machine sync</td>
                                    <td className="text-center py-3 px-4 text-faint">—</td>
                                    <td className="text-center py-3 px-4 text-proton">✓</td>
                                </tr>
                                <tr>
                                    <td className="py-3 px-4">Custom SLA</td>
                                    <td className="text-center py-3 px-4 text-faint">—</td>
                                    <td className="text-center py-3 px-4 text-proton">✓</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </section>

                {/* CTA */}
                <section className="max-w-3xl mx-auto text-center">
                    <div
                        className="rounded-xl p-8"
                        style={{
                            background: 'linear-gradient(135deg, rgba(22, 27, 34, 0.9) 0%, rgba(15, 17, 23, 0.9) 100%)',
                            border: '1px solid rgba(88, 166, 255, 0.3)',
                        }}
                    >
                        <h2
                            className="text-2xl font-bold mb-3"
                            style={{ ...headingStyle, color: '#ffffff' }}
                        >
                            Ready to share codebase intelligence?
                        </h2>
                        <p className="text-slate-400 mb-6">
                            Start with Team ($29/user/mo) or talk to us about Enterprise.
                            The OSS core ({version}) remains free forever.
                        </p>
                        <div className="flex items-center justify-center gap-4 flex-wrap">
                            <a
                                href="/pricing"
                                className="inline-block text-sm font-semibold py-2.5 px-6 rounded-lg transition-colors"
                                style={{
                                    background: 'linear-gradient(135deg, #3b82f6 0%, #6366f1 100%)',
                                    color: '#ffffff',
                                }}
                            >
                                See Pricing
                            </a>
                            <a
                                href="mailto:hello@neuralmind.uk"
                                className="inline-block text-sm font-semibold py-2.5 px-6 rounded-lg transition-colors"
                                style={{
                                    background: 'rgba(255, 255, 255, 0.04)',
                                    border: '1px solid #30363d',
                                    color: '#e1e4e8',
                                }}
                            >
                                Contact Sales
                            </a>
                        </div>
                    </div>
                </section>
            </main>
            <Footer />
        </>
    );
}
