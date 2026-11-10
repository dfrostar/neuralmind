import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import EvidenceBadge, { type EvidenceLevel } from '@/components/ui/EvidenceBadge';
import { pageMetadata } from '@/lib/seo';
import {
    blob,
    explorationShare,
    heldOutHook,
    publicBenchmark,
    retrievalEval,
    reviewDrift,
    taskOutcomePilot,
} from '@/lib/evidence';
import terms from '../../../../commercial-terms.json';
import type { Metadata } from 'next';

export const metadata: Metadata = pageMetadata({
    path: '/consultancies',
    title: 'For Consultancies: What Client Executives Ask — NeuralMind',
    description:
        'What a client’s CTO, CISO and CFO ask before a contractor’s coding agent touches their code, answered with the evidence and the misses we publish.',
    keywords: [
        'AI coding agent vendor review',
        'consultancy client code review',
        'contractor AI tool security questionnaire',
        'coding agent CISO questions',
        'AI coding agent cost evidence',
        'NeuralMind for consultancies',
    ],
    ogTitle: 'What your client’s CTO, CISO and CFO will ask',
    ogDescription:
        'Each question answered with the evidence a reviewer can check, and what NeuralMind does not do, stated beside it.',
});

// The page the consultancy positioning (docs/use-cases/consultancy-client-code-review.md)
// points a client's executives to. Every figure is rendered from evidence.ts,
// which reads claims.json and the committed runs; the misses sit beside the
// wins on purpose, because a technical buyer finds them anyway.

type Answer = {
    q: string;
    a: React.ReactNode;
    evidence?: EvidenceLevel;
    href?: string;
    link?: string;
};

const team = terms.pricing.team;
const pilot = taskOutcomePilot.figures;
const share = explorationShare;

