import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';
import { Prose, WorkingOn } from '@/components/performance/Narrative';
import ProfileCard from '@/components/performance/ProfileCard';
import RecordTable from '@/components/performance/RecordTable';
import Sparkline from '@/components/performance/Sparkline';
import { RateValue, RatioValue, fmtRate, fmtRatio } from '@/components/performance/Gated';
import Callout from '@/components/ui/Callout';
import CommandLine from '@/components/ui/CommandLine';
import EvidenceBadge from '@/components/ui/EvidenceBadge';
import { blob } from '@/lib/evidence';
import { RECORD, performanceRecord } from '@/lib/performance';
import { SMALL_SAMPLE_N, rateView, ratioView, series, type Metric, type ProjectHistory } from '@/lib/record';
import { pageMetadata } from '@/lib/seo';
import type { Metadata } from 'next';

export const metadata: Metadata = pageMetadata({
    path: '/performance',
    title: 'Performance Record: Retrieval Run by Run — NeuralMind',
    description:
        'Hit@1, hit@5 and tokens vs indexed code on our own repos, re-measured on one dev box. Raw rows committed; misses, sample sizes and drops stay on the page.',
    keywords: [
        'longitudinal benchmark',
        'retrieval hit rate over releases',
        'code retrieval regression tracking',
        'token reduction measured baseline',
        'NeuralMind performance record',
        'neuralmind eval',
    ],
    ogTitle: 'The NeuralMind performance record',
});

/**
 * Every number on this page is a row of benchmarks/ai9970/record.jsonl, read
 * at build time through lib/performance and gated by lib/record: none is typed
 * here. Adding a month is a change to the record (and a narrative), not to
 * this file.
 */
const { projects, profile, narrative, evidence, lastRun } = performanceRecord();

const TRENDS: { metric: Metric; label: string; domain?: [number, number] }[] = [
    { metric: 'hit_at_1', label: 'hit@1', domain: [0, 1] },
    { metric: 'hit_at_5', label: 'hit@5', domain: [0, 1] },
    { metric: 'ratio_vs_indexed', label: 'vs indexed code' },
];

function Trend({ history, metric, label, domain }: { history: ProjectHistory; metric: Metric; label: string; domain?: [number, number] }) {
    const latest = history.runs.at(-1)?.row;
    const isRatio = metric === 'ratio_vs_indexed';
    return (
        <figure className="panel rounded-card p-4 flex flex-col gap-3 min-w-0">
            <figcaption className="flex items-start justify-between gap-3">
                <span className="eyebrow">{label}</span>
                {latest &&
                    (isRatio ? (
                        <RatioValue view={ratioView(latest)} align="end" />
                    ) : (
                        <RateValue view={rateView(latest[metric], latest.gold_n)} align="end" />
                    ))}
            </figcaption>
            <Sparkline
                points={series(history, metric)}
                label={`${label}, ${history.project}`}
                domain={domain}
                format={isRatio ? fmtRatio : fmtRate}
            />
            <p className="text-faint text-caption">
                {isRatio ? 'Axis from zero.' : 'Fixed 0–1 axis.'}
                {history.runs.some((r) => r.versionBump) && ' Dashed rules mark a new version.'}
            </p>
        </figure>
    );
}

