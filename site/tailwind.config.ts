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
 */
module.exports = {
    content: [
        './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
        './src/components/**/*.{js,ts,jsx,tsx,mdx}',
        './src/app/**/*.{js,ts,jsx,tsx,mdx}',
    ],
    theme: {
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

                // Muted text that still clears WCAG AA on `carbon`. Tailwind's
                // own slate-500 and slate-600 do not, which is what the whole
                // site was using for captions, labels and legal lines.
                faint: '#7E8794',
            },
            fontFamily: {
                sans: ['var(--font-sans)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
                mono: ['var(--font-mono)', 'ui-monospace', 'SFMono-Regular', 'monospace'],
                display: ['var(--font-display)', 'var(--font-sans)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
            },
            letterSpacing: {
                tightest: '-0.045em',
                tighter: '-0.03em',
            },
            borderRadius: {
                card: '0.625rem',
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
