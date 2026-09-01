'use client';

import SectionHeader from '@/components/ui/SectionHeader';

const assessmentIncludes = [
    'A measured token-reduction ratio on one of your own repos — run locally, with none of your code transmitted',
    'A spend model in your numbers: per-seat subscriptions, usage-based API (OpenRouter, Bedrock, Vertex), and self-hosted GPU',
    'A productivity model: hours lost to context-limit thrashing and re-prompting, valued at your fully-loaded rate',
    'An honest fit verdict — if your workload is generation-heavy or caching already covers you, we say so',
];

export default function Assessment() {
    return (
        <section id="assessment" className="relative py-16 md:py-32 px-4 md:px-6">

            <div className="max-w-3xl mx-auto">
                <SectionHeader eyebrow="Free assessment" title="See your savings before you spend a dollar">
                    NeuralMind is open source and free (MIT) — <code className="font-mono text-[0.9em] text-electric-bright bg-electric/[0.07] rounded px-1 py-0.5">pip install neuralmind</code> and
                    you have the whole product. For teams evaluating at scale, we run a free
                    AI-spend assessment: measured on your code, modeled in your numbers, no obligation.
                </SectionHeader>

                <div className="rounded-xl p-6 md:p-8 panel-accent">
                    <h3 className="font-display text-xl font-semibold tracking-tight text-white mb-6">What the assessment gives you</h3>
                    <ul className="space-y-3 mb-8">
                        {assessmentIncludes.map((item) => (
                            <li key={item} className="flex items-start gap-3 text-sm md:text-base text-slate-300">
                                <svg className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                                {item}
                            </li>
                        ))}
                    </ul>
                    <div className="flex flex-col sm:flex-row gap-4">
                        <a
                            href="mailto:hello@neuralmind.uk?subject=Free%20AI-spend%20assessment"
                            className="btn-primary text-center"
                        >
                            Request a free assessment
                        </a>
                        <a
                            href="https://pypi.org/project/neuralmind/"
                            className="btn-secondary text-center"
                        >
                            Or just install it — it's free
                        </a>
                    </div>
                </div>

                <p className="text-center text-faint text-sm mt-6">
                    The software is MIT-licensed and free. Commercial support for deployment and integration is available.
                </p>
            </div>
        </section>
    );
}
