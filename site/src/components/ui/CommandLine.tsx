'use client';

import { useEffect, useRef, useState } from 'react';
import Icon from './Icon';

/**
 * A copy-to-clipboard install line.
 *
 * The hero previously wrapped `pip install neuralmind` inside the gradient
 * primary button — a control that looked like the page's main action but was
 * really a link to an anchor, with an unselectable code block sitting inside
 * it. Developers try to copy that string; it should behave like a string you
 * can copy.
 */
export default function CommandLine({ command }: { command: string }) {
    const [copied, setCopied] = useState(false);
    const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Clear on unmount so the reset cannot fire against a gone component.
    useEffect(
        () => () => {
            if (resetTimer.current) clearTimeout(resetTimer.current);
        },
        [],
    );

    const copy = async () => {
        try {
            await navigator.clipboard.writeText(command);
            setCopied(true);
            // Cancel the previous reset first. Without this, two clicks 800ms
            // apart leave the first timer running, and it clears the tick
            // 800ms into the second click's window instead of 1600ms.
            if (resetTimer.current) clearTimeout(resetTimer.current);
            resetTimer.current = setTimeout(() => setCopied(false), 1600);
        } catch {
            // Clipboard is unavailable over plain http and in some locked-down
            // browsers. The text is selectable either way, so fail quietly.
        }
    };

    return (
        <div className="inline-flex items-stretch rounded-lg border border-carbon-border bg-carbon-raised overflow-hidden">
            <code className="flex items-center gap-2.5 font-mono text-sm text-slate-200 px-4 py-3 select-all">
                <span className="text-faint select-none">$</span>
                {command}
            </code>
            <button
                type="button"
                onClick={copy}
                aria-label={copied ? 'Copied to clipboard' : `Copy "${command}" to clipboard`}
                className="flex items-center justify-center w-11 border-l border-carbon-border text-faint hover:text-white hover:bg-white/[0.04] transition-colors"
            >
                {copied ? (
                    <Icon name="check" className="w-4 h-4 text-proton" strokeWidth={2} />
                ) : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}
                        strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4" aria-hidden="true">
                        <rect x="9" y="9" width="12" height="12" rx="2" />
                        <path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" />
                    </svg>
                )}
            </button>
            <span aria-live="polite" className="sr-only">
                {copied ? 'Copied' : ''}
            </span>
        </div>
    );
}
