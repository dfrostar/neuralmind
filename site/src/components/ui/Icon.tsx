/**
 * The icon set.
 *
 * Every icon on the homepage used to be an emoji rendered at `text-3xl` —
 * 🧠 🔮 🚀 🆓 🗑️ and eleven more. Emoji are drawn by the operating system, so
 * the site had no control over their weight, colour, alignment or metrics:
 * they arrived full-colour and cartoon-styled into an otherwise monochrome
 * page, and looked different on macOS, Windows and Android. That is the
 * single loudest "assembled from a template" signal a product page can send.
 *
 * These are drawn to one spec instead: 24×24 box, 1.5 stroke, round caps and
 * joins, no fills, `currentColor` throughout. They inherit text colour and
 * size like type does, so an icon in a muted card is muted and an icon in an
 * accented one is accented, without a second set of assets.
 *
 * Each one depicts its actual subject — the synapse layer is a weighted node
 * cluster, progressive disclosure is four rows of increasing length, the
 * local engine is a struck-through globe — rather than reaching for the
 * nearest vaguely-thematic pictograph.
 */

export type IconName =
    | 'chip'
    | 'synapse'
    | 'layers'
    | 'dashboard'
    | 'doc-code'
    | 'doc-link'
    | 'hub'
    | 'tree'
    | 'restore'
    | 'key'
    | 'offline'
    | 'terminal'
    | 'shield-check'
    | 'export'
    | 'report-query'
    | 'index'
    | 'query'
    | 'recall'
    | 'check'
    | 'arrow-right';

