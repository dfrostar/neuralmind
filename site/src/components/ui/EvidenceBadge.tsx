import claims from '../../../claims.json';

/**
 * Which kind of evidence a number on the page is.
 *
 * The levels and what each one promises live in `site/claims.json`
 * (`_evidence_levels`), the same file every claim on the site names its level
 * in. Keying the labels by that object's type means a level added there
 * without a label here fails the build rather than rendering blank.
 *
 * Strength reads in the styling: the two levels a reader can check for
 * themselves are `proton` (measured), a one-repo field report, a community
 * submission, an exploratory pilot and a not-pre-registered follow-up are neutral, and a disclosure — something we say is NOT
 * measured — is dashed, so it never passes for a result at a glance.
 */
export type EvidenceLevel = keyof typeof claims._evidence_levels;

const LEVELS: Record<EvidenceLevel, { label: string; className: string }> = {
    'ci-gated': { label: 'CI-gated', className: 'bg-proton/10 text-proton border-proton/30' },
    reproducible: { label: 'Reproducible', className: 'text-proton border-proton/30' },
    'field-report': { label: 'Field report', className: 'text-body border-carbon-line' },
    community: { label: 'Community', className: 'text-muted border-carbon-line' },
    pilot: { label: 'Pilot', className: 'text-body border-carbon-line' },
    exploratory: { label: 'Exploratory', className: 'text-muted border-carbon-line' },
    disclosure: { label: 'Not measured', className: 'text-faint border-carbon-line border-dashed' },
};

export default function EvidenceBadge({
    level,
    children,
    className = '',
}: {
    level: EvidenceLevel;
    /** Replaces the default label, e.g. "Field report — not CI-gated". */
    children?: React.ReactNode;
    className?: string;
}) {
    const { label, className: tone } = LEVELS[level];
    return (
        <span
            title={claims._evidence_levels[level]}
            className={`inline-flex items-center px-2 py-0.5 rounded-control border font-mono text-eyebrow uppercase tracking-eyebrow whitespace-nowrap ${tone} ${className}`}
        >
            {children ?? label}
        </span>
    );
}
