import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import { getLatestRelease } from '@/lib/release';
import { pageMetadata } from '@/lib/seo';
import type { Metadata } from 'next';

const GITHUB_URL = 'https://github.com/dfrostar/neuralmind';
const COMPLIANCE_URL = `${GITHUB_URL}/blob/main/docs/COMPLIANCE-SUMMARY.md`;
const SECURITY_MD = `${GITHUB_URL}/blob/main/SECURITY.md`;
const LLM_DISCLOSURE = `${GITHUB_URL}/blob/main/docs/compliance/THIRD_PARTY_LLM_DISCLOSURE.md`;
const AIR_GAPPED = 'https://docs.neuralmind.uk/use-cases/air-gapped.html';
const SSDF_DOC = 'https://docs.neuralmind.uk/compliance/SSDF.html';
// The VEX is a living statement of current knowledge, so it links to main
// rather than to the release tag; each tag also carries the copy it shipped.
const VEX_URL = `${GITHUB_URL}/blob/main/security/neuralmind.openvex.json`;
const OIDC_ISSUER = 'https://token.actions.githubusercontent.com';
// Pins the workflow and the two refs a release runs from (main, a vX.Y.Z
// tag); the same patterns as docs/compliance/SSDF.md §2.
const identity = (workflow: string) =>
    `'^https://github\\.com/dfrostar/neuralmind/\\.github/workflows/${workflow}\\.yml@refs/(heads/main|tags/v[0-9]+\\.[0-9]+\\.[0-9]+)$'`;

// Signing and build provenance start with v4.14.0; older releases have
// nothing to verify, so the page says so instead of printing commands
// that would fail.
const FIRST_SIGNED: [number, number, number] = [4, 14, 0];
function isSigned(tag: string): boolean {
    const parts = tag.replace(/^v/, '').split('.').map((p) => parseInt(p, 10));
    if (parts.length < 3 || parts.some(Number.isNaN)) return false;
    for (let i = 0; i < 3; i++) {
        if (parts[i] !== FIRST_SIGNED[i]) return parts[i] > FIRST_SIGNED[i];
    }
    return true;
}

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
        detail: 'Off by default. Only if you set NEURALMIND_LLM_SEED=1 and provide an Anthropic API key does it send README and architecture-doc prose — never source code — to seed synapse edges.',
    },
    {
        what: 'Your agent’s own traffic',
        detail: 'The context slice your agent sends to its model provider. NeuralMind makes it smaller; it does not control it.',
    },
];

export const metadata: Metadata = pageMetadata({
    path: '/security',
    title: 'Security & Supply Chain — NeuralMind',
    description:
        'NeuralMind security: what goes over the network (no telemetry), a CycloneDX SBOM per release, signed releases with provenance, OpenVEX and disclosure policy.',
    keywords: [
        'NeuralMind security',
        'AI coding tool security review',
        'CycloneDX SBOM',
        'no telemetry',
        'air-gapped AI coding agent',
        'hash-chained audit log',
        'signed container image',
        'OpenVEX',
        'NIST SSDF',
    ],
});

