import type { Metric, ProjectHistory, Regression } from '@/lib/record';
import { METRIC_LABELS, rateView, ratioView } from '@/lib/record';
import { RateValue, RatioValue, fmtInt, fmtRate, fmtRatio } from './Gated';

/**
 * Every published run of one project, oldest first. A run that fell from the
 * one before it keeps its place and is tinted (`.is-regressed`), with the
 * previous value beside each metric that dropped; a version bump is marked on
 * its row. Rows withheld by the measured-only gate are counted under the
 * table, never silently dropped.
 */
function Drop({ regression }: { regression?: Regression }) {
    if (!regression) return null;
    const fmt = regression.metric === 'ratio_vs_indexed' ? fmtRatio : fmtRate;
    return <span className="block text-warn text-caption whitespace-nowrap">↓ from {fmt(regression.from)}</span>;
}

export function withheldNote(withheld: Record<string, number>): string | null {
    const parts = Object.entries(withheld).map(([reason, n]) => `${n} ${n === 1 ? 'run' : 'runs'} (${reason})`);
    return parts.length ? `Not shown: ${parts.join(', ')}. Only runs measured against the indexed code are published.` : null;
}

export default function RecordTable({ history }: { history: ProjectHistory }) {
    const note = withheldNote(history.withheld);
    const dropOf = (regs: Regression[], metric: Metric) => regs.find((r) => r.metric === metric);
    return (
        <div>
            <div className="overflow-x-auto">
                <table className="data-table min-w-[52rem]">
                    <caption className="sr-only">Every published run of {history.project}, oldest first</caption>
                    <thead>
                        <tr>
                            <th scope="col">Run</th>
                            <th scope="col">Version</th>
                            <th scope="col" className="num">{METRIC_LABELS.hit_at_1}</th>
                            <th scope="col" className="num">{METRIC_LABELS.hit_at_5}</th>
                            <th scope="col" className="num">{METRIC_LABELS.mrr}</th>
                            <th scope="col" className="num">{METRIC_LABELS.ratio_vs_indexed}</th>
                            <th scope="col" className="num">Median query</th>
                            <th scope="col" className="num">Nodes</th>
                        </tr>
                    </thead>
                    <tbody>
                        {history.runs.length === 0 && (
                            <tr>
                                <td colSpan={8} className="text-faint">No published runs.</td>
                            </tr>
                        )}
                        {history.runs.map(({ row, versionBump, regressions, goldChanged }) => (
                            <tr
                                key={row.ts}
                                className={regressions.length ? 'is-regressed' : undefined}
                                data-regressed={regressions.length ? regressions.map((r) => r.metric).join(' ') : undefined}
                            >
                                <th scope="row" className="align-top">
                                    <span className="block whitespace-nowrap">{row.ts.slice(0, 10)}</span>
                                    {row.git_sha && <span className="block text-faint">{row.git_sha.slice(0, 10)}</span>}
                                    {regressions.length > 0 && (
                                        <span className="block text-warn font-sans font-medium mt-1">Dropped</span>
                                    )}
                                    {goldChanged && (
                                        <span className="block text-faint text-caption font-sans whitespace-nowrap">
                                            gold set {goldChanged.from} → {goldChanged.to}
                                        </span>
                                    )}
                                </th>
                                <td className="align-top">
                                    <span className="block font-mono text-caption">{row.version ?? '—'}</span>
                                    {versionBump && (
                                        <span
                                            data-bump={versionBump.to}
                                            className="inline-flex items-center mt-1 px-2 py-0.5 rounded-control border border-carbon-line text-body text-xs font-medium whitespace-nowrap"
                                        >
                                            New version
                                        </span>
                                    )}
                                </td>
                                <td className="num align-top">
                                    <RateValue view={rateView(row.hit_at_1, row.gold_n)} align="end" />
                                    <Drop regression={dropOf(regressions, 'hit_at_1')} />
                                </td>
                                <td className="num align-top">
                                    <RateValue view={rateView(row.hit_at_5, row.gold_n)} align="end" />
                                    <Drop regression={dropOf(regressions, 'hit_at_5')} />
                                </td>
                                <td className="num align-top">
                                    <RateValue view={rateView(row.mrr, row.gold_n, false)} align="end" />
                                    <Drop regression={dropOf(regressions, 'mrr')} />
                                </td>
                                <td className="num align-top">
                                    <RatioValue view={ratioView(row)} align="end" />
                                    <Drop regression={dropOf(regressions, 'ratio_vs_indexed')} />
                                </td>
                                <td className="num align-top metric">
                                    {row.median_query_s === null ? '—' : `${row.median_query_s.toFixed(3)} s`}
                                </td>
                                <td className="num align-top metric">{row.nodes === null ? '—' : fmtInt(row.nodes)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            {note && (
                <p className="text-faint text-caption mt-3" data-withheld-rows="">
                    {note}
                </p>
            )}
        </div>
    );
}
