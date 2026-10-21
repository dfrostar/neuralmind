import Link from 'next/link';
import type { Metadata } from 'next';
import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';

// Without this file the export's 404 carried Next's own noindex beside the
// root layout's `index, follow`, and two <title>s. Declaring the metadata here
// gives it exactly one of each. Not a `page.tsx`, so it never enters the sitemap.
export const metadata: Metadata = {
    title: 'Page not found — NeuralMind',
    // Its own, so the 404 doesn't repeat the homepage's description.
    description: 'This page is not on neuralmind.uk. NeuralMind’s docs moved to docs.neuralmind.uk; the homepage links the benchmark, pricing and research.',
    robots: { index: false, follow: true },
};

export default function NotFound() {
    return (
        <>
            <Navbar />
            <main className="pt-32 pb-20 px-4 md:px-6">
                <article className="max-w-3xl mx-auto">
                    <span className="eyebrow block mb-4">404</span>
                    <h1 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
                        Page not found
                    </h1>
                    <p className="text-muted text-lg mb-10">
                        That page doesn&apos;t exist, or it moved. The docs now live at{' '}
                        <a
                            href="https://docs.neuralmind.uk/"
                            className="text-electric hover:text-electric-bright transition-colors"
                        >
                            docs.neuralmind.uk
                        </a>
                        .
                    </p>
                    <Link
                        href="/"
                        className="text-electric hover:text-electric-bright transition-colors"
                    >
                        ← Back to the homepage
                    </Link>
                </article>
            </main>
            <Footer />
        </>
    );
}
