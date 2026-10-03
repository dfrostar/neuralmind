import './globals.css';
import { getLatestRelease } from '@/lib/release';
import { fontVariables } from '@/lib/fonts';

const SITE_DESCRIPTION =
    'Codebase memory for Claude Code, Cursor and any MCP agent: 95% mean gold-file recall at 46–263× fewer tokens than pasting every source file. Free, MIT core.';

export const metadata = {
    title: 'NeuralMind — Codebase Memory for Claude Code & MCP Agents',
    description: SITE_DESCRIPTION,
    keywords: [
        'Claude Code memory',
        'AI coding agent memory',
        'codebase memory',
        'persistent memory for AI agents',
        'MCP server',
        'MCP memory server',
        'reduce Claude Code token usage',
        'context engineering',
        'token reduction',
        'semantic code search',
        'code knowledge graph',
        'Cursor',
        'Codex',
        'Cline',
        'team memory for AI agents',
        'local-first',
    ],
    authors: [{ name: 'Darren Frost', url: 'https://github.com/dfrostar' }],
    creator: 'Darren Frost',
    publisher: 'NeuralMind',
    metadataBase: new URL('https://neuralmind.uk'),
    alternates: {
        canonical: '/',
    },
    openGraph: {
        title: 'NeuralMind — Your coding agent forgets your codebase. NeuralMind remembers it.',
        description:
            '95% mean gold-file recall at 46–263× fewer tokens than pasting every source file, on a public 40-query benchmark with every miss published. Local-first, no telemetry, MIT core.',
        url: 'https://neuralmind.uk',
        siteName: 'NeuralMind',
        locale: 'en_US',
        type: 'website',
        images: [
            {
                url: '/social-preview.png',
                width: 1200,
                height: 630,
                alt: 'NeuralMind — Code Memory for AI Coding Agents',
            },
        ],
    },
    twitter: {
        card: 'summary_large_image',
        title: 'NeuralMind — Codebase Memory for Claude Code & MCP Agents',
        description: SITE_DESCRIPTION,
        images: ['https://neuralmind.uk/social-preview.png'],
    },
    robots: {
        index: true,
        follow: true,
        googleBot: { index: true, follow: true },
    },
    verification: {
        google: 'google4af0b44a17447d3e',
    },
};

const ORG_ID = 'https://neuralmind.uk/#organization';

