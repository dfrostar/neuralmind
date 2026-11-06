import type { SeriesPoint } from '@/lib/record';

/**
 * One metric over time, as an inline SVG.
 *
 * - x is the run's date, so a skipped month shows as a gap, not a closer step.
 * - A line joins only runs that both have a value. A null (not recorded, or
 *   withheld by a gate) breaks the line and leaves a tick on the axis; the
 *   line is never drawn across it, and no point is invented to fill it.
 * - Rates sit on a fixed 0–1 axis and ratios on an axis from zero, so a small
 *   move can't be drawn as a cliff.
 * - A dashed rule marks each version bump, labelled with the new version.
 * - A run that fell from the previous one is drawn in the warning colour, as
 *   its table row is highlighted.
 *
 * The table beside it carries the same values as text; the SVG has only its
 * summary label. No SVG <title> elements: scripts/check_site_seo.py counts
 * every <title> in the page and wants exactly one.
 */
const PAD_X = 8;
const PAD_TOP = 6;
const PAD_BOTTOM = 16;

export default function Sparkline({
    points,
    label,
    domain,
    format,
    width = 240,
    height = 72,
}: {
    points: SeriesPoint[];
    /** What the line is, e.g. "hit@1, rfnode-guide". */
    label: string;
    /** Fixed y-axis; defaults to zero up to just above the largest value. */
    domain?: [number, number];
    format: (v: number) => string;
    width?: number;
    height?: number;
}) {
    const values = points.map((p) => p.v).filter((v): v is number => v !== null);
    const [lo, hi] = domain ?? [0, values.length ? Math.max(...values) * 1.15 : 1];
    const bottom = height - PAD_BOTTOM;
    const times = points.map((p) => p.t);
    const t0 = Math.min(...times);
    const t1 = Math.max(...times);
    const x = (p: SeriesPoint, i: number) => {
        if (points.length === 1) return width / 2;
        // Runs logged at the same instant fall back to even spacing.
        const f = t1 > t0 ? (p.t - t0) / (t1 - t0) : i / (points.length - 1);
        return PAD_X + f * (width - 2 * PAD_X);
    };
    const y = (v: number) => bottom - ((v - lo) / (hi - lo || 1)) * (bottom - PAD_TOP);

    // Consecutive runs with values; a null ends the segment.
    const segments: { x: number; y: number }[][] = [];
    let open: { x: number; y: number }[] = [];
    points.forEach((p, i) => {
        if (p.v === null) {
            if (open.length) segments.push(open);
            open = [];
        } else {
            open.push({ x: x(p, i), y: y(p.v) });
        }
    });
    if (open.length) segments.push(open);

    const last = values.at(-1);
    const summary =
        last === undefined
            ? `${label}: no value shown yet`
            : `${label}: ${values.length} of ${points.length} runs shown, latest ${format(last)}`;
    const r = (n: number) => n.toFixed(1);

    return (
        <svg
            viewBox={`0 0 ${width} ${height}`}
            width={width}
            height={height}
            role="img"
            aria-label={summary}
            className="max-w-full h-auto overflow-visible"
        >
            <line x1={0} x2={width} y1={bottom} y2={bottom} className="stroke-carbon-border" strokeWidth={1} />
            {points.map((p, i) =>
                p.bump ? (
                    <g key={`bump-${i}`} data-bump={p.bump}>
                        <line
                            x1={x(p, i)}
                            x2={x(p, i)}
                            y1={PAD_TOP - 2}
                            y2={bottom}
                            className="stroke-carbon-line"
                            strokeWidth={1}
                            strokeDasharray="2 2"
                        />
                        <text
                            x={Math.min(Math.max(x(p, i), 18), width - 18)}
                            y={height - 3}
                            textAnchor="middle"
                            className="fill-faint font-mono"
                            fontSize={9}
                        >
                            {p.bump}
                        </text>
                    </g>
                ) : null,
            )}
            {segments
                .filter((s) => s.length > 1)
                .map((s, i) => (
                    <path
                        key={`seg-${i}`}
                        data-segment={s.length}
                        d={s.map((pt, j) => `${j ? 'L' : 'M'}${r(pt.x)},${r(pt.y)}`).join(' ')}
                        fill="none"
                        className="stroke-proton"
                        strokeWidth={1.5}
                        strokeLinejoin="round"
                    />
                ))}
            {points.map((p, i) =>
                p.v === null ? (
                    <line
                        key={`gap-${i}`}
                        data-gap=""
                        x1={x(p, i)}
                        x2={x(p, i)}
                        y1={bottom - 3}
                        y2={bottom + 3}
                        className="stroke-faint"
                        strokeWidth={1}
                    />
                ) : (
                    <circle
                        key={`pt-${i}`}
                        data-point={p.v}
                        cx={r(x(p, i))}
                        cy={r(y(p.v))}
                        r={i === points.length - 1 ? 3 : 2}
                        className={p.regressed ? 'fill-warn' : 'fill-proton'}
                    />
                ),
            )}
        </svg>
    );
}
