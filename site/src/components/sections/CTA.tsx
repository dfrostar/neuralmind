'use client';

import CommandLine from '@/components/ui/CommandLine';
import Icon from '@/components/ui/Icon';

// The three assurances were dotted in emerald, amber and blue — three colours
// carrying no distinction, and amber in particular reads as a warning next to
// the words "CI-verified". One evidence colour, one meaning.
const assurances = ['No cloud calls', 'CI-verified', '100% local'];

export default function CTA() {
    return (
        <section id="install" className="relative py-20 md:py-28 px-4 md:px-6">
            <div className="max-w-6xl mx-auto">
                <div className="panel-accent rounded-2xl px-6 py-14 md:px-14 md:py-16 text-center">
                    <h2 className="font-display text-3xl sm:text-4xl md:text-[2.75rem] font-semibold text-white tracking-tighter mb-5 max-w-2xl mx-auto">
                        Stop paying for tokens you don&apos;t use.
                    </h2>
                    <p className="text-slate-400 text-base md:text-lg mb-9 max-w-xl mx-auto leading-relaxed">
                        One command to install. Seconds to verify. Your agent remembers what matters.
                    </p>

                    <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-10">
                        <CommandLine command="pip install neuralmind" />
                        <a href="https://pypi.org/project/neuralmind/" className="btn-primary py-3">
                            Get started
                            <Icon name="arrow-right" className="w-4 h-4" />
                        </a>
                    </div>

                    <ul className="flex flex-wrap items-center justify-center gap-x-7 gap-y-2 text-sm text-faint">
                        {assurances.map((item) => (
                            <li key={item} className="flex items-center gap-2">
                                <Icon name="check" className="w-3.5 h-3.5 text-proton" strokeWidth={2.25} />
                                {item}
                            </li>
                        ))}
                    </ul>
                </div>
            </div>
        </section>
    );
}
