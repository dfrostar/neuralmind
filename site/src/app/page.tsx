import Hero from '@/components/sections/Hero';
import Problem from '@/components/sections/Problem';
import HowItWorks from '@/components/sections/HowItWorks';
import Features from '@/components/sections/Features';
import Benchmarks from '@/components/sections/Benchmarks';
import ProveIt from '@/components/sections/ProveIt';
import Proof from '@/components/sections/Proof';
import BusinessCase from '@/components/sections/BusinessCase';
import Assessment from '@/components/sections/Assessment';
import FAQ from '@/components/sections/FAQ';
import CTA from '@/components/sections/CTA';
import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';

// Problem → how it works → what you get → the evidence → the business case →
// questions → install. The page used to open with three proof sections in a
// row before it had said what the product does or what it replaces.
export default function Page() {
    return (
        <>
            <Navbar />
            <main>
                <Hero />
                <Problem />
                <HowItWorks />
                <Features />
                <Benchmarks />
                <ProveIt />
                <Proof />
                <BusinessCase />
                <Assessment />
                <FAQ />
                <CTA />
            </main>
            <Footer />
        </>
    );
}