const paths: Record<IconName, React.ReactNode> = {
    // Local retrieval — silicon, not a round trip.
    chip: (
        <>
            <rect x="5" y="5" width="14" height="14" rx="2" />
            <rect x="9" y="9" width="6" height="6" rx="1" />
            <path d="M9 3v2M15 3v2M9 19v2M15 19v2M3 9h2M3 15h2M19 9h2M19 15h2" />
        </>
    ),
    // Hebbian layer — a hub and its co-activated neighbours.
    synapse: (
        <>
            <circle cx="12" cy="12" r="2.5" />
            <circle cx="5" cy="5.5" r="1.75" />
            <circle cx="19.5" cy="8" r="1.75" />
            <circle cx="16" cy="19.5" r="1.75" />
            <path d="M6.3 6.9 10.2 10.4" />
            <path d="M17.9 8.9 14.2 11" />
            <path d="M15.1 17.6 13 14.3" />
        </>
    ),
    // L0 → L3: each level discloses more than the last.
    layers: (
        <>
            <path d="M4 5.5h5" />
            <path d="M4 10.5h9" />
            <path d="M4 15.5h13" />
            <path d="M4 20.5h16" />
        </>
    ),
    dashboard: (
        <>
            <rect x="3" y="4" width="18" height="16" rx="2" />
            <path d="M3 9h18" />
            <path d="M7 16.5l3-3.5 2.5 2L17 10.5" />
        </>
    ),
    'doc-code': (
        <>
            <path d="M13.5 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8.5Z" />
            <path d="M13.5 3v5.5H19" />
            <path d="M10.6 12.6 9 14.2l1.6 1.6" />
            <path d="M13.4 12.6 15 14.2l-1.6 1.6" />
        </>
    ),
    // Business docs seeded into the code graph.
    'doc-link': (
        <>
            <rect x="3" y="4.5" width="9" height="12" rx="1.5" />
            <path d="M5.7 8h3.6" />
            <path d="M5.7 11h3.6" />
            <circle cx="19.5" cy="7" r="1.75" />
            <circle cx="18" cy="17.5" r="2" />
            <path d="M12 10c3.2 0 3.6-2 5.8-2.7" />
            <path d="M12 13.4c3 0 4.2 1.8 4.9 2.6" />
        </>
    ),
    hub: (
        <>
            <rect x="8.5" y="8.5" width="7" height="7" rx="1.75" />
            <path d="M12 8.5V5.5" />
            <path d="M15.5 12h3" />
            <path d="M12 15.5v3" />
            <path d="M8.5 12h-3" />
            <circle cx="12" cy="3.75" r="1.5" />
            <circle cx="20.25" cy="12" r="1.5" />
            <circle cx="12" cy="20.25" r="1.5" />
            <circle cx="3.75" cy="12" r="1.5" />
        </>
    ),
    // tree-sitter output: a syntax tree.
    tree: (
        <>
            <circle cx="12" cy="4" r="2" />
            <circle cx="12" cy="12" r="2" />
            <circle cx="5.5" cy="20" r="2" />
            <circle cx="18.5" cy="20" r="2" />
            <path d="M12 6v4" />
            <path d="M10.4 13.4 7.1 18.3" />
            <path d="M13.6 13.4 16.9 18.3" />
        </>
    ),
    // Dropped tool output, pulled back into the buffer.
    restore: (
        <>
            <path d="M4 13.5V18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4.5" />
            <path d="M8 9.5 12 13.5 16 9.5" />
            <path d="M12 13.5V3.5" />
        </>
    ),
    key: (
        <>
            <circle cx="7.5" cy="16.5" r="4" />
            <path d="M10.4 13.6 20.5 3.5" />
            <path d="M16.4 7.6 18.9 10.1" />
            <path d="M13.9 10.1 15.9 12.1" />
        </>
    ),
    // Zero network calls of its own.
    offline: (
        <>
            <circle cx="12" cy="12" r="9" />
            <path d="M3.2 12h17.6" />
            <path d="M12 3c2.4 2.7 3.7 5.7 3.7 9s-1.3 6.3-3.7 9c-2.4-2.7-3.7-5.7-3.7-9S9.6 5.7 12 3Z" />
            <path d="M4.6 19.4 19.4 4.6" />
        </>
    ),
    terminal: (
        <>
            <rect x="3" y="4" width="18" height="16" rx="2" />
            <path d="M7.5 9.5 10.5 12.5 7.5 15.5" />
            <path d="M13 15.5h4" />
        </>
    ),
    'shield-check': (
        <>
            <path d="M12 21.5s7.5-3.5 7.5-9.5V5.5L12 2.5 4.5 5.5V12c0 6 7.5 9.5 7.5 9.5Z" />
            <path d="M9 11.8 11.2 14 15.2 9.8" />
        </>
    ),
    export: (
        <>
            <path d="M12 21H6.5A1.5 1.5 0 0 1 5 19.5v-15A1.5 1.5 0 0 1 6.5 3h6.8L18 7.7v3.6" />
            <path d="M13 3v5h5" />
            <path d="M14.5 17.5H21" />
            <path d="M18.5 15 21 17.5 18.5 20" />
        </>
    ),
    'report-query': (
        <>
            <path d="M4 5.5h12" />
            <path d="M4 10h12" />
            <path d="M4 14.5h6" />
            <circle cx="15" cy="16" r="3.5" />
            <path d="M17.6 18.6 20.6 21.6" />
        </>
    ),
    index: (
        <>
            <ellipse cx="12" cy="6" rx="8" ry="3" />
            <path d="M4 6v6c0 1.66 3.58 3 8 3s8-1.34 8-3V6" />
            <path d="M4 12v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6" />
        </>
    ),
    query: (
        <>
            <circle cx="10.5" cy="10.5" r="7" />
            <circle cx="10.5" cy="10.5" r="2" />
            <path d="M15.6 15.6 21 21" />
        </>
    ),
    // Recall: the loop that keeps running around what you already know.
    recall: (
        <>
            <circle cx="12" cy="12" r="2.5" />
            <path d="M12 3.6a8.4 8.4 0 0 1 8.1 6.1" />
            <path d="M12 20.4a8.4 8.4 0 0 1-8.1-6.1" />
            <path d="M15.9 10.5 20.4 10 19.6 5.6" />
            <path d="M8.1 13.5 3.6 14l.8 4.4" />
        </>
    ),
    check: <path d="M4.5 12.5 9.5 17.5 19.5 6.5" />,
    'arrow-right': (
        <>
            <path d="M4 12h15" />
            <path d="M13.5 6.5 19.5 12l-6 5.5" />
        </>
    ),
};

export default function Icon({
    name,
    className = 'w-5 h-5',
    strokeWidth = 1.5,
}: {
    name: IconName;
    className?: string;
    strokeWidth?: number;
}) {
    return (
        <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeLinejoin="round"
            className={className}
            aria-hidden="true"
            focusable="false"
        >
            {paths[name]}
        </svg>
    );
}
