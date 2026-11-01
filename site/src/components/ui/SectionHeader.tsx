/**
 * One section header, used by every section.
 *
 * Each section previously wrote its own: centred, with an eyebrow in
 * `text-sm font-semibold uppercase tracking-wider` coloured either electric
 * or proton depending on the section, and an `md:text-5xl font-bold` title.
 * Nine near-identical implementations that disagreed on colour and weight is
 * how a page ends up looking assembled rather than designed.
 *
 * The eyebrow went in the Console restyle: a one-word label over every head
 * ("Features" over "What your agent gets") is the most recognisable tell of a
 * generated page, and each title here already says what its section is.
 *
 * Left-aligned, because centred body copy over 60+ characters gives the eye
 * no consistent return edge — which is why the Benchmarks intro broke into
 * four ragged lines around its inline code span.
 */
export default function SectionHeader({
    title,
    children,
    className = '',
}: {
    title: string;
    children?: React.ReactNode;
    className?: string;
}) {
    return (
        <header className={`max-w-2xl mb-10 md:mb-14 ${className}`}>
            <h2 className="font-display text-3xl sm:text-4xl md:text-display font-semibold text-white tracking-tighter mb-4">
                {title}
            </h2>
            {children && (
                <div className="text-muted text-base md:text-lg leading-relaxed">{children}</div>
            )}
        </header>
    );
}