const roles: { id: string; role: string; who: string; answers: Answer[] }[] = [
    {
        id: 'cto',
        role: 'CTO',
        who: 'Yours and the client’s: does it find the right code in a repository nobody on your team wrote?',
        answers: [
            {
                q: 'Does it find the right file in code it has never seen?',
                a: (
                    <>
                        On the public benchmark, four pinned open-source repositories and 40
                        pre-registered questions, NeuralMind’s context held the gold file on{' '}
                        {publicBenchmark.found('neuralmind')} queries, against keyword ripgrep’s{' '}
                        {publicBenchmark.found('ripgrep')}. On the 150-question retrieval eval a gold file
                        was in the top five for {retrievalEval.hitAt5}, with {retrievalEval.misses} misses
                        published. Both rerun from a fresh clone.
                    </>
                ),
                evidence: 'reproducible',
                href: '/benchmark/',
                link: 'The benchmark, query by query',
            },
            {
                q: 'And on a large repository, on real bug fixes?',
                a: (
                    <>
                        Weaker, and we publish it. On {heldOutHook.tasks} hermes-agent bug-fix tasks kept out
                        of all tuning, the block the prompt hook adds to each prompt named a file the fix
                        changed on {heldOutHook.byDefault.named} of {heldOutHook.tasks} by default, and on{' '}
                        {heldOutHook.withFlag.named} of {heldOutHook.tasks} with the opt-in{' '}
                        <code className="font-mono text-body">{heldOutHook.flag}</code>. Offline replays
                        through the real hook: whether an agent then does better is not measured here.
                    </>
                ),
                evidence: heldOutHook.evidence,
                href: blob(heldOutHook.source),
                link: 'The held-out replay',
            },
            {
                q: 'Can it review a change for us?',
                a: (
                    <>
                        Not better than what you already have. On {reviewDrift.pairs} held-out file pairs
                        from real commits, <code className="font-mono text-body">neuralmind review</code> put
                        the missing file in its top ten {reviewDrift.reviewHits} times, git co-change history{' '}
                        {reviewDrift.cochangeHits}. <code className="font-mono text-body">neuralmind drift</code>{' '}
                        fired on {reviewDrift.fixHits} of {reviewDrift.fixCommits} bug fixes and{' '}
                        {reviewDrift.controlHits} of {reviewDrift.controlCommits} other commits alike. Both
                        fail their pre-registered gate, on cold indexes.
                    </>
                ),
                evidence: reviewDrift.evidence,
                href: blob(reviewDrift.source),
                link: 'The review and drift eval',
            },
        ],
    },
    {
        id: 'ciso',
        role: 'CIO / CISO',
        who: 'Mostly the client’s: what does a contractor’s tool do with our code, and what can we verify?',
        answers: [
            {
                q: 'What does NeuralMind send off the machine?',
                a: (
                    <>
                        By default, nothing: no telemetry, and no repository content off the machine it runs
                        on. The index is built and queried locally. Your coding agent is a separate matter:
                        it sends what it reads to its model provider, so approve the agent on its own terms.{' '}
                        <code className="font-mono text-body">neuralmind data-locations .</code> lists every
                        file NeuralMind writes.
                    </>
                ),
                href: '/security/#network',
                link: 'Every network path, listed',
            },
            {
                q: 'Can we verify what we install?',
                a: (
                    <>
                        Every container image is signed with cosign, keyless, with build attestations, a
                        CycloneDX SBOM for every release and an OpenVEX statement. Every change runs CodeQL,
                        bandit and pip-audit, and the Actions it uses are pinned.
                    </>
                ),
                href: '/security/#verify',
                link: 'The verification commands',
            },
            {
                q: 'Does it fit a regulated environment?',
                a: (
                    <>
                        <code className="font-mono text-body">security.profile: cui</code> switches on the
                        CUI-enclave posture as one setting, a 17-rule hardening check maps to SP 800-53 Rev. 5,
                        an OSCAL component definition is published, FIPS-mode hosts are supported, and{' '}
                        <code className="font-mono text-body">neuralmind scan-for-secrets .</code> runs before
                        the first build. Most of a vendor-review questionnaire is answered from the compliance
                        docs without a call.
                    </>
                ),
                href: '/security/#controls',
                link: 'Controls and compliance evidence',
            },
            {
                q: 'What don’t you have?',
                a: (
                    <>
                        A certification: NeuralMind is not certified against any framework, and the docs map
                        controls rather than claim compliance. SSO / SAML is on the roadmap, not shipped.
                    </>
                ),
            },
        ],
    },
    {
        id: 'cfo',
        role: 'CFO',
        who: 'What does it cost, and what does it change on the agent bill? The weakest story today, so here it is plainly.',
        answers: [
            {
                q: 'Does it change what we pay for agents?',
                a: (
                    <>
                        Not measurably, so far. In a pre-registered pilot, {pilot.tasks} bug-fix tasks run{' '}
                        {pilot.runs} times, Claude Code solved {pilot.tasks_solved.neuralmind} tasks with
                        NeuralMind and {pilot.tasks_solved.baseline} without, at a median cost change of{' '}
                        {pilot.median_cost_change} ({pilot.cost_change_ci95}); the agent called none of
                        NeuralMind’s tools. The per-question token ratio is real, and it applies only to the
                        reading and searching part of a session.
                    </>
                ),
                evidence: taskOutcomePilot.evidence,
                href: '/benchmark/#task-outcomes',
                link: 'The pilot',
            },
            {
                q: 'How big is that part of our bill?',
                a: (
                    <>
                        Measure it: <code className="font-mono text-body">neuralmind measure sessions</code>{' '}
                        reads the sessions your agents already recorded, on your machine, and reports the share
                        that was reading and searching code. For one developer’s {share.claudeCode.sessions}{' '}
                        Claude Code sessions it was {share.claudeCode.ofBilled} of the billed prompt. That
                        bounds what any retrieval tool can affect, ours included, so it is also the number that
                        tells you not to overpay anyone.
                    </>
                ),
                evidence: share.evidence,
                href: '/benchmark/#exploration-share',
                link: 'The field report',
            },
            {
                q: 'What does it cost?',
                a: (
                    <>
                        Free at one seat, every feature, no signup and no expiry, so a pilot on a client
                        engagement costs nothing. Team is {team.display} ({team.seats} seats, {team.billing})
                        for more seats and priority support.{' '}
                        <code className="font-mono text-body">neuralmind savings --cost</code> prints a labelled
                        token estimate per engagement for a client report.
                    </>
                ),
                href: '/pricing/',
                link: 'Pricing',
            },
        ],
    },
    {
        id: 'operations',
        role: 'Operations',
        who: 'Can every engineer run it on every client repository the same way?',
        answers: [
            {
                q: 'What do we install, and where?',
                a: (
                    <>
                        One <code className="font-mono text-body">pip install neuralmind</code> on the
                        engineer’s machine and one <code className="font-mono text-body">neuralmind build .</code>{' '}
                        per repository. There is no service to host and nothing for the client to procure; each
                        client’s index lives in that repository’s own{' '}
                        <code className="font-mono text-body">.neuralmind/</code> folder, so engagements stay
                        apart.
                    </>
                ),
                href: '/measure-your-own/',
                link: 'Measure it on a repo first',
            },
        ],
    },
];

