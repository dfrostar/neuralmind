'use client';

import Icon, { type IconName } from '@/components/ui/Icon';
import { withCode } from '@/lib/ticks';

// Copy unchanged. `icon` was ⚡ / 🧠 / 🔮 — a crystal ball for the Hebbian
// synapse layer, which undersold the one genuinely novel thing in the product.
const steps: { icon: IconName; title: string; desc: string; time: string }[] = [
    {
        icon: 'index',
        title: 'Index',
        desc: 'tree-sitter parses your codebase into a graph — functions, classes, imports, comments. Ten languages, zero config. TurboVec compresses vectors 4-bit.',
        time: '~15 min',
    },
    {
        icon: 'query',
        title: 'Query',
        desc: 'Your agent asks a question. Progressive L0–L3 disclosure pulls exactly the right amount of context — a local index lookup, not another model call.',
        time: 'local lookup',
    },
    {
        icon: 'recall',
        title: 'Remember',
        desc: 'A Hebbian synapse layer learns co-activations from how you actually use the codebase. Budget-neutral, runs in the background.',
        time: 'Forever',
    },
];

export default function HowItWorks() {
    return (
        <section id="how-it-works" className="relative py-20 md:py-28 px-4 md:px-6">
            <div className="max-w-6xl mx-auto">
                <header className="max-w-2xl mb-10 md:mb-14">
                    <span className="eyebrow block mb-4">Pipeline</span>
                    <h2 className="font-display text-3xl sm:text-4xl md:text-[2.75rem] font-semibold text-white tracking-tighter mb-4">
                        How it works
                    </h2>
                    <p className="text-slate-400 text-base md:text-lg leading-relaxed">
                        {withCode(
                            'Three steps, then it runs forever on every git commit via `neuralmind init-hook .`',
                        )}
                    </p>
                </header>

                <ol className="grid grid-cols-1 md:grid-cols-3 border-t border-l border-carbon-border rounded-sm overflow-hidden">
                    {steps.map((step, i) => (
                        <li
                            key={step.title}
                            className="relative border-b border-r border-carbon-border p-7 md:p-8"
                        >
                            {/*
                                The step number was 72px of near-invisible outline
                                type sitting behind the content. It now reads as
                                what it is: an ordinal, in the same mono face as
                                every other piece of machine output on the site.
                            */}
                            <div className="flex items-center justify-between mb-6">
                                <Icon name={step.icon} className="w-6 h-6 text-electric" />
                                <span className="font-mono text-xs text-faint tabular-nums">
                                    {String(i + 1).padStart(2, '0')} / {String(steps.length).padStart(2, '0')}
                                </span>
                            </div>

                            <h3 className="font-display text-xl font-semibold text-white tracking-tight mb-3">
                                {step.title}
                            </h3>
                            <p className="text-slate-400 leading-relaxed text-[0.9375rem] mb-6">
                                {step.desc}
                            </p>

                            <span className="inline-flex items-center gap-2 font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-faint">
                                <span className="w-1 h-1 rounded-full bg-proton" />
                                {step.time}
                            </span>
                        </li>
                    ))}
                </ol>
            </div>
        </section>
    );
}
