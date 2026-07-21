import './globals.css';
import { Inter, JetBrains_Mono, Fraunces } from 'next/font/google';
import { getLatestRelease, type LatestRelease } from '@/lib/release';

const inter = Inter({
    subsets: ['latin'],
    variable: '--font-inter',
    display: 'swap',
});

const jetbrains = JetBrains_Mono({
    subsets: ['latin'],
    variable: '--font-mono',
    display: 'swap',
});

const fraunces = Fraunces({
    subsets: ['latin'],
    weight: ['400', '500', '600', '700', '800', '900'],
    variable: '--font-display',
    display: 'swap',
});

export const metadata = {
    title: 'NeuralMind — Persistent Memory for AI Coding Agents | 40–70× Token Reduction',
    description:
        'Persistent, 100% local memory for AI coding agents. NeuralMind learns your codebase like a senior engineer and cuts token costs 40–70×. Works with Claude Code, Cursor, Cline, and any MCP agent.',
    keywords: [
        'AI coding agent memory',
        'persistent agent memory',
        'semantic code search',
        'token reduction',
        'context compression',
        'MCP server',
        'Claude Code memory',
        'Cursor',
        'Cline',
        'tree-sitter code graph',
        'Hebbian learning',
        'synapse layer',
        'local-first',
        'hybrid search',
        'BM25',
        'code retrieval benchmark',
        'team memory',
        'progressive context disclosure',
        'tool output compression',
    ],
    authors: [{ name: 'Darren Frost' }],
    creator: 'Darren Frost',
    publisher: 'Darren Frost',
    metadataBase: new URL('https://neuralmind.uk'),
    alternates: {
        canonical: '/',
    },
    openGraph: {
        title: 'NeuralMind — Persistent Memory for AI Coding Agents',
        description:
            'Your agent learns your codebase the way a senior engineer would — and remembers it across sessions. 100% local engine, no telemetry, no cloud calls. Side effect: 40–70× cheaper code questions, measured in CI on every commit.',
        url: 'https://neuralmind.uk',
        siteName: 'NeuralMind',
        locale: 'en_US',
        type: 'website',
        images: [
            {
                url: '/social-preview.png',
                width: 1200,
                height: 630,
                alt: 'NeuralMind — Persistent Memory for AI Coding Agents',
            },
        ],
    },
    twitter: {
        card: 'summary_large_image',
        title: 'NeuralMind — Persistent Memory for AI Coding Agents',
        description:
            'Your agent learns your codebase the way a senior engineer would — and remembers it across sessions. 100% local. 40–70× token reduction, measured in CI.',
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

// Version and modification date come from the latest GitHub release at build
// time — never hardcoded, so they can't drift out of sync with what shipped.
const jsonLdFor = (rel: LatestRelease) => ({
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
                'Persistent memory and semantic code intelligence for AI coding agents. Local-first code indexing with 40–70× per-query token reduction, a brain-like synapse layer that learns associations from how you use the codebase, an Obsidian-style graph view, an MCP server, and a built-in install doctor.',
            url: 'https://neuralmind.uk',
            downloadUrl: 'https://pypi.org/project/neuralmind/',
            installUrl: 'https://pypi.org/project/neuralmind/',
            softwareVersion: rel.version,
            datePublished: '2025-05-01',
            dateModified: rel.date,
            license: 'https://opensource.org/licenses/MIT',
            isAccessibleForFree: true,
            programmingLanguage: 'Python',
            operatingSystemRequirements: 'Python 3.10+',
            codeRepository: 'https://github.com/dfrostar/neuralmind',
            keywords:
                'AI coding agent memory, code intelligence, token reduction, RAG, MCP server, knowledge graph, Hebbian synapses, progressive context disclosure',
            featureList: [
                'Progressive L0–L3 context disclosure for 40–70× per-query token reduction',
                'Brain-like Hebbian synapse layer that learns associations from how you use the codebase',
                'Bundled tree-sitter code graph indexing ten languages',
                'Honest public benchmark: 100% gold-file recall at 38–85× fewer tokens',
                'MCP server for Claude Code, Cursor, Cline, Continue, and any MCP-compatible agent',
                'Obsidian-style local graph view and a recovery cache for dropped tool output',
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
    const jsonLd = jsonLdFor(await getLatestRelease());
    return (
        <html lang="en" className={`${inter.variable} ${jetbrains.variable} ${fraunces.variable}`}>
            <head>
                <link rel="preconnect" href="https://fonts.googleapis.com" />
                <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
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