export default function ConsultanciesPage() {
    return (
        <>
            <Navbar />
            <main className="max-w-4xl mx-auto px-4 md:px-6 pt-32 pb-16">
                <header className="mb-12 pb-8 border-b border-carbon-border">
                    <h1 className="font-display text-3xl md:text-display font-bold text-white mb-5 leading-display tracking-tighter">
                        What your client’s executives will ask
                    </h1>
                    <p className="text-lg text-body leading-relaxed mb-4">
                        In a small consultancy one founder often answers for the CTO, the CISO and the CFO at
                        once, and the client’s own executives ask the same questions before a contractor’s
                        coding agent goes near their code.
                    </p>
                    <p className="text-muted leading-relaxed">
                        Each answer below links to the evidence a reviewer can check, and where NeuralMind
                        doesn’t help, the answer says so. For the engagement itself, see the{' '}
                        <a href="https://docs.neuralmind.uk/use-cases/consultancy-client-code-review.html" className="link">
                            client code-review walkthrough
                        </a>
                        .
                    </p>
                    <nav aria-label="Roles" className="flex flex-wrap gap-2 mt-6">
                        {roles.map((r) => (
                            <a
                                key={r.id}
                                href={`#${r.id}`}
                                className="px-2.5 py-1 rounded-control border border-carbon-line text-body text-sm hover:border-accent"
                            >
                                {r.role}
                            </a>
                        ))}
                    </nav>
                </header>

                {roles.map((r) => (
                    <section key={r.id} id={r.id} className="mb-14 scroll-mt-24">
                        <h2 className="font-display text-xl font-bold text-white mb-2">{r.role}</h2>
                        <p className="text-muted mb-6">{r.who}</p>
                        <div className="space-y-4">
                            {r.answers.map((x) => (
                                <div key={x.q} className="card rounded-card p-6">
                                    <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                                        <h3 className="font-display text-lg font-bold text-white">{x.q}</h3>
                                        {x.evidence && <EvidenceBadge level={x.evidence} />}
                                    </div>
                                    <p className="text-body text-sm leading-relaxed">{x.a}</p>
                                    {x.href && x.link && (
                                        <a href={x.href} className="link text-sm mt-3 inline-block">
                                            {x.link}
                                        </a>
                                    )}
                                </div>
                            ))}
                        </div>
                    </section>
                ))}

                <section className="card rounded-card p-6">
                    <h2 className="font-display text-xl font-bold text-white mb-2">Ask us the rest</h2>
                    <p className="text-body text-sm leading-relaxed">
                        If your client’s questionnaire asks something this page doesn’t answer, send it to{' '}
                        <a href={`mailto:${terms.entity.contact_email}`} className="link">
                            {terms.entity.contact_email}
                        </a>
                        . We answer from the docs, and say when the answer is no.
                    </p>
                </section>
            </main>
            <Footer />
        </>
    );
}
