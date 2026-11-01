/** @type {import('tailwindcss').Config} */

/**
 * Design tokens.
 *
 * The site wears Hallmark's Console material (github.com/nutlope/hallmark,
 * MIT) in a colourway of its own, "NeuralMind graphite". Console is a public
 * theme, so the material alone would make this one of many pages that look
 * alike; what is ours is the colourway, the mark and the record the hero
 * draws from the committed benchmark run (site/DESIGN.md says which is which).
 *
 * The legacy names (`carbon*`, `electric*`, `proton`, `iris`) are kept because
 * 300+ usages across 25 files reference them; repointing the values here
 * restyles every page at once instead of touching each one. What they mean
 * now:
 *
 * - `carbon*` is graphite in three lightness steps: the ground, a panel one
 *   step up (`carbon-card`), and the deepest step (`carbon-raised`, kept for
 *   its name) for code, logs and wells. Nothing glows and nothing floats: a
 *   surface is a 1px rule with a step of graphite inside it.
 * - `electric` is amber, and amber means a person: the action you take (the
 *   primary button, the focus ring, a hovered link) and a deviation someone
 *   should look at. One per view.
 * - `proton` is the blue the site always had, at the lightness of its old
 *   `electric-bright`, and it now means an instrument: a number that was
 *   measured, a CI-gated or reproducible badge, the NeuralMind row in a
 *   results table. The brand keeps its blue; the blue stops meaning "click".
 * - Text has four named steps (`ink`, `body`, `muted`, `faint`), all clearing
 *   WCAG AA on every surface.
 * - `danger` / `success` are Console's bad and ok, for diffs and verdicts
 *   only. `warn` is amber: a modeled or mixed result is a deviation, and a
 *   third signal colour is exactly what the material forbids.
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
            card: '0.625rem',
            pill: '9999px',
        },
        extend: {
            colors: {
                // Graphite, three steps plus two rules. OKLCH in the comments
                // is the source; the hex is what Tailwind's opacity modifiers
                // (`bg-proton/10`) can take.
                carbon: '#0D1013', // oklch(17% 0.008 250), the ground
                'carbon-raised': '#06080B', // oklch(13.5% 0.007 250), the deepest step: code, wells
                'carbon-card': '#15191C', // oklch(21% 0.009 250), a panel
                'carbon-border': '#2D3135', // oklch(31% 0.01 250), hairlines
                'carbon-line': '#484E54', // oklch(42% 0.012 250), the selected row, outlines

                // A person: the action, the focus ring, a deviation.
                electric: '#F7B83D', // oklch(82% 0.15 80)
                'electric-bright': '#FFCC69', // oklch(87% 0.13 82), hover
                'electric-dim': '#38280A', // oklch(29% 0.05 80), fills behind amber

                // An instrument: what was measured.
                proton: '#92B3FB', // oklch(77% 0.11 265)
                'proton-dim': '#1F2B44', // oklch(29% 0.05 265)

                // Retained so stray references resolve; the `muted` value.
                iris: '#9DA2A8',

                // Text, brightest to dimmest. Contrast on carbon / carbon-card /
                // carbon-raised: ink 16.5 / 15.3 / 17.4, body 11.3 / 10.5 /
                // 11.9, muted 7.4 / 6.9 / 7.8, faint 5.5 / 5.1 / 5.7. `faint`
                // is the floor: nothing dimmer carries text.
                ink: '#ECEFF2', // oklch(95% 0.005 250)
                body: '#C3C8CC', // oklch(83% 0.008 250)
                muted: '#9DA2A8', // oklch(71% 0.01 250)
                faint: '#848A90', // oklch(63% 0.012 250)

                // Verdicts. Each clears 6.1:1 on every surface.
                danger: '#F66D67', // oklch(70% 0.17 25), bad
                warn: '#F7B83D', // amber: a deviation
                success: '#61CB7C', // oklch(76% 0.15 150), ok
            },
            fontFamily: {
                sans: ['var(--font-sans)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
                mono: ['var(--font-mono)', 'ui-monospace', 'SFMono-Regular', 'monospace'],
                // Console sets heads in the body face; the token stays for the classes that name it.
                display: ['var(--font-sans)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
            },
            // Console sets every head at one weight, 500, and never 700. Body
            // emphasis (`strong`) is 600 in globals.css.
            fontWeight: {
                semibold: '500',
                bold: '500',
            },
            // Named steps between Tailwind's own, so no page needs `text-[…]`.
            fontSize: {
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
                tighter: '-0.03em', // every display head
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
