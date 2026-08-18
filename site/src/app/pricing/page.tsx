import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import { getLatestRelease } from '@/lib/release';
import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Pricing — NeuralMind',
    description:
        'NeuralMind is MIT-licensed open source with every feature free at 1 seat. The Team tier licenses seats beyond one (5-50) with priority support; Enterprise adds custom SLAs.',
};

const tiers = [
    {
        name: 'Free',
        price: '$0',
        period: 'forever',
        description:
            'MIT core plus every tier2 feature at 1 seat — governance, audit, self-hosted. Nothing is gated.',
        features: [
            'MIT OSS — full source code',
            '1-seat license, auto-issued, never expires',
            'Personal memory graph',
            'L0–L3 progressive disclosure',
            'Governance, audit & self-hosted at 1 seat',
            'Community support (Discord/GitHub)',
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
        q: 'Where is my team data stored?',
        a: 'All synapse data is stored locally. Team memory bundles publish and import through your own git repository — no relay, no server of ours in the path. Enterprise is air-gap installable in your infrastructure. We never train on your code.',
    },
];

export default async function PricingPage() {
    const rel = await getLatestRelease();
    const version = rel.tag;

    return (
        <>
            <Navbar />
            <main className="pt-32 pb-20 px-4 md:px-6">
                <section className="max-w-5xl mx-auto text-center mb-16">
                    <h1 className="font-display text-4xl md:text-5xl font-bold text-white mb-4">
                        Pricing
                    </h1>
                    <p className="text-lg text-slate-300 max-w-2xl mx-auto">
                        NeuralMind&apos;s core engine ({version}) is MIT-licensed open source —
                        free forever, including governance, audit, and self-hosted at
                        1 seat. The Team tier licenses seats beyond one; Enterprise
                        adds custom SLAs and onboarding.
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
