const steps = [
    {
        step: '1',
        title: '30-second demo on a fresh clone',
        body: 'One script: isolated venv, index build, three real questions against the bundled fixture project.',
        code: ['git clone https://github.com/dfrostar/neuralmind && cd neuralmind', 'bash scripts/demo.sh'],
    },
    {
        step: '2',
        title: 'Then measure YOUR codebase',
        body: 'The fixture is tiny (~500 lines, ~5.5×). Real repos consistently hit 40–70× on the same pipeline — run the benchmark on your own code and read your own number.',
        code: ['pip install neuralmind', 'cd /path/to/your-repo', 'neuralmind build .', 'neuralmind benchmark .'],
    },
    {
        step: '3',
        title: 'Verify what you installed',
        body: 'Check the SBOM, release integrity, and audit trail on the security page — and the full production before/after data on the effectiveness page.',
        code: null,
    },
];

export default function ProveIt() {
    return (
        <section id="prove-it" className="relative py-16 md:py-32 px-4 md:px-6">
            <div className="absolute top-1/3 left-0 w-[500px] h-[500px] bg-electric/3 rounded-full blur-[200px] -z-10" />
            <div className="max-w-5xl mx-auto">
                <div className="text-center mb-12 md:mb-16">
                    <span className="text-electric text-sm font-semibold tracking-wider uppercase mb-3 block">
                        Don&apos;t take our word for it
                    </span>
                    <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
                        Prove it in 5 minutes
                    </h2>
                    <p className="text-slate-400 text-base sm:text-lg md:text-xl max-w-xl mx-auto">
                        Every claim on this site reproduces from a fresh clone. No account, no signup, no cloud.
                    </p>
                </div>

                <div className="grid md:grid-cols-3 gap-4 mb-8">
                    {steps.map((s) => (
                        <div key={s.step} className="glow-card rounded-2xl p-6 flex flex-col">
                            <div className="flex items-center gap-3 mb-3">
                                <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-electric to-proton flex items-center justify-center font-display font-bold text-white text-sm">
                                    {s.step}
                                </span>
                                <h3 className="font-display text-lg font-bold text-white">{s.title}</h3>
                            </div>
                            <p className="text-slate-400 text-sm mb-4">{s.body}</p>
                            {s.code ? (
                                <div className="bg-carbon rounded-lg p-4 font-mono text-xs text-slate-300 overflow-x-auto mt-auto">
                                    {s.code.map((line) => (
                                        <p key={line} className="whitespace-nowrap">
                                            <span className="text-slate-600 select-none">$ </span>
                                            {line}
                                        </p>
                                    ))}
                                </div>
                            ) : (
                                <div className="flex flex-col gap-2 mt-auto">
                                    <a href="/security" className="text-electric hover:text-electric-bright text-sm font-medium transition-colors">
                                        Security posture: SBOM &amp; integrity →
                                    </a>
                                    <a href="/effectiveness" className="text-electric hover:text-electric-bright text-sm font-medium transition-colors">
                                        Measured production results →
                                    </a>
                                </div>
                            )}
                        </div>
                    ))}
                </div>

                <div className="glow-card rounded-2xl p-6 md:p-8">
                    <p className="text-slate-500 text-xs font-semibold uppercase tracking-wider mb-3">
                        What the demo prints (bundled fixture)
                    </p>
                    <div className="bg-carbon rounded-lg p-4 font-mono text-xs text-slate-400 overflow-x-auto">
                        <p className="whitespace-pre">{'Q: How does authentication work in this codebase?'}</p>
                        <p className="whitespace-pre text-slate-500">{'   naive = 4,736 tok   neuralmind =  829 tok   reduction =   5.7×'}</p>
                        <p className="whitespace-pre mt-2">{'Average reduction:   5.5×  across 3 queries'}</p>
                        <p className="whitespace-pre text-slate-500">{'Avg context size:    859 tokens  (vs 4,736 naive)'}</p>
                    </div>
                    <p className="text-slate-500 text-xs mt-3">
                        Small fixture, small multiplier — by design. It runs in CI on every commit as a regression
                        gate. The 40–70× headline comes from real repos; your own number is one{' '}
                        <code className="font-mono text-electric">neuralmind benchmark .</code> away.
                    </p>
                </div>
            </div>
        </section>
    );
}
