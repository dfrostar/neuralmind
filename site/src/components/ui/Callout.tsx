/**
 * A boxed aside in running copy.
 *
 * - `note`: context the reader can skip.
 * - `evidence`: points at a measured result; `proton`, like every other
 *   evidence mark on the site.
 * - `caution`: a limit or a known loss the reader should not skip.
 * - `not-measured`: says outright what the site does NOT measure. Dashed and
 *   grey so it can never be mistaken for a result, and it carries its own
 *   label so copy can't drop the words "not measured" by accident. Pair it with
 *   a `disclosure` entry in `site/claims.json`.
 */
type Variant = 'note' | 'evidence' | 'caution' | 'not-measured';

const VARIANTS: Record<Variant, { box: string; label: string; defaultTitle?: string }> = {
    note: { box: 'border-carbon-border bg-carbon-card', label: 'text-faint' },
    evidence: { box: 'border-proton/30 bg-proton/5', label: 'text-proton' },
    caution: { box: 'border-warn/30 bg-warn/5', label: 'text-warn' },
    'not-measured': {
        box: 'border-dashed border-carbon-line bg-transparent',
        label: 'text-faint',
        defaultTitle: 'Not measured',
    },
};

export default function Callout({
    variant = 'note',
    title,
    children,
    className = '',
}: {
    variant?: Variant;
    title?: string;
    children: React.ReactNode;
    className?: string;
}) {
    const v = VARIANTS[variant];
    const heading = title ?? v.defaultTitle;
    return (
        <aside role="note" className={`rounded-card border px-5 py-4 ${v.box} ${className}`}>
            {heading && (
                <p className={`font-mono text-eyebrow uppercase tracking-eyebrow mb-2 ${v.label}`}>{heading}</p>
            )}
            <div className="text-body text-sm leading-relaxed">{children}</div>
        </aside>
    );
}
