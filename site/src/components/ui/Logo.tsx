/**
 * The mark.
 *
 * Was a rounded square filled with a blue→purple gradient containing the
 * letter "N" — the default logo of every generated startup template, and the
 * one element that appears on every page of the site.
 *
 * This draws the actual product instead: a hub node with three weighted edges
 * to its neighbours, which is what the synapse layer is. The three edges carry
 * different stroke weights because the weights are the point — associations
 * strengthen with co-activation.
 */
export default function Logo({ className = 'w-[1.625rem] h-[1.625rem]' }: { className?: string }) {
    return (
        <svg viewBox="0 0 28 28" fill="none" className={className} aria-hidden="true">
            <path d="M9.6 9.1 12.3 12" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" />
            <path d="M15.9 12.6 19.4 10.6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            <path d="M14.6 16.5 16.2 20" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
            <circle cx="14" cy="14" r="3.1" fill="currentColor" />
            <circle cx="7.4" cy="7.4" r="2.4" fill="currentColor" />
            <circle cx="21.4" cy="9" r="1.9" fill="currentColor" opacity="0.75" />
            <circle cx="17.2" cy="21.6" r="1.5" fill="currentColor" opacity="0.5" />
        </svg>
    );
}