export default async function SecurityPage() {
    const rel = await getLatestRelease();
    const version = rel.tag;                          // e.g. "v1.9.1"
    const releaseDate = rel.date;
    const releaseUrl = rel.htmlUrl;                   // GitHub release page (always exists)
    const pypiUrl = rel.pypiUrl;                      // verified at build time
    const sbomUrl = rel.sbomUrl;                      // direct download, or null if none yet
    const tarballUrl = `${GITHUB_URL}/archive/refs/tags/${version}.tar.gz`;
    const image = `ghcr.io/dfrostar/neuralmind:${version}`;
    const signed = isSigned(version);

    return (
        <>
            <Navbar />
            <main className="max-w-4xl mx-auto px-4 md:px-6 pt-32 pb-16">
                <h1 className="font-display text-4xl md:text-5xl font-bold text-white mb-4">
                    Security Posture
                </h1>
                <p className="text-lg text-slate-300 mb-12 max-w-2xl">
                    The facts a security review asks for, stated plainly: what NeuralMind sends over
                    the network, what ships in each release, and how to report a vulnerability.
                </p>

                {/* Network */}
                <section className="mb-10">
                    <h2 className="font-display text-2xl font-bold text-white mb-4">What goes over the network</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl divide-y divide-carbon-border">
                        {network.map((n) => (
                            <div key={n.what} className="p-5 grid md:grid-cols-[13rem_1fr] gap-1 md:gap-6">
                                <p className="text-white font-semibold text-sm">{n.what}</p>
                                <p className="text-slate-400 text-sm leading-relaxed">{n.detail}</p>
                            </div>
                        ))}
                    </div>
                    <p className="text-slate-400 text-sm mt-3">
                        By default, NeuralMind sends no telemetry and transmits no repository content
                        off your machine. Details:{' '}
                        <a href={LLM_DISCLOSURE} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">
                            third-party LLM disclosure
                        </a>{' '}
                        ·{' '}
                        <a href={AIR_GAPPED} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">
                            running air-gapped
                        </a>
                    </p>
                </section>

                {/* Latest Release */}
                <section className="mb-10">
                    <h2 className="font-display text-2xl font-bold text-white mb-4">Latest Release</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6">
                        <div className="flex items-center justify-between flex-wrap gap-4">
                            <div>
                                <span className="text-electric-bright font-mono font-bold text-xl">{version}</span>
                                <span className="text-slate-400 ml-3">Released {releaseDate}</span>
                            </div>
                            <div className="flex gap-3">
                                <a href={releaseUrl} target="_blank" rel="noopener noreferrer"
                                   className="text-sm text-electric hover:text-electric-bright transition-colors">
                                    Release Notes →
                                </a>
                                <a href={pypiUrl} target="_blank" rel="noopener noreferrer"
                                   className="text-sm text-electric hover:text-electric-bright transition-colors">
                                    PyPI →
                                </a>
                            </div>
                        </div>
                    </div>
                </section>

                {/* SBOM & Supply Chain */}
                <section className="mb-10">
                    <h2 className="font-display text-2xl font-bold text-white mb-4">Software Bill of Materials</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6">
                        <p className="text-slate-300 mb-4">
                            A CycloneDX SBOM is generated for every release.
                        </p>
                        {sbomUrl ? (
                            <a href={sbomUrl} target="_blank" rel="noopener noreferrer"
                               className="inline-flex items-center gap-2 text-electric hover:text-electric-bright transition-colors font-mono text-sm">
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                </svg>
                                Download SBOM (JSON) for {version} →
                            </a>
                        ) : (
                            <p className="text-slate-400 text-sm">
                                The SBOM for {version} is still being generated — it appears here
                                shortly after each release. Meanwhile, see the{' '}
                                <a href={`${GITHUB_URL}/actions/workflows/sbom.yml`} target="_blank" rel="noopener noreferrer"
                                   className="text-electric hover:text-electric-bright">SBOM workflow →</a>
                            </p>
                        )}
                    </div>
                </section>

                {/* Release verification (NIST SP 800-218 PS.2) */}
                <section className="mb-10">
                    <h2 className="font-display text-2xl font-bold text-white mb-4">Verify a Release</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6">
                        <p className="text-slate-300 mb-4 text-sm">
                            From v4.14.0, each container image is signed with cosign. The signing is
                            keyless: the signature is bound to the release workflow&apos;s GitHub
                            identity and logged in Sigstore&apos;s public transparency log. The image,
                            wheel and sdist also carry build-provenance attestations naming the
                            workflow and commit that built them. The release workflow runs the same
                            checks before <code className="font-mono">:latest</code> moves.
                        </p>
                        {signed ? (
                            <div className="bg-carbon rounded-lg p-4 font-mono text-xs text-slate-400 break-all overflow-x-auto mb-4">
                                <p className="text-faint"># The image signature</p>
                                <p className="mb-3">
                                    cosign verify {image} --certificate-identity-regexp {identity('docker-publish')}{' '}
                                    --certificate-oidc-issuer {OIDC_ISSUER}
                                </p>
                                <p className="text-faint"># The image&apos;s build provenance</p>
                                <p className="mb-3">
                                    gh attestation verify oci://{image} --repo dfrostar/neuralmind --cert-identity-regex{' '}
                                    {identity('docker-publish')}
                                </p>
                                <p className="text-faint"># A wheel or sdist you downloaded</p>
                                <p>
                                    gh attestation verify neuralmind-{rel.version}-py3-none-any.whl --repo dfrostar/neuralmind{' '}
                                    --cert-identity-regex {identity('release')}
                                </p>
                            </div>
                        ) : (
                            <p className="text-slate-400 text-sm mb-4">
                                {version} was released before signing began, so it has no signature or
                                attestation to verify. The commands appear here once a signed release is current.
                            </p>
                        )}
                        <p className="text-slate-300 text-sm mb-2">
                            <strong className="text-white">Dependency advisories that don&apos;t apply.</strong>{' '}
                            ChromaDB advisories that NeuralMind&apos;s use of ChromaDB can&apos;t reach are recorded as not affected, with the reason for each, in an{' '}
                            <a href={VEX_URL} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">
                                OpenVEX document
                            </a>
                            . ChromaDB is an opt-in extra and isn&apos;t in the default install or the image. If you install it
                            and scan your environment, pass the document to your scanner (Grype or Trivy{' '}
                            <code className="font-mono">--vex</code>) so those advisories show as not affected.
                        </p>
                        <p className="text-slate-400 text-sm">
                            Every NIST SP 800-218 (SSDF) practice, mapped to its evidence:{' '}
                            <a href={SSDF_DOC} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">
                                SSDF.md →
                            </a>
                        </p>
                    </div>
                </section>

                {/* Source Integrity */}
                <section className="mb-10">
                    <h2 className="font-display text-2xl font-bold text-white mb-4">Source Integrity</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6">
                        <p className="text-slate-300 mb-3 text-sm">
                            Verify the tarball integrity against the release SHA-256:
                        </p>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-xs text-slate-400 break-all overflow-x-auto">
                            <p className="mb-1">curl -sL {tarballUrl} | sha256sum</p>
                            <p className="text-faint">Compare against the SHA-256 on the GitHub release page.</p>
                        </div>
                    </div>
                </section>

                {/* Vulnerability Reports */}
                <section className="mb-10">
                    <h2 className="font-display text-2xl font-bold text-white mb-4">Vulnerability Reports</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6">
                        <div className="flex items-center gap-3 mb-3">
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">
                                <span className="w-1.5 h-1.5 rounded-full bg-green-400"></span>
                                No open vulnerability reports
                            </span>
                        </div>
                        <p className="text-slate-400 text-sm leading-relaxed mb-2">
                            No externally reported vulnerabilities to date. Issues found internally are
                            fixed and called out in the release notes, and advisories against
                            third-party dependencies are tracked with a written, reachability-based
                            disposition in SECURITY.md.
                        </p>
                        <p className="text-slate-400 text-sm">
                            Found something? Responsible disclosure is welcome —{' '}
                            <a href={SECURITY_MD} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">
                                see SECURITY.md for how to report it
                            </a>
                            .
                        </p>
                    </div>
                </section>

                {/* Compliance & Certification */}
                <section className="mb-10">
                    <h2 className="font-display text-2xl font-bold text-white mb-4">Compliance & Certification</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6 space-y-4">
                        <div>
                            <p className="text-white font-semibold">Architecture supports, certification is yours</p>
                            <p className="text-slate-400 text-sm mt-1">
                                NeuralMind&apos;s architecture supports GDPR, SOC 2, CMMC 2.0, HIPAA, and ISO 27017 requirements.
                                We provide the evidence (audit trail, SBOM, hash chain); certification is maintained by the
                                operator. See <a href={COMPLIANCE_URL} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">COMPLIANCE-SUMMARY.md</a>.
                            </p>
                        </div>
                        <div className="flex gap-3 flex-wrap">
                            <span className="px-3 py-1.5 rounded-lg bg-carbon border border-carbon-border text-xs text-slate-300">GDPR</span>
                            <span className="px-3 py-1.5 rounded-lg bg-carbon border border-carbon-border text-xs text-slate-300">SOC 2</span>
                            <span className="px-3 py-1.5 rounded-lg bg-carbon border border-carbon-border text-xs text-slate-300">CMMC 2.0</span>
                            <span className="px-3 py-1.5 rounded-lg bg-carbon border border-carbon-border text-xs text-slate-300">HIPAA</span>
                            <span className="px-3 py-1.5 rounded-lg bg-carbon border border-carbon-border text-xs text-slate-300">ISO 27017</span>
                            <span className="px-3 py-1.5 rounded-lg bg-carbon border border-carbon-border text-xs text-slate-300">NIST AI RMF</span>
                        </div>
                        <div>
                            <p className="text-slate-400 text-sm">
                                Next audit target: a <span className="text-white font-semibold">SOC 2 Type I</span> report — Q3 2027
                            </p>
                        </div>
                    </div>
                </section>

                {/* Audit Trail */}
                <section className="mb-10">
                    <h2 className="font-display text-2xl font-bold text-white mb-4">Audit Trail</h2>
                    <div className="bg-carbon-card border border-carbon-border rounded-xl p-6">
                        <p className="text-slate-300 mb-3">
                            Every query is logged with a per-user actor attribution, stored locally in an append-only
                            SHA-256 hash chain. The trail is tamper-evident, searchable, and exportable in JSONL/CEF formats.
                        </p>
                        <div className="bg-carbon rounded-lg p-4 font-mono text-xs text-slate-400 overflow-x-auto">
                            <p><span className="text-faint select-none">$ </span>neuralmind audit verify</p>
                            <p><span className="text-faint select-none">$ </span>neuralmind audit export --format cef -o audit.cef</p>
                        </div>
                    </div>
                </section>

                <div className="mt-12 pt-8 border-t border-carbon-border text-center">
                    <p className="text-faint text-sm">
                        This page is updated quarterly, or on significant security events.
                    </p>
                    <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright text-sm transition-colors">
                        View on GitHub →
                    </a>
                </div>
            </main>
            <Footer />
        </>
    );
}
