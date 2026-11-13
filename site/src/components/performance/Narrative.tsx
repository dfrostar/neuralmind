import type { WorkItem } from '@/lib/record';

/**
 * The narrative's published blocks. Block A is a small Markdown subset —
 * paragraphs, `- ` lists, `code`, **bold**, and links to https:// or a site
 * path — rendered as React elements, never as HTML, so a narrative can't
 * inject markup. Anything else in it prints as text.
 */
const INLINE_RE = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\[[^\]]+\]\([^)\s]+\))/g;
const LINK_RE = /^\[([^\]]+)\]\(([^)\s]+)\)$/;

function inline(text: string): React.ReactNode[] {
    const out: React.ReactNode[] = [];
    let last = 0;
    for (const m of text.matchAll(INLINE_RE)) {
        const token = m[0];
        const at = m.index ?? 0;
        if (at > last) out.push(text.slice(last, at));
        const key = `${at}`;
        if (token.startsWith('`')) {
            out.push(
                <code key={key} className="text-ink bg-carbon-raised px-1.5 py-0.5 rounded-control text-sm">
                    {token.slice(1, -1)}
                </code>,
            );
        } else if (token.startsWith('**')) {
            out.push(
                <strong key={key} className="text-ink font-semibold">
                    {token.slice(2, -2)}
                </strong>,
            );
        } else {
            const [, label, href] = LINK_RE.exec(token)!;
            out.push(
                /^(https:\/\/|\/)/.test(href) ? (
                    <a key={key} href={href} className="link">
                        {label}
                    </a>
                ) : (
                    label
                ),
            );
        }
        last = at + token.length;
    }
    if (last < text.length) out.push(text.slice(last));
    return out;
}

export function Prose({ markdown }: { markdown: string }) {
    const blocks = markdown.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
    return (
        <div className="space-y-4 text-body leading-relaxed">
            {blocks.map((block, i) => {
                const lines = block.split('\n');
                if (lines.every((l) => l.startsWith('- '))) {
                    return (
                        <ul key={i} className="list-disc pl-5 space-y-1.5 marker:text-faint">
                            {lines.map((l, j) => (
                                <li key={j}>{inline(l.slice(2).trim())}</li>
                            ))}
                        </ul>
                    );
                }
                return <p key={i}>{inline(lines.map((l) => l.trim()).join(' '))}</p>;
            })}
        </div>
    );
}

const TAGS: Record<WorkItem['tag'], { label: string; tone: string }> = {
    moved: { label: 'Moved', tone: 'border-success/30 text-success' },
    stalled: { label: 'Stalled', tone: 'border-warn/30 text-warn' },
};

/** Block C: areas for improvement, each tagged moved or stalled. */
export function WorkingOn({ items }: { items: WorkItem[] }) {
    return (
        <ul className="divide-y divide-carbon-border border-y border-carbon-border">
            {items.map((item, i) => (
                <li key={i} className="flex items-start gap-4 py-4" data-tag={item.tag}>
                    <span
                        className={`shrink-0 inline-flex justify-center w-20 px-2 py-0.5 rounded-control border text-xs font-medium ${TAGS[item.tag].tone}`}
                    >
                        {TAGS[item.tag].label}
                    </span>
                    <span className="text-body text-sm leading-relaxed">{inline(item.text)}</span>
                </li>
            ))}
        </ul>
    );
}
