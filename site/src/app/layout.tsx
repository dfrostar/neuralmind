import './globals.css';
import { getLatestRelease } from '@/lib/release';

export const metadata = {
    title: 'NeuralMind — Code Memory for AI Coding Agents | 93.75% Gold-File Recall',
    description:
        'Memory for AI coding agents that opens the right file first: 93.75% gold-file recall across 40 pre-registered queries on four public repos, at 45–257× fewer tokens than pasting them in. Local-first, no telemetry.',
    keywords: [
        'AI coding agent memory',
        'gold-file recall',
        'local code retrieval',
        'token reduction',
        'semantic code search',
        'context compression',
        'MCP server',
        'Claude Code memory',
        'Cursor',
        'Cline',
        'local-first',
        'TurboVec',
        'code intelligence',
        'team dashboard',
        'auto-documenting code',
    ],
    authors: [{ name: 'Darren Frost' }],
    creator: 'Darren Frost',
    publisher: 'Darren Frost',
    metadataBase: new URL('https://neuralmind.uk'),
    alternates: {
        canonical: '/',
    },
    openGraph: {
        title: 'NeuralMind — Code Memory for AI Coding Agents',
        description:
            '93.75% gold-file recall across 40 pre-registered queries on four public repos, at 45–257× fewer tokens. Local-first, no telemetry, honest benchmarks — every miss published.',
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
        title: 'NeuralMind — Code Memory for AI Coding Agents',
        description:
            '93.75% gold-file recall across 40 pre-registered queries on four public repos, at 45–257× fewer tokens. Local-first, no telemetry.',
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

// softwareVersion/dateModified are resolved from the latest GitHub release at
// build time — never hardcode a version here (it drifts out of sync with the
// actual release, which is exactly the bug a pinned v0.42.0 once caused).
const buildJsonLd = (softwareVersion: string, dateModified: string) => ({
    '@context': 'https://schema.org',
    '@graph': [
        {
            '@type': 'SoftwareApplication',
            '@id': 'https://neuralmind.uk/#software',
            name: 'NeuralMind',
            applicationCategory: 'DeveloperApplication',
            applicationSubCategory: 'AI coding agent memory & code intelligence',
            operatingSystem: 'Linux, macOS, Windows',
            description:
                'Persistent memory and semantic code intelligence for AI coding agents. Local-first code indexing with 12–50× per-query token reduction, a brain-like synapse layer that learns associations from how you use the codebase, an Obsidian-style graph view, an MCP server, and a built-in install doctor.',
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
                'AI coding agent memory, code intelligence, token reduction, RAG, MCP server, knowledge graph, Hebbian synapses, progressive context disclosure',
            featureList: [
                'ChromaDB-free TurboVec retrieval: 4-bit quantized index, 8–16× smaller vectors, parity gated in CI',
                '45–257× fewer tokens than full-file context across 40 pre-registered queries on four public repos',
                'Read-only team dashboard with synapse memory, ingestion, and latency trends',
                'DocEvolver: evolutionary JSDoc optimization for undocumented methods',
                'Brain-like Hebbian synapse layer that learns associations from how you use the codebase',
                'Bundled tree-sitter code graph indexing ten languages',
                'MCP server for Claude Code, Cursor, Cline, Continue, and any MCP-compatible agent',
                '100% local engine — zero network calls of its own, no telemetry',
            ],
            offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
            author: { '@type': 'Person', name: 'Darren Frost' },
            publisher: { '@type': 'Person', name: 'Darren Frost' },
            sameAs: ['https://github.com/dfrostar/neuralmind', 'https://pypi.org/project/neuralmind/'],
        },
        {
            '@type': 'WebSite',
            '@id': 'https://neuralmind.uk/#website',
            name: 'NeuralMind',
            url: 'https://neuralmind.uk',
            about: { '@id': 'https://neuralmind.uk/#software' },
            inLanguage: 'en',
        },
    ],
});

export default async function RootLayout({ children }: { children: React.ReactNode }) {
    const rel = await getLatestRelease();
    const jsonLd = buildJsonLd(rel.tag.replace(/^v/, ''), rel.date);
    return (
        <html lang="en">
            <head>
                <link rel="icon" href="/favicon.ico" sizes="any" />
                <link rel="icon" href="/icon.svg" type="image/svg+xml" />
                <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
                <link rel="manifest" href="/site.webmanifest" />
                <meta name="theme-color" content="#0c0c0c" />
                {!process.env.NODE_ENV || process.env.NODE_ENV === 'production' ? (
                    <script defer src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "97b18db165e64f6e8d1d75b5e4e16447"}'></script>
                ) : null}
                <script
                    type="application/ld+json"
                    dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
                />
            </head>
            <body className="bg-carbon text-slate-200 antialiased">{children}</body>
        </html>
    );
}
