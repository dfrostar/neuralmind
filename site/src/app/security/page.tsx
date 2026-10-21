import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import Callout from '@/components/ui/Callout';
import { getLatestRelease, tagAtLeast } from '@/lib/release';
import { pageMetadata } from '@/lib/seo';
import { withCode } from '@/lib/ticks';
import type { Metadata } from 'next';

const GITHUB_URL = 'https://github.com/dfrostar/neuralmind';
const DOCS = 'https://docs.neuralmind.uk';
const COMPLIANCE_URL = `${GITHUB_URL}/blob/main/docs/COMPLIANCE-SUMMARY.md`;
const SECURITY_MD = `${GITHUB_URL}/blob/main/SECURITY.md`;
const LLM_DISCLOSURE = `${GITHUB_URL}/blob/main/docs/compliance/THIRD_PARTY_LLM_DISCLOSURE.md`;
const AIR_GAPPED = `${DOCS}/use-cases/air-gapped.html`;
const CUI_WALKTHROUGH = `${DOCS}/use-cases/cmmc-cui-enclave.html`;
const SSDF_DOC = `${DOCS}/compliance/SSDF.html`;
const SP800_53_DOC = `${DOCS}/compliance/SP800-53.html`;
const HARDENING_DOC = `${DOCS}/compliance/SP800-53-HARDENING.html`;
const NIST_DOC = `${DOCS}/compliance/NIST.html`;
const CLI_REF = `${DOCS}/wiki/CLI-Reference`;
// The VEX and the OSCAL component definition are living statements, so they
// link to main rather than to a release tag.
const VEX_URL = `${GITHUB_URL}/blob/main/security/neuralmind.openvex.json`;
const OSCAL_URL = `${GITHUB_URL}/blob/main/security/neuralmind.oscal-component-definition.json`;
const OIDC_ISSUER = 'https://token.actions.githubusercontent.com';
// Pins the workflow and the two refs a release runs from (main, a vX.Y.Z
// tag); the same patterns as docs/compliance/SSDF.md §2.
const identity = (workflow: string) =>
    `'^https://github\\.com/dfrostar/neuralmind/\\.github/workflows/${workflow}\\.yml@refs/(heads/main|tags/v[0-9]+\\.[0-9]+\\.[0-9]+)$'`;

// Signing and build provenance start with v4.14.0; older releases have
// nothing to verify, so the page says so instead of printing commands that
// would fail.
const FIRST_SIGNED = '4.14.0';

// Everything NeuralMind itself puts on the wire. Security reviews ask this
// first, and the honest answer is short but not "nothing" — the first build
// downloads a model, so "no network calls" would be false.
const network = [
    {
        what: 'Telemetry',
        detail: 'None — not opt-in, not anonymous. There is no telemetry mechanism in the product.',
    },
    {
        what: 'Embedding model, first build',
        detail: 'An HTTPS download of the public all-MiniLM-L6-v2 model, verified against a pinned SHA-256 — on first build, and again only if the cached copy is removed. It carries none of your data, and pre-seeding the model removes it entirely for air-gapped installs.',
    },
    {
        what: 'Opt-in LLM seeding',
        detail: 'Off by default. Only if you set NEURALMIND_LLM_SEED=1 and provide an Anthropic API key does it send README and architecture-doc prose — never source code — to seed synapse edges. Refused under security.profile: cui.',
    },
    {
        what: 'Audit forwarding',
        detail: 'Off by default. If you set security.audit_syslog, each audit record goes to the syslog target you name; under security.profile: cui only a unix socket or loopback address is accepted.',
    },
    {
        what: 'Your agent’s own traffic',
        detail: 'The context slice your agent sends to its model provider. NeuralMind makes it smaller; it does not control it.',
    },
];

