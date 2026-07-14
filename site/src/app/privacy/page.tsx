import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';

export const metadata = {
    title: 'Privacy Policy — NeuralMind',
    description: 'Privacy policy for NeuralMind. The engine runs 100% locally with no telemetry — this policy explains the little that\'s left.',
};

const sections = [
    {
        title: 'Overview',
        body: 'NeuralMind is built on a simple principle: your code stays on your machine. We designed the product to function 100% locally, with zero cloud calls for any code processing. This policy explains what data we collect (very little), why, and your rights.',
    },
    {
        title: 'Data We Do Not Collect',
        body: 'We do not collect, transmit, or store your source code, queries, file paths, graph data, synapse weights, or any file contents. The index lives entirely in your project\'s `.neuralmind/` and `graphify-out/` directories on your machine. The NeuralMind software has no telemetry of any kind — not opt-in, not anonymous, none. It makes zero network calls of its own; the only network traffic in your workflow is what your AI agent sends to its own model provider, which NeuralMind minimizes but does not control.',
    },
    {
        title: 'Data We Collect',
        body: [
            'From the software: nothing. There is no telemetry mechanism in the product.',
            'PyPI download counts (public registry data, collected by PyPI, not by us)',
            'Website visitor analytics on neuralmind.uk (see Cloudflare section below)',
        ],
    },
    {
        title: 'GDPR & Your Rights',
        body: 'Because we have minimal data collection, exercising your rights is simple:',
        list: [
            'Right to access: we hold no personal data about you to access; for website analytics questions email hello@neuralmind.uk',
            'Right to deletion: your index is local files you control — delete your project\'s `.neuralmind/` directory (or run `neuralmind reset`) and it is gone completely',
            'Right to portability: your local data is already in open formats (SQLite and JSON) inside your project directory',
            'EU Representative: Darren Frost, Cheval-Volant LLC, Delaware, USA',
        ],
    },
    {
        title: 'Cloudflare Web Analytics',
        body: 'Our website uses Cloudflare Web Analytics, which is privacy-first and does not set cookies or collect personal identifiers. No individual visitors are tracked. Data is aggregated and retained for 30 days. No data is sold or shared with third parties.',
    },
    {
        title: 'Cookies & Tracking',
        body: 'NeuralMind does not use cookies on neuralmind.uk or any of its services. We have no advertising pixels, no cross-site trackers, and no fingerprinting.',
    },
    {
        title: 'Third-Party Services',
        body: [
            'GitHub: for source code hosting and releases. GitHub\'s privacy policy applies.',
            'PyPI: for package distribution. Python Software Foundation privacy policy applies.',
            'Cloudflare: for domain, DNS, and Pages hosting. Cloudflare\'s privacy policy applies.',
        ],
    },
    {
        title: 'Changes to This Policy',
        body: 'We may update this policy as the product evolves. Material changes will be announced on the GitHub repository and linked from this page. Last updated: July 2026.',
    },
    {
        title: 'Contact',
        body: 'Questions about privacy or legal matters: hello@neuralmind.uk',
    },
];

export default function Privacy() {
    return (
        <>
            <Navbar />
            <main className="pt-32 pb-20 px-4 md:px-6">
                <article className="max-w-3xl mx-auto">
                    <h1 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">Privacy Policy</h1>
                    <p className="text-slate-400 text-lg mb-12">Last updated: July 2026</p>
                    {sections.map((s) => (
                        <div key={s.title} className="mb-10">
                            <h2 className="font-display text-2xl font-bold text-white mb-3 border-l-4 border-electric pl-4">{s.title}</h2>
                            <p className="text-slate-300 leading-relaxed">{s.body}</p>
                            {s.list && (
                                <ul className="mt-3 space-y-2 text-slate-300">
                                    {s.list.map((item) => (
                                        <li key={item} className="flex items-start gap-2">
                                            <span className="text-emerald-400 mt-1.5">•</span>
                                            <span>{item}</span>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    ))}
                </article>
            </main>
            <Footer />
        </>
    );
}