// softwareVersion/dateModified are resolved from the latest GitHub release at
// build time — never hardcode a version here (it drifts out of sync with the
// actual release, which is exactly the bug a pinned v0.42.0 once caused).
// Entity and prices mirror commercial-terms.json; change that file first.
const buildJsonLd = (softwareVersion: string, dateModified: string) => ({
    '@context': 'https://schema.org',
    '@graph': [
        {
            '@type': 'Organization',
            '@id': ORG_ID,
            name: 'NeuralMind',
            legalName: 'Cheval-Volant LLC',
            url: 'https://neuralmind.uk',
            logo: 'https://neuralmind.uk/apple-touch-icon.png',
            email: 'hello@neuralmind.uk',
            founder: { '@type': 'Person', name: 'Darren Frost', url: 'https://github.com/dfrostar' },
            sameAs: ['https://github.com/dfrostar/neuralmind', 'https://pypi.org/project/neuralmind/'],
        },
        {
            '@type': 'SoftwareApplication',
            '@id': 'https://neuralmind.uk/#software',
            name: 'NeuralMind',
            applicationCategory: 'DeveloperApplication',
            applicationSubCategory: 'AI coding agent memory & code intelligence',
            operatingSystem: 'Linux, macOS, Windows',
            description:
                'Local-first persistent memory for AI coding agents. NeuralMind indexes a codebase into a code graph, learns which files belong together from how you work (a Hebbian synapse layer), and serves compact, ranked context to Claude Code, Codex, Cursor, Cline, Continue or any MCP client — 95% mean gold-file recall at 46–263× fewer tokens than pasting every source file on a public 40-query benchmark.',
            url: 'https://neuralmind.uk',
            downloadUrl: 'https://pypi.org/project/neuralmind/',
            installUrl: 'https://pypi.org/project/neuralmind/',
            softwareVersion,
            datePublished: '2025-05-01',
            dateModified,
            license: 'https://opensource.org/licenses/MIT',
            isAccessibleForFree: true,
            programmingLanguage: 'Python',
            operatingSystemRequirements: 'Python 3.10+',
            codeRepository: 'https://github.com/dfrostar/neuralmind',
            keywords:
                'AI coding agent memory, Claude Code memory, MCP server, codebase memory, context engineering, token reduction, code knowledge graph, Hebbian synapses, progressive context disclosure',
            featureList: [
                '46–263× fewer tokens than pasting every source file, at 95% mean gold-file recall, across 40 pre-registered queries on four public repos',
                'Hebbian synapse layer that learns which files go together from how you use the codebase — budget-neutral recall',
                'Progressive L0–L3 context disclosure with a hard per-query token budget',
                'MCP server for Claude Code, Codex, Cursor, Cline, Continue and any MCP-compatible agent',
                'Claude Code lifecycle hooks: session-start memory, tool-output compression and recovery',
                'Team memory that travels with git clone, with a quality review queue for imports and a hash-chained audit log',
                'Bundled tree-sitter code graph indexing ten languages',
                'ChromaDB-free TurboVec retrieval: 4-bit quantized index, 8–16× smaller vectors, parity gated in CI',
                'Commit-time drift guard, decision memory and stale-decision guard',
                'Local engine — by default no telemetry and no repository content transmitted off your machine',
            ],
            offers: [
                { '@type': 'Offer', name: 'Free', price: '0', priceCurrency: 'USD' },
                {
                    '@type': 'Offer',
                    name: 'Team',
                    price: '29',
                    priceCurrency: 'USD',
                    priceSpecification: {
                        '@type': 'UnitPriceSpecification',
                        price: '29',
                        priceCurrency: 'USD',
                        unitText: 'per user per month, billed annually',
                    },
                    eligibleQuantity: { '@type': 'QuantitativeValue', minValue: 5, maxValue: 50, unitText: 'seats' },
                    url: 'https://neuralmind.uk/pricing/',
                },
            ],
            author: { '@type': 'Person', name: 'Darren Frost', url: 'https://github.com/dfrostar' },
            publisher: { '@id': ORG_ID },
            sameAs: ['https://github.com/dfrostar/neuralmind', 'https://pypi.org/project/neuralmind/'],
        },
        {
            '@type': 'WebSite',
            '@id': 'https://neuralmind.uk/#website',
            name: 'NeuralMind',
            url: 'https://neuralmind.uk',
            about: { '@id': 'https://neuralmind.uk/#software' },
            publisher: { '@id': ORG_ID },
            inLanguage: 'en',
        },
    ],
});

export default async function RootLayout({ children }: { children: React.ReactNode }) {
    const rel = await getLatestRelease();
    const jsonLd = buildJsonLd(rel.tag.replace(/^v/, ''), rel.date);
    return (
        <html lang="en" className={fontVariables}>
            <head>
                <link rel="icon" href="/favicon.ico" sizes="any" />
                <link rel="icon" href="/icon.svg" type="image/svg+xml" />
                <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
                <link rel="manifest" href="/site.webmanifest" />
                <meta name="theme-color" content="#0a0b0d" />
                {!process.env.NODE_ENV || process.env.NODE_ENV === 'production' ? (
                    <script defer src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "97b18db165e64f6e8d1d75b5e4e16447"}'></script>
                ) : null}
                <script
                    type="application/ld+json"
                    dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
                />
            </head>
            <body className="bg-carbon text-slate-200 font-sans antialiased">{children}</body>
        </html>
    );
}
