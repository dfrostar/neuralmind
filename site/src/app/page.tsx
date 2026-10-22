import Hero from '@/components/sections/Hero';
import HowItWorks from '@/components/sections/HowItWorks';
import Features from '@/components/sections/Features';
import Proof from '@/components/sections/Proof';
import TeamsSecurity from '@/components/sections/TeamsSecurity';
import FAQ from '@/components/sections/FAQ';
import CTA from '@/components/sections/CTA';
import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';

// Six sections, each answering the next question a developer asks: what is
// it and does it work (Hero), how (How it works, with a quickstart), what do
// I get (Features), can I believe the numbers (Proof), will it work for my
// team and my security review (Teams & security), and what's left (FAQ,
// install). It was eleven, with three proof sections back to back.
export default function Page() {
    return (
        <>
            <Navbar />
            <main>
                <Hero />
                <HowItWorks />
                <Features />
                <Proof />
                <TeamsSecurity />
                <FAQ />
                <CTA />
            </main>
            <Footer />
        </>
    );
}