// The controls a security team turns on, each with the command that shows
// it working. `since` is the release it shipped in; one on main but not yet
// released says so, judged against the latest release this build read.
const controls: { name: string; since?: string; body: string; cmd: string[]; href: string; link: string }[] = [
    {
        name: 'The CUI-enclave posture, as one setting',
        since: '4.16.0',
        body: '`security.profile: cui` in `neuralmind-backend.yaml` switches on OS-account identity, refuses an unencrypted disk, refuses `serve` beyond loopback or without its token, and refuses LLM seeding even when switched on. Each refusal lands in the audit log; a contradictory or misspelled profile fails closed. An administrator’s machine policy keeps it on.',
        cmd: ['neuralmind doctor .   # checks the profile as a unit; fails when the OS FIPS mode is off'],
        href: CUI_WALKTHROUGH,
        link: 'CUI enclave walkthrough',
    },
    {
        name: 'SP 800-53 hardening check',
        since: '4.19.0',
        body: '17 rules, each mapped to the SP 800-53 Rev. 5 controls it supports: the security profile and machine policy, OS identity, file permissions, verified encrypted storage, the OS FIPS mode, the daemon, the audit log’s chain, signed and anchored checkpoints, and forwarding with nothing waiting. A rule that can’t be checked fails.',
        cmd: ['neuralmind hardening .   # exits 1 when any rule fails'],
        href: HARDENING_DOC,
        link: 'The hardening baseline',
    },
    {
        name: 'Audit records to your SIEM as they are written',
        since: '4.19.0',
        body: 'Set `security.audit_syslog` and every audit record goes to syslog right after it is written, from the CLI, the MCP server, the hooks and the daemon, with its hash so the SIEM can check the chain. A record that can’t be written raises an `alert`-severity message at once. Records a dead target missed are sent when it is back.',
        cmd: ['neuralmind audit forward .   # send what is waiting, on demand'],
        href: `${CLI_REF}#audit-forward`,
        link: 'audit forward',
    },
    {
        name: 'An audit log you can’t silently shorten',
        since: '4.16.0',
        body: 'Every query, build and admin change is logged with its actor in an append-only SHA-256 hash chain. Signed checkpoints, anchored where the developer can’t write, make removing the newest records or recomputing the chain fail verification.',
        cmd: ['neuralmind audit verify .', 'neuralmind audit checkpoint .', 'neuralmind audit export . --format cef -o audit.cef'],
        href: `${CLI_REF}#audit-verify`,
        link: 'audit commands',
    },
    {
        name: 'Secrets found before they’re indexed',
        body: 'Reports credentials in the files a build would index, so they can be removed and rotated before they reach the index, a commit or an agent’s context. `build --redact-secrets` is a backstop for indexed text, not a substitute for rotating a key.',
        cmd: ['neuralmind scan-for-secrets .'],
        href: `${CLI_REF}#scan-for-secrets`,
        link: 'scan-for-secrets',
    },
    {
        name: 'Every place it keeps data',
        since: '4.18.0',
        body: 'Lists every location NeuralMind writes for a project, in it and outside it, and the integrations that write them — each with what it holds and the command that removes it. Read-only; for retention reviews and erasure requests.',
        cmd: ['neuralmind data-locations . --json'],
        href: `${CLI_REF}#data-locations-v4180`,
        link: 'data-locations',
    },
];

export const metadata: Metadata = pageMetadata({
    path: '/security',
    title: 'Security, Verification & Compliance — NeuralMind',
    description:
        'Verify NeuralMind releases (cosign, attestations, SBOM, VEX), run it air-gapped, and turn on the CUI profile, SP 800-53 hardening and syslog audit.',
    keywords: [
        'NeuralMind security',
        'AI coding tool security review',
        'CycloneDX SBOM',
        'cosign verify',
        'gh attestation verify',
        'OpenVEX',
        'NIST SSDF',
        'SP 800-53 hardening',
        'OSCAL component definition',
        'CMMC CUI enclave',
        'syslog audit forwarding',
        'air-gapped AI coding agent',
    ],
});

function Section({ id, title, lede, children }: { id: string; title: string; lede?: React.ReactNode; children: React.ReactNode }) {
    return (
        <section id={id} className="mb-14 scroll-mt-24">
            <h2 className="font-display text-2xl font-bold text-white tracking-tight mb-2">{title}</h2>
            {lede && <p className="text-muted leading-relaxed mb-5">{lede}</p>}
            {children}
        </section>
    );
}

