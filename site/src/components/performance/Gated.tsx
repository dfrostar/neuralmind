import type { RateView, RatioView } from '@/lib/record';
import { SMALL_SAMPLE_N } from '@/lib/record';

/**
 * The only way /performance prints a rate or a ratio. Each takes the gate's
 * verdict from `lib/record.ts`, never a bare number, so a hit rate can't
 * appear without its gold-set size and misses, nor a ratio without its
 * measured baseline. A withheld value says why, in place.
 */

export const fmtRate = (v: number) => v.toFixed(3);
export const fmtRatio = (v: number) => `${v.toFixed(1)}×`;
export const fmtInt = (v: number) => v.toLocaleString('en-US');

export function SmallSampleBadge() {
    return (
        <span
            title={`Fewer than ${SMALL_SAMPLE_N} questions: one question moves the rate by a large step.`}
            className="inline-flex items-center px-1.5 rounded-control border border-warn/30 text-warn font-mono text-eyebrow uppercase tracking-eyebrow whitespace-nowrap"
        >
            small sample
        </span>
    );
}

type Align = 'start' | 'end';
const column = (align: Align) => `inline-flex flex-col ${align === 'end' ? 'items-end text-right' : 'items-start'}`;

export function WithheldValue({ reason, align = 'start' }: { reason: string; align?: Align }) {
    return (
        <span className={column(align)} data-withheld={reason}>
            <span className="text-faint" aria-hidden="true">
                —
            </span>
            <span className="text-faint text-caption">not shown: {reason}</span>
        </span>
    );
}

/** "0.667" over "8 of 12 · 4 missed", or for MRR "n = 12". */
export function RateValue({ view, align = 'start' }: { view: RateView; align?: Align }) {
    if (!view.shown) return <WithheldValue reason={view.reason} align={align} />;
    return (
        <span className={column(align)} data-rate={view.value} data-n={view.n}>
            <span className="metric text-white">{fmtRate(view.value)}</span>
            <span className="text-faint text-caption">
                {view.hits !== null && view.misses !== null
                    ? `${view.hits} of ${view.n} · ${view.misses} missed`
                    : `n = ${view.n}`}
            </span>
            {view.small && (
                <span className="mt-1">
                    <SmallSampleBadge />
                </span>
            )}
        </span>
    );
}

/** The ratio over its baseline: "vs 52,218 measured tokens". */
export function RatioValue({ view, align = 'start' }: { view: RatioView; align?: Align }) {
    if (!view.shown) return <WithheldValue reason={view.reason} align={align} />;
    return (
        <span className={column(align)} data-ratio={view.ratio} data-baseline={view.baselineTok}>
            <span className="metric text-white">{fmtRatio(view.ratio)}</span>
            <span className="text-faint text-caption">
                vs {fmtInt(view.baselineTok)} measured tokens
            </span>
        </span>
    );
}
