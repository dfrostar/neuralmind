'use client';

export default function CTA() {
    return (
        <section id="install" className="relative py-16 md:py-32 px-4 md:px-6">
            <div className="absolute inset-0 -z-10">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-electric/5 rounded-full blur-[200px]" />
            </div>

            <div className="max-w-3xl mx-auto text-center">
                <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-6">
                    Stop paying for tokens you don't use.
                </h2>
                <p className="text-slate-400 text-base sm:text-lg md:text-xl mb-10 max-w-xl mx-auto">
                    One command to install. Seconds to verify. Your agent remembers what matters.
                </p>

                <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-10">
                    <code className="text-base font-mono bg-carbon-raised border border-carbon-border px-6 py-3 rounded-xl text-white shadow-lg">
                        pip install neuralmind
                    </code>
                    <a
                        href="https://pypi.org/project/neuralmind/"
                        className="btn-primary"
                    >
                        Get started
                    </a>
                </div>

                <div className="flex items-center justify-center gap-6 text-sm text-slate-500">
                    <span className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-emerald-400" />
                        No cloud calls
                    </span>
                    <span className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-amber-400" />
                        CI-verified
                    </span>
                    <span className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-blue-400" />
                        100% local
                    </span>
                </div>
            </div>
        </section>
    );
}
