// neuralmind:example-file — annotations here are syntax examples, not evidence.
import Icon, { type IconName } from '@/components/ui/Icon';
import SectionHeader from '@/components/ui/SectionHeader';
import { getLatestRelease, tagAtLeast } from '@/lib/release';
import { withCode } from '@/lib/ticks';

// Four pillars, one per question a developer asks before installing: does it
// find the right code, does it stay right, can I trust it, does it fit my
// agent. Twenty-two equal cards grouped by subsystem answered none of them.
//
// Every command exists in neuralmind/cli.py; every ratio is in
// site/claims.json. `since` names the release a recent feature shipped in;
// one that is on main but not yet released says so (see tagAtLeast).
type Item = { name: string; desc: string; since?: string };
type Pillar = { icon: IconName; title: string; lede: string; items: Item[]; link?: { href: string; label: string } };

const pillars: Pillar[] = [
    {
        icon: 'layers',
        title: 'The right code, in fewer tokens',
        lede: 'A map, the relevant symbols and their call edges instead of whole files, deeper only where the question needs it.',
        items: [
            { name: 'Progressive L0–L3 disclosure', desc: 'Project map, relevant clusters, symbol detail, then search.' },
            { name: 'Hard context budget', desc: 'Set a per-query token budget; NeuralMind trims L3 → L2 → L1 to fit it.' },
            { name: 'Read dedup', desc: 'In Claude Code, a repeat read of an unchanged file comes back as a short stub; the next read is full again.' },
            { name: 'Local retrieval', desc: 'A local index lookup, not another model call. TurboVec keeps 4-bit vectors 8–16× smaller than float32, parity gated in CI.' },
        ],
        link: { href: '/benchmark/', label: 'The benchmark, misses included' },
    },
    {
        icon: 'restore',
        title: 'Stays current, and remembers',
        lede: 'An index that keeps up with git and says when it hasn’t, plus memory that survives the session.',
        items: [
            { name: 'Fresh after every git move', desc: '`neuralmind init-hook .` installs post-commit, post-merge, post-checkout and post-rewrite hooks, so commits, pulls, branch switches and rebases rebuild in the background.', since: '4.13.0' },
            { name: 'Stale-index warnings', desc: 'When commits since the last build changed the project, or the background rebuild failed, query, search, the MCP tools and the prompt hook say so in one line.', since: '4.17.0' },
            { name: 'Learned associations', desc: 'A Hebbian synapse layer links files you use together and re-ranks recall with those links; `neuralmind eval . --synapse-ab` measures whether that helps on your repo.' },
            { name: 'Decisions that go stale with their code', desc: 'Architecture decisions are stored with their files. A later commit or pull that changes those files marks them stale, and a hook surfaces a stale one before your agent edits under it.' },
        ],
    },
    {
        icon: 'shield-check',
        title: 'Local, and verifiable',
        lede: 'By default no telemetry and no repository content off your machine, with the evidence a security review asks for.',
        items: [
            { name: 'Signed, attested releases', desc: 'cosign-signed images, build-provenance attestations, a CycloneDX SBOM per release and an OpenVEX statement.', since: '4.14.0' },
            { name: 'Secret scan', desc: '`neuralmind scan-for-secrets .` reports credentials before they reach the index, a commit or an agent’s context.' },
            { name: 'CUI profile', desc: '`security.profile: cui` turns on the CUI-enclave posture as one setting and refuses what would weaken it.', since: '4.16.0' },
            { name: 'Data locations', desc: '`neuralmind data-locations .` lists every place NeuralMind keeps data for a project, and how to remove each.', since: '4.18.0' },
            { name: 'SP 800-53 hardening check', desc: '`neuralmind hardening` checks a project and its host against 17 rules mapped to SP 800-53 controls; audit records forward to syslog as they are written.', since: '4.19.0' },
        ],
        link: { href: '/security', label: 'Security and verification' },
    },
    {
        icon: 'hub',
        title: 'Works with your agent',
        lede: 'No new IDE, no model swap, no hosted service. Claude Code is tested end to end; other MCP clients connect through the same protocol.',
        items: [
            { name: 'MCP server', desc: '`neuralmind install-mcp` registers it with Claude Code, or Cursor, Cline, VS Code and Claude Desktop via `--client`; any other client points at `neuralmind-mcp`.' },
            { name: 'Claude Code hooks', desc: 'Memory at session start, related files at each prompt, and a guard that surfaces a stale decision before an edit.' },
            { name: 'Hermes plugin', desc: '`neuralmind install-hermes-plugin` runs the same hook actions inside Hermes-Agent.' },
            { name: 'Ten languages', desc: 'Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby and PHP, plus JavaScript, OpenAPI, SQL DDL and Protocol Buffers.' },
        ],
    },
];

export default async function Features() {
    const latest = (await getLatestRelease()).tag;
    const badge = (since?: string) => {
        if (!since) return null;
        const out = tagAtLeast(latest, since);
        return (
            <span className="ml-2 align-middle font-mono text-xs text-faint whitespace-nowrap">
                v{since}
                {out ? '+' : ', next release'}
            </span>
        );
    };

    return (
        <section id="features" className="relative py-20 md:py-28 px-4 md:px-6">
            <div className="max-w-6xl mx-auto">
                <SectionHeader title="What your agent gets">
                    Four things, in one local install. Every feature runs free at one seat.
                </SectionHeader>

                <div className="grid md:grid-cols-2 bg-carbon-card border-t border-l border-carbon-border">
                    {pillars.map((p, i) => (
                        <div key={p.title} className="border-b border-r border-carbon-border p-6 md:p-8 flex flex-col">
                            <div className="flex items-center justify-between mb-5">
                                <Icon name={p.icon} className="w-6 h-6 text-muted" />
                                <span className="font-mono text-xs text-faint tabular-nums">
                                    {String(i + 1).padStart(2, '0')} / {String(pillars.length).padStart(2, '0')}
                                </span>
                            </div>
                            <h3 className="font-display text-2xl font-semibold text-white tracking-tight mb-2">{p.title}</h3>
                            <p className="text-muted text-body-sm leading-relaxed mb-6">{p.lede}</p>
                            <dl className="space-y-4 mb-2">
                                {p.items.map((item) => (
                                    <div key={item.name}>
                                        <dt className="text-ink text-sm font-semibold">
                                            {item.name}
                                            {badge(item.since)}
                                        </dt>
                                        <dd className="text-muted text-sm leading-relaxed mt-0.5">{withCode(item.desc)}</dd>
                                    </div>
                                ))}
                            </dl>
                            {p.link && (
                                <a href={p.link.href} className="mt-auto pt-4 link text-sm font-medium">
                                    {p.link.label}
                                </a>
                            )}
                        </div>
                    ))}
                </div>

                <figure className="mt-10">
                    <div className="rounded-card border border-carbon-border overflow-hidden bg-carbon-raised">
                        {/* eslint-disable-next-line @next/next/no-img-element -- static export, no image optimizer */}
                        <img
                            src="/graph-view.webp"
                            width={1600}
                            height={561}
                            loading="lazy"
                            alt="NeuralMind's graph view of the psf/requests index: the sidebar's toggles for learned synapses and structural edges, beside a force-directed graph of the repo's nodes coloured by cluster."
                            className="w-full h-auto block"
                        />
                    </div>
                    <figcaption className="mt-3 text-faint text-caption">
                        {withCode('`neuralmind serve`: the psf/requests index with structural edges and learned synapses overlaid. Local, read-only, behind a per-session token.')}
                    </figcaption>
                </figure>
            </div>
        </section>
    );
}