export default function PerformancePage() {
    return (
        <>
            <Navbar />
            <main className="max-w-5xl mx-auto px-4 md:px-6 pt-32 pb-16">
                <header className="mb-12 pb-8 border-b border-carbon-border">
                    <span className="eyebrow block mb-4">Performance record</span>
                    <h1 className="font-display text-3xl md:text-display font-bold text-white mb-5 leading-display tracking-tighter">
                        Retrieval on our own repos, run by run
                    </h1>
                    <p className="text-lg text-body leading-relaxed mb-4 max-w-3xl">
                        The same projects, re-measured on the same machine with the same command, each row
                        committed as the run produced it. A run that does worse than the one before stays on
                        the page, highlighted; a value a run did not record stays blank.
                    </p>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted">
                        <EvidenceBadge level={evidence} />
                        {lastRun && <span>Latest run {lastRun.slice(0, 10)}</span>}
                        <a href={blob(RECORD.source)} className="text-electric hover:text-electric-bright transition-colors">
                            Raw rows (JSONL) →
                        </a>
                    </div>
                </header>

                <Callout title="How to read it" className="mb-12">
                    <ul className="list-disc pl-5 space-y-1.5 marker:text-faint">
                        <li>
                            A hit rate always shows how many questions it is over and how many were missed.
                            Under {SMALL_SAMPLE_N} questions it carries a small-sample badge: one question moves
                            it a long way.
                        </li>
                        <li>
                            The ratio is every code file the index covers, in tokens, over the mean context per
                            question. It is shown only beside that measured baseline; a run whose baseline was
                            not measured is left out whole, and counted under its table.
                        </li>
                        <li>
                            Our own repos, one dev box, one maintainer: a field report, reproducible in method,
                            not in number. Run it on your own repo with the commands at the bottom.
                        </li>
                    </ul>
                </Callout>

                {projects.length === 0 ? (
                    <Callout variant="not-measured" className="mb-14">
                        No runs are recorded yet. The first month&rsquo;s rows land in {RECORD.source}.
                    </Callout>
                ) : (
                    <section className="mb-14" aria-labelledby="projects">
                        <h2 id="projects" className="font-display text-xl font-bold text-white mb-6">
                            Projects
                        </h2>
                        <div className="grid md:grid-cols-2 gap-4">
                            {projects.map((h) => (
                                <ProfileCard
                                    key={h.project}
                                    history={h}
                                    shape={profile.projects[h.project]?.shape ?? null}
                                    hardware={profile.machine.hardware}
                                    method={profile.method}
                                    evidence={evidence}
                                />
                            ))}
                        </div>
                    </section>
                )}

                {narrative?.site && (
                    <section className="mb-14" aria-labelledby="this-month">
                        <span className="eyebrow block mb-3">{narrative.month}</span>
                        <h2 id="this-month" className="font-display text-xl font-bold text-white mb-5">
                            This month
                        </h2>
                        <div className="max-w-3xl">
                            <Prose markdown={narrative.site} />
                        </div>
                    </section>
                )}

                {projects.map((h) => (
                    <section key={h.project} className="mb-14" aria-labelledby={`run-${h.project}`}>
                        <h2 id={`run-${h.project}`} className="font-display text-xl font-bold text-white mb-6">
                            {h.project}
                        </h2>
                        <div className="grid sm:grid-cols-3 gap-4 mb-6">
                            {TRENDS.map((t) => (
                                <Trend key={t.metric} history={h} {...t} />
                            ))}
                        </div>
                        <RecordTable history={h} />
                    </section>
                ))}

                {narrative && narrative.working.length > 0 && (
                    <section className="mb-14" aria-labelledby="working-on">
                        <span className="eyebrow block mb-3">{narrative.month}</span>
                        <h2 id="working-on" className="font-display text-xl font-bold text-white mb-5">
                            What we are working on
                        </h2>
                        <WorkingOn items={narrative.working} />
                    </section>
                )}

                <section className="rounded-card panel-accent p-6 md:p-7">
                    <h2 className="font-display text-lg font-semibold tracking-tight text-white mb-2">
                        Reproduce it on your repo
                    </h2>
                    <p className="text-muted text-sm leading-relaxed mb-5">
                        These rows come from two commands you can run on your own code. <code className="font-mono text-code-inline text-electric-bright">eval</code>{' '}
                        scores questions you write, each with the file that answers it; <code className="font-mono text-code-inline text-electric-bright">benchmark</code>{' '}
                        measures tokens per question against your indexed code.
                    </p>
                    <div className="flex flex-col sm:flex-row flex-wrap gap-3 mb-5">
                        <CommandLine command="neuralmind eval ." />
                        <CommandLine command="neuralmind benchmark ." />
                    </div>
                    <a href="/measure-your-own/" className="text-electric hover:text-electric-bright transition-colors text-sm">
                        Step-by-step: measure it on your own repo →
                    </a>
                </section>
            </main>
            <Footer />
        </>
    );
}
