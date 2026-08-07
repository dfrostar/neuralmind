import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';

export const metadata = {
    title: 'Research & Publications — NeuralMind',
    description: 'Research reports and defensive publications from the NeuralMind project. Deep-dive technical reports verified against the live codebase.',
    keywords: [
        'NeuralMind research',
        'defensive publication',
        'technical report',
        'team memory',
        'token reduction',
        'spreading activation',
        'Hebbian learning',
        'agent amnesia',
        'Claude Code',
        'MCP server',
        'local-first',
        'NeuralMind',
    ],
    authors: [{ name: 'Darren Frost' }],
    creator: 'Darren Frost',
    publisher: 'NeuralMind',
    metadataBase: new URL('https://neuralmind.uk'),
    alternates: {
        canonical: '/publications',
    },
    openGraph: {
        title: 'Research & Publications — NeuralMind',
        description: 'Research reports and defensive publications from the NeuralMind project.',
        url: 'https://neuralmind.uk/publications',
        siteName: 'NeuralMind',
        locale: 'en_US',
        type: 'website',
    },
    twitter: {
        card: 'summary_large_image',
        title: 'Research & Publications — NeuralMind',
        description: 'Research reports and defensive publications from the NeuralMind project.',
        images: ['https://neuralmind.uk/social-preview.png'],
    },
    robots: {
        index: true,
        follow: true,
        googleBot: { index: true, follow: true },
    },
};

const publications = [
    {
        slug: 'budget-neutral-synaptic-recall',
        title: 'Budget-Neutral Synaptic Recall: Displacement Injection with Learned Per-Edge Decay',
        type: 'Defensive Publication',
        date: 'August 7, 2026',
        description: 'Companion to the synapse learning loop publication, covering the retrieval side: recalled associations enter the agent’s context by boosting present hits and displacing the weakest vector hits one-for-one, so the token budget never grows — with per-edge forgetting rates learned from reinforcement history.',
    },
    {
        slug: 'synapse-learning-loop',
        title: 'Hebbian Co-Activation with Long-Term Potentiation and Hub-Normalized Spreading Activation',
        type: 'Defensive Publication',
        date: 'August 6, 2026',
        description: 'The NeuralMind synapse learning loop: debounced file-edit co-activation strengthens weighted edges, wall-clock half-life decay forgets, long-term potentiation preserves habitual associations, and hub-normalized spreading activation recalls. Local-first, telemetry-free.',
    },
    {
        slug: 'claude-teams-deep-dive',
        title: 'NeuralMind + Claude Teams: Procedures, Token Measurement, and Amnesia Prevention',
        type: 'Research Report',
        date: 'July 26, 2026',
        description: 'Deep-dive research report: how to use NeuralMind with Claude Code teams, measure token reduction, and eliminate agent amnesia via committed team memory bundles. Verified against the live codebase. DeepSeek v4 Pro QA-corrected.',
    },
    {
        slug: 'quality-weighted-merge',
        title: 'Quality-Weighted Merge with Conflict-Driven Decay',
        type: 'Defensive Publication',
        date: 'July 22, 2026',
        description: 'A method for resolving conflicting assertions in a distributed edge-weight graph. Each edge carries a quality score from reinforcement, recency, and conflict rate. The loser is excluded, forcing consensus.',
    },
];

export default function PublicationsIndex() {
    return (
        <>
            <Navbar />
            <main className="max-w-4xl mx-auto px-4 md:px-6 py-16">
                <header className="mb-12 pb-8 border-b border-carbon-border">
                    <h1 className="font-display text-3xl md:text-4xl font-bold text-white mb-4">
                        Research & Publications
                    </h1>
                    <p className="text-lg text-slate-300">
                        Research reports and defensive publications from the NeuralMind project. All reports are verified against the live codebase.
                    </p>
                </header>

                <div className="space-y-6">
                    {publications.map((pub) => (
                        <a
                            key={pub.slug}
                            href={`/publications/${pub.slug}`}
                            className="block bg-carbon-card border border-carbon-border rounded-xl p-6 hover:border-electric/50 transition-colors group"
                        >
                            <div className="flex items-center gap-3 mb-3">
                                <span className="px-3 py-1 rounded-lg bg-electric/10 text-electric text-xs font-mono">{pub.type}</span>
                                <span className="text-slate-500 text-sm">{pub.date}</span>
                            </div>
                            <h2 className="font-display text-xl font-bold text-white mb-2 group-hover:text-electric transition-colors">
                                {pub.title}
                            </h2>
                            <p className="text-slate-400 text-sm leading-relaxed">
                                {pub.description}
                            </p>
                        </a>
                    ))}
                </div>
            </main>
            <Footer />
        </>
    );
}
