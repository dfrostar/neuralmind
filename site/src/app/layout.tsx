import './globals.css';
import { getLatestRelease } from '@/lib/release';
import { fontVariables } from '@/lib/fonts';
import CondensingGraph from '@/components/ui/CondensingGraph';
import LiquidBackground from '@/components/ui/LiquidBackground';

const SITE_DESCRIPTION =
    'Review code you’ve never seen: a local index that hands your agent the gold file on 40 of 40 queries vs ripgrep’s 32 of 40, at 31–67× fewer tokens.';

export const metadata = {
    title: 'NeuralMind — Review Code You’ve Never Seen, with Your Agent',
    description: SITE_DESCRIPTION,
    keywords: [
        'local code index for AI coding agents',
        'code intelligence for AI agents',
        'Claude Code',
        'Hermes agent',
        'MCP server',
        'measure Claude Code token usage',
        'context engineering',
        'fewer tokens per question',
        'semantic code search',
        'code knowledge graph',
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
        title: 'NeuralMind — Review code you’ve never seen. Show the client the evidence.',
        description:
            'A local index of a client’s repository that hands your coding agent the right code first: the gold file on 40 of 40 public-benchmark queries vs keyword ripgrep’s 32 of 40 (top five files opened whole), at 31–67× fewer tokens. 93.3% top-5 on a 150-question eval, every miss published. No telemetry by default, signed releases, compliance evidence. MIT core.',
        url: 'https://neuralmind.uk',
        siteName: 'NeuralMind',
        locale: 'en_US',
        type: 'website',
        images: [
            {
                url: '/social-preview.png',
                width: 2400,
                height: 1260,
                alt: 'NeuralMind — a local code index for AI coding agents',
            },
        ],
    },
    twitter: {
        card: 'summary_large_image',
        title: 'NeuralMind — Review Code You’ve Never Seen, with Your Agent',
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
            applicationSubCategory: 'Code intelligence for AI coding agents',
            operatingSystem: 'Linux, macOS, Windows',
            description:
                'A local code index for AI coding agents. NeuralMind indexes a codebase into a code graph and assembles compact, ranked context from it, delivered to Claude Code and Hermes through a prompt hook and to any MCP client through a server — the gold file on 40 of 40 public-benchmark queries vs keyword ripgrep’s 32 of 40 (top five files opened whole), at 31–67× fewer tokens, and 51–242× fewer than pasting every source file; 93.3% top-5 on a 150-question eval, with its 10 misses published. It has not been shown to make agents finish more tasks or spend less, and every run that tested that is published.',
            url: 'https://neuralmind.uk',
            downloadUrl: 'https://pypi.org/project/neuralmind/',
            installUrl: 'https://pypi.org/project/neuralmind/',
            softwareVersion,
            datePublished: '2025-05-01',
            // Empty when neither the API nor CHANGELOG.md dates the tag: omit it
            // rather than publish another release's date.
            ...(dateModified ? { dateModified } : {}),
            license: 'https://opensource.org/licenses/MIT',
            isAccessibleForFree: true,
            programmingLanguage: 'Python',
            operatingSystemRequirements: 'Python 3.10+',
            codeRepository: 'https://github.com/dfrostar/neuralmind',
            keywords:
                'local code index, code intelligence for AI agents, Claude Code, Hermes agent, MCP server, context engineering, code knowledge graph, progressive context disclosure',
            featureList: [
                'The gold file on 40 of 40 pre-registered queries on four public repos vs keyword ripgrep’s 32 of 40 (top five files opened whole), at 31–67× fewer tokens, and 51–242× fewer than pasting every source file; 93.3% top-5 on a 150-question eval, misses published',
                'Synapse layer that records which files are used together and re-ranks recall; an exploratory Hermes run that carried that state from task to task found no statistically significant gain in tasks solved',
                'Progressive L0–L3 context disclosure with a hard per-query token budget',
                'MCP server for MCP-compatible clients; agents did not call its tools in our task-outcome runs',
                'Prompt hook for Claude Code and Hermes: session-start context and prompt-time recall; in Claude Code, a stale-decision guard before each edit',
                'Committed team bundle of recorded file associations that travels with git, with a review queue for imports and a hash-chained audit log',
                'Bundled tree-sitter code graph indexing ten languages plus JavaScript (parsed with the TypeScript grammars)',
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
                <meta name="theme-color" content="#0d1013" />
                {!process.env.NODE_ENV || process.env.NODE_ENV === 'production' ? (
                    <script defer src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "97b18db165e64f6e8d1d75b5e4e16447"}'></script>
                ) : null}
                <script
                    type="application/ld+json"
                    dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
                />
            </head>
            {/* No background on body: the liquid canvas, and the graph that
                condenses out of it, paint between the ground on <html> and
                the page. */}
            <body className="text-ink font-sans antialiased">
                <LiquidBackground />
                <CondensingGraph />
                {children}
            </body>
        </html>
    );
}
