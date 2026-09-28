import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import { getLatestRelease } from '@/lib/release';
import type { Metadata } from 'next';
import { pageMetadata } from '@/lib/seo';

export const metadata: Metadata = pageMetadata({
    path: '/pricing',
    title: 'NeuralMind Pricing — Free MIT Core, Team $29/user/mo',
    description:
        'Every NeuralMind feature is free at 1 seat — no signup, no expiry. Team is $29/user/mo (5–50 seats, annual) for more seats and priority support.',
    keywords: [
        'NeuralMind pricing',
        'Claude Code memory pricing',
        'AI coding agent memory free',
        'MCP server pricing',
        'team memory for AI agents',
    ],
});

const tiers = [
    {
        name: 'Free',
        price: '$0',
        period: 'forever',
        description:
            'MIT core plus every tier2 feature at 1 seat — governance, audit, self-hosted. Nothing is gated.',
        features: [
            'MIT core — full source on GitHub',
            '1-seat license, auto-issued, never expires',
            'Personal memory graph',
            'L0–L3 progressive disclosure',
            'Governance, audit & self-hosted at 1 seat',
            'Community support (GitHub)',
        ],
        cta: 'pip install neuralmind',
        ctaHref: 'https://pypi.org/project/neuralmind/',
        highlight: false,
    },
    {
        name: 'Team',
        price: '$29',
        period: 'per user / month',
        description:
            'The license buys seats and support — the features are already free at 1 seat, so evaluate everything first.',
        features: [
            'Multi-seat license (5-50 seats)',
            'Priority support',
            'Annual invoice — procurement-friendly',
            'Signed seat manifests + admin audit at team scale',
            'Self-hosted deployment support',
        ],
        cta: 'Contact us about Team',
        ctaHref: 'mailto:hello@neuralmind.uk?subject=NeuralMind%20Team%20tier',
        highlight: true,
    },
    {
        name: 'Enterprise',
        price: 'Custom',
        period: 'tailored to your org',
        description: 'Self-hosted deployment, custom SLA, dedicated onboarding.',
        features: [
            'Self-hosted deployment',
            'Custom SLA & support',
            'Dedicated onboarding',
            'SSO / SAML integration (roadmap)',
            'Real-time cross-machine sync (roadmap)',
        ],
        cta: 'Contact sales',
        ctaHref: 'mailto:hello@neuralmind.uk',
        highlight: false,
    },
];

const faqs = [
    {
        q: 'Is NeuralMind really open source?',
        a: 'Yes. The core engine is MIT-licensed — full source on GitHub, no feature gates. The paid tiers do not unlock hidden features: the Team license covers seats beyond one, priority support, and an annual invoice. Everything is evaluable on the free 1-seat license first.',
    },
    {
        q: 'How does billing work for Team?',
        a: '$29 per user per month on an annual contract, 5-50 seats, invoiced — contact hello@neuralmind.uk to start. There is no self-serve checkout. Seats are reassignable as your team changes.',
    },
    {
        q: 'Is there a free trial?',
        a: 'There is no trial because there is nothing to unlock: the free 1-seat license never expires and runs every feature. Evaluate NeuralMind on one repo for as long as you like, then contact hello@neuralmind.uk when your team needs more seats.',
    },
    {
        q: 'Where is my team data stored?',
        a: 'On your machines. The index and synapse data live in each project directory, and team memory bundles publish and import through your own git repository — no relay, no server of ours in the path. Every tier is air-gap installable. We never see your code, so we never train on it.',
    },
];

const faqJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqs.map((faq) => ({
        '@type': 'Question',
        name: faq.q,
        acceptedAnswer: { '@type': 'Answer', text: faq.a },
    })),
};

export default async function PricingPage() {
    const rel = await getLatestRelease();
    const version = rel.tag;

    return (
        <>
            <Navbar />
            <main className="pt-32 pb-20 px-4 md:px-6">
                <script
                    type="application/ld+json"
                    dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
                />
                <section className="max-w-5xl mx-auto text-center mb-16">
                    <h1 className="font-display text-4xl md:text-5xl font-bold text-white mb-4">
                        Pricing
                    </h1>
                    <p className="text-lg text-slate-300 max-w-2xl mx-auto">
                        NeuralMind&apos;s core engine ({version}) is MIT-licensed open source, and
                        every feature — governance, audit and self-hosted included — is free at
                        1 seat, forever. You pay for seats beyond one and for support, not for
                        features.
                    </p>
                </section>

                {/* Pricing Cards */}
                <section className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6 mb-20">
                    {tiers.map((tier) => (
                        <div
                            key={tier.name}
                            className={`rounded-xl p-6 flex flex-col ${
                                tier.highlight
                                    ? 'bg-carbon-card border-2 border-electric shadow-electric/10 shadow-2xl'
                                    : 'bg-carbon-card border border-carbon-border'
                            }`}
                        >
                            <div className="mb-4">
                                <h3 className="font-display text-xl font-bold text-white mb-1">
                                    {tier.name}
                                </h3>
                                <div className="flex items-baseline gap-1">
                                    <span className="text-3xl font-bold text-white">
                                        {tier.price}
                                    </span>
                                    {tier.period !== 'forever' && (
                                        <span className="text-sm text-slate-400">
                                            / {tier.period}
                                        </span>
                                    )}
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

                {/* FAQ */}
                <section className="max-w-3xl mx-auto">
                    <h2 className="font-display text-2xl font-bold text-white mb-8 text-center">
                        Frequently Asked Questions
                    </h2>
                    <div className="space-y-6">
                        {faqs.map((faq) => (
                            <div
                                key={faq.q}
                                className="bg-carbon-card border border-carbon-border rounded-xl p-6"
                            >
                                <h3 className="text-white font-semibold mb-2">{faq.q}</h3>
                                <p className="text-slate-400 text-sm leading-relaxed">
                                    {faq.a}
                                </p>
                            </div>
                        ))}
                    </div>
                </section>
            </main>
            <Footer />
        </>
    );
}
