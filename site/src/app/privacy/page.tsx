import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';

export const metadata = {
    title: 'Privacy Policy — NeuralMind',
    description: 'Privacy policy for NeuralMind. The engine runs 100% locally with no telemetry — this policy explains the little that\'s left.',
};

type Section = {
    title: string;
    body: string | string[];
    list?: string[];
};

const sections: Section[] = [
    {
        title: 'Overview',
        body: 'NeuralMind is built on a simple principle: your code stays on your machine. We designed the product to function 100% locally, with zero cloud calls for any code processing. This policy explains what data we collect (very little), why, and your rights. The full, canonical GDPR policy is maintained in the open at github.com/dfrostar/neuralmind/blob/main/docs/PRIVACY-POLICY.md.',
    },
    {
        title: 'Data We Do Not Collect',
        body: 'We do not collect, transmit, or store your source code, queries, file paths, graph data, synapse weights, or any file contents. The index lives entirely in your project\'s `.neuralmind/` and `graphify-out/` directories on your machine. The NeuralMind software has no telemetry of any kind — not opt-in, not anonymous, none. It makes one kind of outbound request of its own, and only this: the first time it needs to embed on a machine with no cached model, it downloads a public embedding model (all-MiniLM-L6-v2) over HTTPS, verified against a pinned checksum. That fetch retries on transient network errors and runs again if the cached model is later removed, so it is not a once-in-a-lifetime event — but it is always the same public file, and it never carries your data. That request carries none of your data — it is a plain file download — and pre-seeding the model via NEURALMIND_ONNX_MODEL_DIR removes it entirely. Beyond that, the only network traffic in your workflow is what your AI agent sends to its own model provider, which NeuralMind minimizes but does not control. Payment card data never touches our systems — it is handled entirely by Stripe.',
    },
    {
        title: 'Data We Collect',
        body: [
            'From the open-source software: nothing. There is no telemetry mechanism in the product.',
            'Team tier license data: your email address (and optional company name) when you purchase a license, the seat email addresses you add, and license metadata (tier, seats, expiry, signature hash).',
            'Payment: a Stripe customer ID for reconciliation. Card data is handled entirely by Stripe (PCI-DSS Level 1) and never touches our systems.',
            'License portal: IP address and user agent are recorded in audit logs when you use the license portal, for security monitoring and fraud prevention.',
            'PyPI download counts (public registry data, collected by PyPI, not by us)',
            'Website visitor analytics on neuralmind.uk (see Cloudflare section below)',
        ],
    },
    {
        title: 'Data Retention',
        body: 'We keep Team-tier data only as long as the law and license validation require:',
        list: [
            'Active license data: duration of the license + 3 years after expiry',
            'Audit logs (with IP): 3 years after creation, then anonymized',
            'Financial records (Stripe): 7 years, required for tax compliance',
            'Deleted customer records: personal data anonymized immediately; financial records retained per above',
        ],
    },
    {
        title: 'GDPR & Your Rights',
        body: 'Because we have minimal data collection, exercising your rights is simple:',
        list: [
            'Right to access: for the open-source tool we hold no personal data about you at all; Team-tier customers can request a copy of their license and audit data at hello@neuralmind.uk',
            'Right to deletion: your index is local files you control — delete your project\'s `.neuralmind/` directory (or run `neuralmind reset`) and it is gone completely. Team-tier customers: email hello@neuralmind.uk and personal data is deleted (financial records are anonymized per the retention policy above)',
            'Right to portability: your local data is already in open formats (SQLite and JSON) inside your project directory',
            'EU Representative: Darren Frost, Cheval-Volant LLC, Texas, USA',
        ],
    },
    {
        title: 'Cloudflare Web Analytics',
        body: 'Our website uses Cloudflare Web Analytics, which is privacy-first and does not set cookies or collect personal identifiers. No individual visitors are tracked. Data is aggregated and retained for 30 days. No data is sold or shared with third parties.',
    },
    {
        title: 'Cookies & Tracking',
        body: 'NeuralMind does not use cookies on neuralmind.uk. The Team license portal uses a single strictly-necessary session cookie for authentication — nothing else. We have no advertising pixels, no cross-site trackers, and no fingerprinting anywhere.',
    },
    {
        title: 'Third-Party Services',
        body: [
            'GitHub: for source code hosting and releases. GitHub\'s privacy policy applies.',
            'PyPI: for package distribution. Python Software Foundation privacy policy applies.',
            'Cloudflare: for domain, DNS, and Pages hosting. Cloudflare\'s privacy policy applies.',
            'Stripe: payment processing for Team licenses. Card data goes directly to Stripe; Stripe\'s privacy policy applies.',
        ],
    },
    {
        title: 'Changes to This Policy',
        body: 'We may update this policy as the product evolves. Material changes will be announced on the GitHub repository and linked from this page. Last updated: July 20, 2026.',
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
                    <p className="text-slate-400 text-lg mb-12">Last updated: July 20, 2026</p>
                    {sections.map((s) => (
                        <div key={s.title} className="mb-10">
                            <h2 className="font-display text-2xl font-bold text-white mb-3 border-l-4 border-electric pl-4">{s.title}</h2>
                            {Array.isArray(s.body) ? (
                                <ul className="space-y-2 text-slate-300">
                                    {s.body.map((item) => (
                                        <li key={item} className="flex items-start gap-2">
                                            <span className="text-emerald-400 mt-1.5">•</span>
                                            <span>{item}</span>
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="text-slate-300 leading-relaxed">{s.body}</p>
                            )}
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
