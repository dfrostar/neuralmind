'use client';

const steps = [
    {
        icon: '⚡',
        title: 'Index',
        desc: 'tree-sitter parses your codebase into a graph — functions, classes, imports, comments. Ten languages, zero config.',
        time: '~15 min',
    },
    {
        icon: '🧠',
        title: 'Query',
        desc: 'Your agent asks a question. Progressive L0–L3 disclosure pulls exactly the right amount of context — never the whole repo.',
        time: '<1s',
    },
    {
        icon: '🔮',
        title: 'Remember',
        desc: 'A Hebbian synapse layer learns co-activations from how you actually use the codebase. Budget-neutral, runs in the background.',
        time: 'Forever',
    },
];

export default function HowItWorks() {
    return (
        <section id="how-it-works" className="relative py-16 md:py-32 px-4 md:px-6">
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-electric/3 rounded-full blur-[200px] -z-10" />

            <div className="max-w-5xl mx-auto">
                <div className="text-center mb-12 md:mb-20">
                    <span className="text-electric-mono text-sm font-semibold tracking-wider uppercase mb-3 block">
                        Pipeline
                    </span>
                    <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
                        How it works
                    </h2>
                    <p className="text-slate-400 text-base sm:text-lg md:text-xl max-w-xl mx-auto">
                        Three steps, then it runs forever on every git commit via `neuralmind init-hook .`
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
                    {steps.map((step, i) => (
                        <div
                            key={step.title}
                            className="glow-card rounded-2xl p-6 md:p-8 relative overflow-hidden"
                        >
                            {/* Step number */}
                            <div className="absolute top-4 right-4 text-6xl font-display font-bold text-carbon-border/30 leading-none">
                                {String(i + 1).padStart(2, '0')}
                            </div>

                            {/* Icon */}
                            <div className="text-4xl mb-4">{step.icon}</div>

                            {/* Title */}
                            <h3 className="font-display text-2xl font-bold text-white mb-3">{step.title}</h3>

                            {/* Description */}
                            <p className="text-slate-400 leading-relaxed mb-4 text-[15px]">{step.desc}</p>

                            {/* Time */}
                            <span className="text-electric-mono text-xs font-semibold tracking-wide">
                                {step.time}
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
