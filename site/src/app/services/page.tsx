import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Services — NeuralMind',
    description:
        'Fixed-fee assessment and pilot engagements for engineering teams adopting NeuralMind: measured token-reduction benchmarks on your repos, governance setup, and an honest keep-or-skip recommendation.',
    alternates: {
        canonical: '/services',
    },
};

const offerings = [
    {
        name: 'Codebase Fit Assessment',
        price: 'Fixed fee',
        period: 'per organization',
        description:
            'Find out what NeuralMind actually does on your code before anyone installs anything team-wide.',
        features: [
            'Benchmark on 1–3 of your repos, run on your hardware — the benchmark makes no network calls of its own',
            'Measured retrieval reduction ratios (the same harness as our public CI numbers)',
            'Retrieval-quality spot checks against real questions from your team',
            'Fit across your agent stack: Claude Code, Cursor, Cline, Codex, any MCP client',
            'Written report with a keep-or-skip recommendation — if the numbers say skip, the report says skip',
        ],
        cta: 'Request an assessment',
        ctaHref:
            'mailto:hello@neuralmind.uk?subject=NeuralMind%20Fit%20Assessment',
        highlight: false,
    },
    {
        name: 'Two-Week Team Pilot',
        price: 'Fixed fee',
        period: 'per organization',
        description:
            'One repo, your team, two weeks — instrumented from day one so the exit decision is made on data.',
        features: [
            'Install, hooks, and MCP wiring for each developer’s agent',
            'Shared team-memory baseline committed to your repo (travels via your git remote)',
            'Governance configuration: publish scoping, admin roles, hash-chained audit trail',
            'Weekly measurement checkpoints — token reduction and adoption, not vibes',
            'Exit report with a keep / expand / stop recommendation',
        ],
        cta: 'Request a pilot',
        ctaHref: 'mailto:hello@neuralmind.uk?subject=NeuralMind%20Team%20Pilot',
        highlight: true,
    },
];

const steps = [
    {
        n: '1',
        title: 'Scope call',
        text: 'Which repos, which agents, what compliance constraints. 30 minutes, no deck.',
    },
    {
        n: '2',
        title: 'Fixed-fee quote',
        text: 'Per organization, in writing, invoice-friendly. No per-seat meter running during an engagement.',
    },
    {
        n: '3',
        title: 'The work runs on your infrastructure',
        text: 'NeuralMind is local-first with zero telemetry — engagements follow the same rule. We never take your code.',
    },
    {
        n: '4',
        title: 'Written findings',
        text: 'Measured numbers and a recommendation you can forward to whoever owns the budget.',
    },
];

const wontDo = [
    'Host or process your code on our infrastructure — everything runs local to you.',
    'Promise features that are roadmap-only (SSO/SAML, real-time cross-machine sync).',
    'Recommend a rollout the benchmark data doesn’t support.',
    'Pitch seats during a pilot — licensing is a separate conversation, and every product feature is evaluable free at 1 seat.',
];