function Commands({ lines }: { lines: { comment?: string; cmd: string }[] }) {
    return (
        <div className="bg-carbon rounded-control border border-carbon-border p-4 font-mono text-xs text-body overflow-x-auto">
            {lines.map((l, i) => (
                <div key={i} className={i > 0 ? 'mt-3' : undefined}>
                    {l.comment && <p className="text-faint"># {l.comment}</p>}
                    <p className="break-all">
                        <span className="text-faint select-none">$ </span>
                        {l.cmd.split(/\s+#\s/)[0]}
                        {l.cmd.includes(' # ') && (
                            <span className="text-faint select-none">{`   # ${l.cmd.split(/\s+#\s/)[1]}`}</span>
                        )}
                    </p>
                </div>
            ))}
        </div>
    );
}

const link = 'text-electric hover:text-electric-bright';

export default async function SecurityPage() {
    const rel = await getLatestRelease();
    const version = rel.tag;
    const released = (since: string) => tagAtLeast(version, since);
    const tarballUrl = `${GITHUB_URL}/archive/refs/tags/${version}.tar.gz`;
    const image = `ghcr.io/dfrostar/neuralmind:${version}`;
    const signed = released(FIRST_SIGNED);
    const nav = [
        ['verify', 'Verify a release'],
        ['network', 'Network'],
        ['air-gapped', 'Air-gapped'],
        ['controls', 'Controls'],
        ['evidence', 'Compliance evidence'],
        ['disclosure', 'Disclosure'],
    ];

    return (
        <>
            <Navbar />
            <main className="max-w-4xl mx-auto px-4 md:px-6 pt-32 pb-16">
                <header className="mb-12 pb-8 border-b border-carbon-border">
                    <p className="eyebrow mb-4">For security and compliance teams</p>
                    <h1 className="font-display text-3xl md:text-display font-bold text-white mb-5 leading-display tracking-tighter">
                        Security, verification and compliance evidence
                    </h1>
                    <p className="text-lg text-body leading-relaxed mb-6 max-w-2xl">
                        What NeuralMind sends over the network, how to verify what you install, how to run it
                        with no network at all, and the controls a regulated deployment turns on — each with
                        the command that shows it.
                    </p>
                    <nav aria-label="On this page" className="flex flex-wrap gap-2">
                        {nav.map(([id, label]) => (
                            <a
                                key={id}
                                href={`#${id}`}
                                className="px-3 py-1.5 rounded-control border border-carbon-border bg-carbon-card text-sm text-body hover:text-white hover:border-carbon-line"
                            >
                                {label}
                            </a>
                        ))}
                    </nav>
                </header>

                {/* Latest release */}
                <div className="panel rounded-card p-5 md:p-6 mb-14 flex items-center justify-between flex-wrap gap-4">
                    <div>
                        <p className="eyebrow mb-1">Latest release</p>
                        <span className="text-electric-bright font-mono font-bold text-xl">{version}</span>
                        {rel.date && <span className="text-muted ml-3">Released {rel.date}</span>}
                    </div>
                    <div className="flex gap-4">
                        <a href={rel.htmlUrl} target="_blank" rel="noopener noreferrer" className={`text-sm ${link}`}>
                            Release notes →
                        </a>
                        <a href={rel.pypiUrl} target="_blank" rel="noopener noreferrer" className={`text-sm ${link}`}>
                            PyPI →
                        </a>
                    </div>
                </div>

                <Section
                    id="verify"
                    title="Verify a release"
                    lede="Each container image is signed with cosign, keyless: the signature is bound to the release workflow’s GitHub identity and logged in Sigstore’s public transparency log. The image, wheel and sdist carry build-provenance attestations naming the workflow and commit that built them. The release workflow runs the same checks before :latest moves."
                >
                    {signed ? (
                        <Commands
                            lines={[
                                {
                                    comment: 'The image signature',
                                    cmd: `cosign verify ${image} --certificate-identity-regexp ${identity('docker-publish')} --certificate-oidc-issuer ${OIDC_ISSUER}`,
                                },
                                {
                                    comment: 'The image’s build provenance',
                                    cmd: `gh attestation verify oci://${image} --repo dfrostar/neuralmind --cert-identity-regex ${identity('docker-publish')}`,
                                },
                                {
                                    comment: 'A wheel or sdist you downloaded',
                                    cmd: `gh attestation verify neuralmind-${rel.version}-py3-none-any.whl --repo dfrostar/neuralmind --cert-identity-regex ${identity('release')}`,
                                },
                                { comment: 'The source tarball: compare with the SHA-256 on the release page', cmd: `curl -sL ${tarballUrl} | sha256sum` },
                            ]}
                        />
                    ) : (
                        <p className="text-muted text-sm">
                            {version} was released before signing began (v{FIRST_SIGNED}), so it has no signature or
                            attestation to verify. The commands appear here once a signed release is current.
                        </p>
                    )}

                    <div className="grid sm:grid-cols-3 gap-4 mt-6">
                        <div className="panel rounded-card p-5">
                            <p className="text-white font-semibold text-sm mb-1.5">SBOM</p>
                            <p className="text-muted text-sm leading-relaxed mb-3">A CycloneDX SBOM for every release since v4.0.0.</p>
                            {rel.sbomUrl ? (
                                <a href={rel.sbomUrl} target="_blank" rel="noopener noreferrer" className={`text-sm font-mono ${link}`}>
                                    SBOM for {version} →
                                </a>
                            ) : (
                                <a href={`${GITHUB_URL}/actions/workflows/sbom.yml`} target="_blank" rel="noopener noreferrer" className={`text-sm ${link}`}>
                                    Still generating — SBOM workflow →
                                </a>
                            )}
                        </div>
                        <div className="panel rounded-card p-5">
                            <p className="text-white font-semibold text-sm mb-1.5">VEX</p>
                            <p className="text-muted text-sm leading-relaxed mb-3">
                                Dependency advisories NeuralMind&rsquo;s code can&rsquo;t reach, each marked not affected with the
                                reason. Pass it to Grype or Trivy with <code className="font-mono text-code-inline">--vex</code>.
                            </p>
                            <a href={VEX_URL} target="_blank" rel="noopener noreferrer" className={`text-sm ${link}`}>
                                OpenVEX document →
                            </a>
                        </div>
                        <div className="panel rounded-card p-5">
                            <p className="text-white font-semibold text-sm mb-1.5">SSDF</p>
                            <p className="text-muted text-sm leading-relaxed mb-3">
                                Every NIST SP 800-218 practice, mapped to the workflow, file or check that is its evidence.
                            </p>
                            <a href={SSDF_DOC} target="_blank" rel="noopener noreferrer" className={`text-sm ${link}`}>
                                SSDF mapping →
                            </a>
                        </div>
                    </div>
                </Section>

                <Section
                    id="network"
                    title="What goes over the network"
                    lede="By default, NeuralMind sends no telemetry and transmits no repository content off your machine. The complete list:"
                >
                    <div className="panel rounded-card divide-y divide-carbon-border">
                        {network.map((n) => (
                            <div key={n.what} className="p-5 grid md:grid-cols-[13rem_1fr] gap-1 md:gap-6">
                                <p className="text-white font-semibold text-sm">{n.what}</p>
                                <p className="text-muted text-sm leading-relaxed">{n.detail}</p>
                            </div>
                        ))}
                    </div>
                    <p className="text-muted text-sm mt-3">
                        Details:{' '}
                        <a href={LLM_DISCLOSURE} target="_blank" rel="noopener noreferrer" className={link}>
                            third-party LLM disclosure
                        </a>
                    </p>
                </Section>

                <Section
                    id="air-gapped"
                    title="Air-gapped install"
                    lede="Bundle the wheels and the embedding model on a connected machine with the target’s Python version, verify them there, and install with no index. The first build then makes no network request."
                >
                    <Commands
                        lines={[
                            { comment: 'On a connected machine', cmd: 'pip download neuralmind --dest ./offline-bundle' },
                            { cmd: 'python -c "from neuralmind.onnx_embedder import OnnxMiniLMEmbedder as E; E()([\'warm\'])"' },
                            { comment: 'On the air-gapped machine', cmd: 'pip install --no-index --find-links offline-bundle neuralmind' },
                            { comment: 'Or point at a model directory you manage', cmd: 'export NEURALMIND_ONNX_MODEL_DIR=/opt/models/all-MiniLM-L6-v2/onnx' },
                        ]}
                    />
                    <p className="text-muted text-sm mt-3">
                        The full procedure, platform pinning and verifying the bundle before it crosses:{' '}
                        <a href={AIR_GAPPED} target="_blank" rel="noopener noreferrer" className={link}>
                            running air-gapped →
                        </a>
                    </p>
                </Section>

                <Section
                    id="controls"
                    title="Controls you can turn on"
                    lede="Each is free at one seat, like every feature. A version tag says which release a control shipped in."
                >
                    <div className="space-y-4">
                        {controls.map((c) => (
                            <article key={c.name} className="panel rounded-card p-5 md:p-6">
                                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 mb-2">
                                    <h3 className="font-display text-title-sm font-semibold text-white tracking-tight">{c.name}</h3>
                                    {c.since && (
                                        <span className="font-mono text-eyebrow uppercase tracking-eyebrow text-faint">
                                            v{c.since}
                                            {released(c.since) ? '+' : ' · in the next release, on main now'}
                                        </span>
                                    )}
                                </div>
                                <p className="text-muted text-sm leading-relaxed mb-4">{withCode(c.body)}</p>
                                <Commands lines={c.cmd.map((cmd) => ({ cmd }))} />
                                <a href={c.href} target="_blank" rel="noopener noreferrer" className={`inline-block mt-3 text-sm ${link}`}>
                                    {c.link} →
                                </a>
                            </article>
                        ))}
                    </div>
                </Section>

                <Section
                    id="evidence"
                    title="Compliance evidence"
                    lede="NeuralMind provides evidence your reviewers can map to controls; whether a deployment meets a framework is decided by assessing that deployment. NeuralMind itself holds no certification."
                >
                    <div className="grid sm:grid-cols-2 gap-4">
                        <div className="panel rounded-card p-5">
                            <p className="text-white font-semibold text-sm mb-1.5">
                                SP 800-53 OSCAL component definition
                                {!released('4.19.0') && <span className="ml-2 font-mono text-eyebrow uppercase tracking-eyebrow text-faint">on main</span>}
                            </p>
                            <p className="text-muted text-sm leading-relaxed mb-3">
                                The 21 SP 800-53 Rev. 5 controls NeuralMind touches, what it implements for each and what
                                stays yours, as OSCAL 1.1.3 a GRC tool can import into a System Security Plan.
                            </p>
                            <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                                <a href={OSCAL_URL} target="_blank" rel="noopener noreferrer" className={link}>
                                    OSCAL JSON →
                                </a>
                                <a href={SP800_53_DOC} target="_blank" rel="noopener noreferrer" className={link}>
                                    Readable version →
                                </a>
                            </div>
                        </div>
                        <div className="panel rounded-card p-5">
                            <p className="text-white font-semibold text-sm mb-1.5">NIST: what applies, and where it stands</p>
                            <p className="text-muted text-sm leading-relaxed mb-3">
                                Which NIST documents you&rsquo;ll be asked about — SSDF, SP 800-171 and CMMC Level 2,
                                SP 800-53, FIPS 140-3, the AI RMF — depending on who you are, and where NeuralMind
                                stands on each.
                            </p>
                            <a href={NIST_DOC} target="_blank" rel="noopener noreferrer" className={`text-sm ${link}`}>
                                NIST overview →
                            </a>
                        </div>
                    </div>
                    <p className="text-muted text-sm mt-4 leading-relaxed">
                        Framework mappings for GDPR, SOC 2, CMMC 2.0, HIPAA, ISO 27017 and NIST AI RMF, and the
                        audit trail, SBOM and hash chain behind them:{' '}
                        <a href={COMPLIANCE_URL} target="_blank" rel="noopener noreferrer" className={link}>
                            COMPLIANCE-SUMMARY.md
                        </a>
                        . Next audit target: a SOC 2 Type I report, Q3 2027.
                    </p>
                </Section>

                <Section id="disclosure" title="Vulnerability reports">
                    <div className="panel rounded-card p-6">
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 mb-3 rounded-pill text-xs font-medium bg-success/10 text-success border border-success/20">
                            <span className="w-1.5 h-1.5 rounded-pill bg-success"></span>
                            No open vulnerability reports
                        </span>
                        <p className="text-muted text-sm leading-relaxed mb-2">
                            No externally reported vulnerabilities to date. Issues found internally are fixed and
                            called out in the release notes, and advisories against third-party dependencies are
                            tracked with a written, reachability-based disposition in SECURITY.md.
                        </p>
                        <p className="text-muted text-sm">
                            Found something? Responsible disclosure is welcome —{' '}
                            <a href={SECURITY_MD} target="_blank" rel="noopener noreferrer" className={link}>
                                see SECURITY.md for how to report it
                            </a>
                            .
                        </p>
                    </div>
                </Section>

                <Callout variant="note" title="Evaluating for a team?">
                    The{' '}
                    <a href="/services#fit-assessment" className={link}>
                        Codebase Fit Assessment
                    </a>{' '}
                    runs NeuralMind on one to three of your repos, on your hardware, and ends in a written
                    keep-or-skip recommendation. Questions about a review:{' '}
                    <a href="mailto:hello@neuralmind.uk" className={link}>
                        hello@neuralmind.uk
                    </a>
                    .
                </Callout>
            </main>
            <Footer />
        </>
    );
}
