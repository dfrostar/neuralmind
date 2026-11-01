import EvidenceBadge, { type EvidenceLevel } from './EvidenceBadge';

/**
 * One measured number: a label, the value, an optional sentence of context
 * and the kind of evidence behind it.
 *
 * Stats sit in a `StatGrid`, the hairline ledger the homepage and /benchmark
 * already used: the grid draws the top and left rules, each cell its own
 * bottom and right, so any column count closes cleanly.
 *
 * A value must be in `site/claims.json` like any other number on the site;
 * this component makes it easy to label, not exempt from the ledger.
 */
export function StatGrid({ children, className = '' }: { children: React.ReactNode; className?: string }) {
    return <dl className={`grid bg-carbon-card border-t border-l border-carbon-border ${className}`}>{children}</dl>;
}

export default function Stat({
    label,
    value,
    note,
    evidence,
    figure = true,
}: {
    label: string;
    value: React.ReactNode;
    note?: React.ReactNode;
    evidence?: EvidenceLevel;
    /** False for a word rather than a number ("Free"): set in the display face, not mono. */
    figure?: boolean;
}) {
    return (
        <div className="border-b border-r border-carbon-border p-5 flex flex-col">
            <dt className="label mb-3">{label}</dt>
            <dd className="flex flex-col flex-1">
                <p
                    className={
                        figure
                            ? 'metric text-stat text-white mb-2'
                            : 'font-display text-stat font-semibold tracking-tight text-white mb-2'
                    }
                >
                    {value}
                </p>
                {note && <p className="text-muted text-sm leading-relaxed">{note}</p>}
                {evidence && <EvidenceBadge level={evidence} className="self-start mt-3" />}
            </dd>
        </div>
    );
}
