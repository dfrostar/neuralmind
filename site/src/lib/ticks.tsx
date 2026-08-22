/**
 * Renders the backtick spans that the copy has always contained.
 *
 * Strings like '`neuralmind init-hook .` keeps it current' were being printed
 * verbatim, backticks and all, on the homepage — the page was showing its own
 * markdown source. This splits on the ticks and styles the code spans, so the
 * copy stays byte-identical in source (which `tests/test_site_claims.py`
 * scans) while rendering the way it was written to read.
 *
 * The span must be allowed to wrap. `pip install neuralmind && neuralmind
 * wakeup .` is 46 characters and does not fit a three-column grid cell; held
 * on one line it ran straight through the cell border and over the next
 * column's prose.
 */
import { Fragment } from 'react';

export function withCode(text: string) {
    const parts = text.split('`');
    return parts.map((part, i) =>
        i % 2 === 1 ? (
            <code
                key={i}
                className="font-mono text-[0.9em] text-electric-bright bg-electric/[0.07] rounded px-1 py-0.5 break-words"
            >
                {part}
            </code>
        ) : (
            <Fragment key={i}>{part}</Fragment>
        ),
    );
}
