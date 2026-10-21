import terms from '../../../../commercial-terms.json';
import Icon from '@/components/ui/Icon';
import SectionHeader from '@/components/ui/SectionHeader';
import { withCode } from '@/lib/ticks';

// The enterprise story used to live only on /security. This section puts the
// two things a team lead asks — how does it work for a team, and will it pass
// a security review — on the homepage, and sends each to its own page.
//
// Price, seats and billing are read from commercial-terms.json (repo root),
// the canon for every commercial term; nothing here is typed by hand.

const team = [
    '`neuralmind memory publish` writes the learned associations — weights, no source code — to a file you commit. Teammates’ agents import it on their next session.',
    'Publishing follows the scope and weight threshold an admin sets, borderline imports wait in a review queue, and removing an association retracts it for everyone.',
    'Every publish, import, review and admin change lands in a hash-chained audit log you can verify and export.',
];

const security = [
    'By default, no telemetry and no repository content off your machine. One public model download on first build, pre-seedable for air-gapped installs.',
    'Signed images and build-provenance attestations you can verify with cosign and `gh attestation verify`, a CycloneDX SBOM and an OpenVEX statement.',
    '`security.profile: cui`, `neuralmind scan-for-secrets`, `neuralmind data-locations` and an SP 800-53 hardening check — evidence for your review; NeuralMind holds no certification.',
];

export default function TeamsSecurity() {
    const paid = terms.pricing.team;
    return (
        <section id="teams" className="relative py-20 md:py-28 px-4 md:px-6">
            <div className="max-w-6xl mx-auto">
                <SectionHeader eyebrow="Teams & security" title="Memory your team shares, evidence your reviewer asks for">
                    Every feature runs free at one seat: the license issues itself on first run, never
                    expires and needs no signup. You pay for seats and support, not for features.
                </SectionHeader>

                <div className="grid md:grid-cols-2 gap-4 md:gap-6">
                    <div className="panel rounded-card p-6 md:p-8 flex flex-col">
                        <p className="eyebrow mb-3">For teams</p>
                        <h3 className="font-display text-2xl font-semibold text-white tracking-tight mb-5">
                            Team memory travels with git
                        </h3>
                        <ul className="space-y-3 mb-6">
                            {team.map((t) => (
                                <li key={t} className="flex items-start gap-3 text-sm text-body leading-relaxed">
                                    <Icon name="check" className="w-4 h-4 text-success shrink-0 mt-1" strokeWidth={2} />
                                    <span>{withCode(t)}</span>
                                </li>
                            ))}
                        </ul>
                        <p className="text-muted text-sm mb-6">
                            <span className="text-white font-semibold">NeuralMind Team, {paid.display}</span>,{' '}
                            {paid.seats.replace('-', '–')} seats, {paid.billing}: seats beyond one, priority support
                            and an annual invoice.
                        </p>
                        <div className="mt-auto flex flex-wrap gap-3">
                            <a href="/team" className="btn-secondary text-sm">
                                How teams use it
                            </a>
                            <a href="/pricing" className="text-electric hover:text-electric-bright text-sm font-medium self-center">
                                Pricing →
                            </a>
                        </div>
                    </div>

                    <div className="panel rounded-card p-6 md:p-8 flex flex-col">
                        <p className="eyebrow mb-3">For security review</p>
                        <h3 className="font-display text-2xl font-semibold text-white tracking-tight mb-5">
                            Local by default, verifiable per release
                        </h3>
                        <ul className="space-y-3 mb-6">
                            {security.map((t) => (
                                <li key={t} className="flex items-start gap-3 text-sm text-body leading-relaxed">
                                    <Icon name="check" className="w-4 h-4 text-success shrink-0 mt-1" strokeWidth={2} />
                                    <span>{withCode(t)}</span>
                                </li>
                            ))}
                        </ul>
                        <div className="mt-auto">
                            <a href="/security" className="btn-secondary text-sm">
                                Security, verification and compliance evidence
                            </a>
                        </div>
                    </div>
                </div>

                {/* The site's one offer, decided 2026-10-21: the paid assessment
                    on /services. Its fee isn't in commercial-terms.json, so no
                    price is quoted here; /services keeps its own wording. */}
                <div className="mt-6 panel-accent rounded-card p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-5">
                    <div className="max-w-2xl">
                        <h3 className="font-display text-lg font-semibold tracking-tight text-white mb-1.5">
                            Want it measured on your repos before a rollout?
                        </h3>
                        <p className="text-muted text-sm leading-relaxed">
                            The Codebase Fit Assessment benchmarks NeuralMind on one to three of your repos, on
                            your hardware, and ends in a written keep-or-skip recommendation. Fixed fee, per
                            organization.
                        </p>
                    </div>
                    <a href="/services#fit-assessment" className="btn-primary text-sm whitespace-nowrap">
                        About the assessment
                        <Icon name="arrow-right" className="w-4 h-4" />
                    </a>
                </div>
            </div>
        </section>
    );
}
