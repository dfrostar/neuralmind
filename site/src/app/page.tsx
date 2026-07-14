import Hero from '@/components/sections/Hero';
import HowItWorks from '@/components/sections/HowItWorks';
import Benchmarks from '@/components/sections/Benchmarks';
import Features from '@/components/sections/Features';
import Assessment from '@/components/sections/Assessment';
import FAQ from '@/components/sections/FAQ';
import CTA from '@/components/sections/CTA';
import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';

export default function Page() {
    return (
        <>
            <Navbar />
            <main>
                <Hero />
                <HowItWorks />
                <Benchmarks />
                <Features />
                <Assessment />
                <FAQ />
                <CTA />
            </main>
            <Footer />
        </>
    );
}
