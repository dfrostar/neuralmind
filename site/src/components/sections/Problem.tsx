import Icon, { type IconName } from '@/components/ui/Icon';

// The homepage used to open on benchmarks without ever saying what hurts.
// Every figure below is read straight off bench/public/results.json (token
// counts and recall, never a ratio) — the same run the Benchmarks section and
// /benchmark/ quote.
const problems: { icon: IconName; title: string; body: string }[] = [
    {
        icon: 'restore',
        title: 'Every session starts from zero',
        body: 'Your agent rediscovers the same files each session — reading, grepping, re-reading. What it worked out yesterday is gone, and so is whatever it learned before the last context compaction.',
    },
    {
        icon: 'layers',
        title: 'Context is the bill',
        body: 'Pasting files is the default way to hand an agent context. Pasting every source file of the public benchmark repos costs 42K–232K tokens per question; NeuralMind’s assembled context averages under 1,000.',
    },
    {
        icon: 'query',
        title: 'Grep is not understanding',
        body: 'Keyword search matches words, not meaning. On three of the four benchmark repos ripgrep’s gold-file recall was 0.79–0.85, while it still read 27K–45K tokens per question.',
    },
];

export default function Problem() {
    return (
        <section id="problem" className="relative py-20 md:py-28 px-4 md:px-6">
            <div className="max-w-6xl mx-auto">
                <header className="max-w-2xl mb-10 md:mb-14">
                    <span className="eyebrow block mb-4">The problem</span>
                    <h2 className="font-display text-3xl sm:text-4xl md:text-[2.75rem] font-semibold text-white tracking-tighter mb-4">
                        AI coding agents have no long-term memory
                    </h2>
                    <p className="text-slate-400 text-base md:text-lg leading-relaxed">
                        Claude Code, Codex, Cursor and every other agent reason well over what is in
                        the window — and forget it when the session ends. So they pay, every time,
                        to find their way around a codebase they have seen before.
                    </p>
                </header>

                <ul className="grid grid-cols-1 md:grid-cols-3 border-t border-l border-carbon-border rounded-sm overflow-hidden">
                    {problems.map((p) => (
                        <li key={p.title} className="border-b border-r border-carbon-border p-7 md:p-8">
                            <Icon name={p.icon} className="w-6 h-6 text-faint mb-6" />
                            <h3 className="font-display text-xl font-semibold text-white tracking-tight mb-3">
                                {p.title}
                            </h3>
                            <p className="text-slate-400 leading-relaxed text-[0.9375rem]">{p.body}</p>
                        </li>
                    ))}
                </ul>

                <p className="mt-8 text-slate-300 text-base md:text-lg leading-relaxed max-w-3xl">
                    NeuralMind is the missing layer: a persistent code graph plus associations
                    learned from how you work, queried on your machine — a local index lookup, not
                    another model call — so your agent starts every session already knowing where
                    things are.
                </p>
            </div>
        </section>
    );
}
