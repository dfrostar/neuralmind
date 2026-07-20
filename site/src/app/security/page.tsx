import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import { getLatestRelease } from '@/lib/release';

const GITHUB_URL = 'https://github.com/dfrostar/neuralmind';
const COMPLIANCE_URL = `${GITHUB_URL}/blob/main/docs/COMPLIANCE-SUMMARY.md`;

export default async function SecurityPage() {
    const rel = await getLatestRelease();
    const version = rel.tag;                          // e.g. "v0.42.1"
    const versionNumber = version.replace(/^v/, '');  // e.g. "0.42.1"
    const releaseDate = rel.date;
    const releaseUrl = rel.htmlUrl;                   // GitHub release page (always exists)
    const pypiUrl = `https://pypi.org/project/neuralmind/${versionNumber}/`;
    const sbomUrl = releaseUrl;                       // CycloneDX SBOM is attached to the release
    const tarballUrl = `${GITHUB_URL}/archive/refs/tags/${version}.tar.gz`;

    return (
        <>
            <Navbar />
            <main className="max-w-4xl mx-auto px-4 md:px-6 py-16">
                <h1 className="font-display text-4xl md:text-5xl font-bold text-white mb-4">
                    Security Posture
                </h1>
                <p className="text-lg text-slate-300 mb-12 max-w-2xl">
                    Transparent security information for NeuralMind. No uptime theater — just the facts security teams ask about.
                </p>

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
                            A CycloneDX SBOM is generated for every release and attached to the GitHub release.
                        </p>
                        <a href={sbomUrl} target="_blank" rel="noopener noreferrer"
                           className="inline-flex items-center gap-2 text-electric hover:text-electric-bright transition-colors font-mono text-sm">
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            Download SBOM (JSON) →
                        </a>
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
                            <p className="text-slate-500">Compare against the SHA-256 on the GitHub release page.</p>
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
                                No Known Vulnerabilities
                            </span>
                        </div>
                        <p className="text-slate-400 text-sm">
                            Last report: — (none received to date). Responsible disclosure welcome.
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
                                NeuralMind&apos;s architecture supports GDPR, SOC 2, HIPAA, and ISO 27017 requirements.
                                We provide the evidence (audit trail, SBOM, hash chain); certification is maintained by the
                                operator. See <a href={COMPLIANCE_URL} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">COMPLIANCE-SUMMARY.md</a>.
                            </p>
                        </div>
                        <div className="flex gap-3 flex-wrap">
                            <span className="px-3 py-1.5 rounded-lg bg-carbon border border-carbon-border text-xs text-slate-300">GDPR</span>
                            <span className="px-3 py-1.5 rounded-lg bg-carbon border border-carbon-border text-xs text-slate-300">SOC 2</span>
                            <span className="px-3 py-1.5 rounded-lg bg-carbon border border-carbon-border text-xs text-slate-300">HIPAA</span>
                            <span className="px-3 py-1.5 rounded-lg bg-carbon border border-carbon-border text-xs text-slate-300">ISO 27017</span>
                            <span className="px-3 py-1.5 rounded-lg bg-carbon border border-carbon-border text-xs text-slate-300">NIST AI RMF</span>
                        </div>
                        <div>
                            <p className="text-slate-400 text-sm">
                                Next certification target: <span className="text-white font-semibold">SOC 2 Type I</span> — Q3 2027
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
                        <p className="text-slate-400 text-sm">
                            Introduced in v0.27.0 (B-Audit). <a href={`${GITHUB_URL}/blob/main/RELEASE_NOTES_v0.27.0.md`} target="_blank" rel="noopener noreferrer" className="text-electric hover:text-electric-bright">Release notes →</a>
                        </p>
                    </div>
                </section>

                <div className="mt-12 pt-8 border-t border-carbon-border text-center">
                    <p className="text-slate-500 text-sm">
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
