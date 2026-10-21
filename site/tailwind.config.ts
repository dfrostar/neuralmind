/** @type {import('tailwindcss').Config} */

/**
 * Design tokens.
 *
 * The legacy names (`carbon*`, `electric*`, `proton`, `iris`) are kept because
 * 200+ usages across 25 files reference them; repointing the values here
 * restyles every page at once instead of touching each one. What changed is
 * what they mean:
 *
 * - `carbon*` lost its navy cast. The old #070b15 was a blue-black, which is
 *   what put the whole site on the same footing as every dark SaaS template.
 *   These are true neutrals, so the one accent is the only chromatic thing on
 *   the page and therefore actually reads as an accent.
 * - `electric` is the single interactive colour: links, focus rings, the
 *   primary action. It is no longer Tailwind's own blue-500 (#3b82f6), which
 *   is the most default colour on the web.
 * - `proton` stopped being the purple half of a blue→purple→pink gradient and
 *   became the evidence colour — verified, measured, CI-gated. Blue means
 *   "you can click this", green means "this was measured". Two colours with
 *   two jobs, which is a system; six colours with no jobs is a mood board.
 * - Text has four named steps (`ink`, `body`, `muted`, `faint`) instead of
 *   Tailwind's slate scale, whose blue cast fought the neutral surfaces.
 * - `danger` / `warn` / `success` are verdict colours for tables of claims
 *   (refuted / modeled / passing). They are not evidence: a result that was
 *   measured is `proton`, never `success`.
 *
 * Type, radius and colour are closed sets: `tests/test_site_design_tokens.py`
 * fails on arbitrary type values, raw palette colours and radii outside
 * `control` / `card` / `pill`. site/DESIGN.md says which to use where.
 */
module.exports = {
    content: [
        './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
        './src/components/**/*.{js,ts,jsx,tsx,mdx}',
        './src/app/**/*.{js,ts,jsx,tsx,mdx}',
    ],
    theme: {
        // Replaces Tailwind's eight radii rather than extending them: three
        // jobs, three values. `control` for anything you click or that sits
        // inline in text, `card` for a surface, `pill` for dots and tags.
        borderRadius: {
            none: '0',
            control: '0.375rem',
            card: '0.75rem',
            pill: '9999px',
        },
        extend: {
            colors: {
                // Surfaces — neutral, four steps, each a real elevation.
                carbon: '#0A0B0D',
                'carbon-raised': '#0F1114',
                'carbon-card': '#131518',
                'carbon-border': '#22262C',
                'carbon-line': '#2E333B',

                // Interactive.
                electric: '#5B8CFF',
                'electric-bright': '#93B4FF',
                'electric-dim': '#1B2742',

                // Evidence / measured.
                proton: '#4FD1A5',
                'proton-dim': '#16302A',

                // Retained so stray references resolve; deliberately near-neutral.
                iris: '#8A93A3',

                // Text, brightest to dimmest. Contrast on `carbon` / `carbon-card`
                // (WCAG AA body text needs 4.5): ink 16.3 / 15.2, body 12.5 /
                // 11.6, muted 7.7 / 7.2, faint 5.4 / 5.0. `faint` is the floor:
                // Tailwind's slate-500 and slate-600 do not clear AA, which is
                // what the site was using for captions, labels and legal lines.
                ink: '#E8EAED',
                body: '#C9CED6',
                muted: '#9AA3AF',
                faint: '#7E8794',

                // Verdicts. Each clears 6.6:1 on every surface.
                danger: '#F27B7B',
                warn: '#E5B567',
                success: '#6CCB86',
            },
            fontFamily: {
                sans: ['var(--font-sans)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
                mono: ['var(--font-mono)', 'ui-monospace', 'SFMono-Regular', 'monospace'],
                display: ['var(--font-display)', 'var(--font-sans)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
            },
            // Named steps between Tailwind's own, so no page needs `text-[…]`.
            fontSize: {
                eyebrow: ['0.6875rem', { lineHeight: '1rem' }], // uppercase mono labels, table heads
                caption: ['0.8125rem', { lineHeight: '1.25rem' }], // table cells, terminal text, small print
                'body-sm': ['0.9375rem', { lineHeight: '1.5rem' }], // card ledes, mobile nav
                'title-sm': ['1.0625rem', { lineHeight: '1.5rem' }], // card titles, wordmark
                stat: ['1.75rem', { lineHeight: '1' }], // a measured number in a Stat
                display: ['2.75rem', { lineHeight: '1.05' }], // page h1, section h2
                hero: ['3.5rem', { lineHeight: '1.05' }], // the homepage h1 only
                'code-inline': '0.875em', // <code> inside running text; relative to it
            },
            lineHeight: {
                display: '1.05',
            },
            letterSpacing: {
                tightest: '-0.045em',
                tighter: '-0.03em',
                eyebrow: '0.14em',
            },
            animation: {
                'fade-in': 'fadeIn 0.5s ease-out both',
                'fade-up': 'fadeUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) both',
                'tag-roll': 'tagRoll 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
            },
            keyframes: {
                fadeIn: {
                    '0%': { opacity: '0' },
                    '100%': { opacity: '1' },
                },
                fadeUp: {
                    '0%': { opacity: '0', transform: 'translateY(10px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' },
                },
                tagRoll: {
                    '0%': { opacity: '0', transform: 'translateY(8px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' },
                },
            },
        },
    },
    plugins: [],
};