export default function ServicesPage() {
    return (
        <>
            <Navbar />
            <main className="pt-32 pb-20 px-4 md:px-6">
                <section className="max-w-5xl mx-auto text-center mb-16">
                    <h1 className="font-display text-4xl md:text-5xl font-bold text-white mb-4">
                        Services
                    </h1>
                    <p className="text-lg text-slate-300 max-w-2xl mx-auto">
                        The software is open source and the savings are free. What we
                        sell is certainty: fixed-fee engagements that measure what
                        NeuralMind does on <em>your</em> repos, wire it into your
                        team&apos;s agents, and put the result in writing.
                    </p>
                </section>

                {/* Offering cards */}
                <section className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-6 mb-20">
                    {offerings.map((tier) => (
                        <div
                            key={tier.name}
                            className={`rounded-xl p-6 flex flex-col ${
                                tier.highlight
                                    ? 'bg-carbon-card border-2 border-electric shadow-electric/10 shadow-2xl'
                                    : 'bg-carbon-card border border-carbon-border'
                            }`}
                        >
                            <div className="mb-4">
                                <h2 className="font-display text-xl font-bold text-white mb-1">
                                    {tier.name}
                                </h2>
                                <div className="flex items-baseline gap-1">
                                    <span className="text-3xl font-bold text-white">
                                        {tier.price}
                                    </span>
                                    <span className="text-sm text-slate-400">
                                        / {tier.period}
                                    </span>
                                </div>
                            </div>
                            <p className="text-slate-400 text-sm mb-6 flex-grow">
                                {tier.description}
                            </p>
                            <ul className="space-y-3 mb-6">
                                {tier.features.map((feature) => (
                                    <li
                                        key={feature}
                                        className="flex items-start gap-2 text-sm text-slate-300"
                                    >
                                        <span className="text-proton mt-0.5">✓</span>
                                        <span>{feature}</span>
                                    </li>
                                ))}
                            </ul>
                            <a
                                href={tier.ctaHref}
                                className={`text-center text-sm font-semibold py-2.5 px-4 rounded-lg transition-colors ${
                                    tier.highlight
                                        ? 'bg-electric hover:bg-electric-bright text-carbon'
                                        : 'bg-carbon border border-carbon-border text-white hover:border-electric/40'
                                }`}
                            >
                                {tier.cta}
                            </a>
                        </div>
                    ))}
                </section>

                {/* How an engagement runs */}
                <section className="max-w-4xl mx-auto mb-20">
                    <h2 className="font-display text-2xl font-bold text-white mb-8 text-center">
                        How an engagement runs
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        {steps.map((step) => (
                            <div
                                key={step.n}
                                className="bg-carbon-card border border-carbon-border rounded-xl p-5"
                            >
                                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-electric to-proton flex items-center justify-center mb-3">
                                    <span className="text-white font-display font-bold text-sm">
                                        {step.n}
                                    </span>
                                </div>
                                <h3 className="text-white font-semibold text-sm mb-2">
                                    {step.title}
                                </h3>
                                <p className="text-slate-400 text-sm leading-relaxed">
                                    {step.text}
                                </p>
                            </div>
                        ))}
                    </div>
                </section>

                {/* Audit-heavy environments */}
                <section className="max-w-3xl mx-auto mb-20">
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-8">
                        <h2 className="font-display text-2xl font-bold text-white mb-4">
                            Built for audit-heavy environments
                        </h2>
                        <p className="text-slate-400 text-sm leading-relaxed mb-4">
                            Teams adopting AI coding agents under compliance regimes —
                            including organizations with EU AI Act obligations that
                            began enforcement in August 2026 — need to show their
                            tooling is controlled and evidenced, not just useful. A
                            NeuralMind engagement documents a deployment that is easy
                            to stand in front of an auditor:
                        </p>
                        <ul className="space-y-2 mb-4">
                            {[
                                'Local-first with zero telemetry — NeuralMind stores your code graph and learned memory on your own infrastructure and makes no network calls of its own',
                                'Append-only, hash-chained audit log of team-memory governance actions',
                                'Publish scoping and admin roles controlling what leaves each developer’s machine',
                                'A CycloneDX SBOM published for every release',
                            ].map((item) => (
                                <li
                                    key={item}
                                    className="flex items-start gap-2 text-sm text-slate-300"
                                >
                                    <span className="text-proton mt-0.5">✓</span>
                                    <span>{item}</span>
                                </li>
                            ))}
                        </ul>
                        <p className="text-slate-500 text-xs leading-relaxed">
                            An engagement supports your evidence needs; it is not legal
                            advice, and no tool by itself makes an organization
                            compliant with any regulation.
                        </p>
                    </div>
                </section>

                {/* What we won't do */}
                <section className="max-w-3xl mx-auto mb-20">
                    <h2 className="font-display text-2xl font-bold text-white mb-6 text-center">
                        What we won&apos;t do
                    </h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6">
                        <ul className="space-y-3">
                            {wontDo.map((item) => (
                                <li
                                    key={item}
                                    className="flex items-start gap-2 text-sm text-slate-300"
                                >
                                    <span className="text-slate-500 mt-0.5">✕</span>
                                    <span>{item}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                </section>

                {/* CTA */}
                <section className="max-w-3xl mx-auto text-center">
                    <p className="text-slate-300 mb-4">
                        Start with the 30-minute scope call — it costs nothing and
                        usually settles whether an engagement is worth it.
                    </p>
                    <a
                        href="mailto:hello@neuralmind.uk?subject=NeuralMind%20Services"
                        className="inline-block bg-electric hover:bg-electric-bright text-carbon text-sm font-semibold py-2.5 px-6 rounded-lg transition-colors"
                    >
                        hello@neuralmind.uk
                    </a>
                    <p className="text-slate-500 text-sm mt-6">
                        Looking for self-serve? The software is free at 1 seat and the
                        Team tier is on the <a href="/pricing" className="text-electric hover:text-electric-bright">pricing page</a>.
                    </p>
                </section>
            </main>
            <Footer />
        </>
    );
}
