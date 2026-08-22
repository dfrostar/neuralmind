/**
 * Webfonts, actually loaded.
 *
 * The site declared `Inter`, `JetBrains Mono` and `Fraunces` in
 * `tailwind.config.ts` but never loaded a single one, so every `font-display`
 * heading — 113 of them across 25 files, including the hero and the logo —
 * fell through to the generic `serif` fallback and rendered in Times New
 * Roman. That one missing link is most of what made the site read as a
 * template.
 *
 * `next/font` downloads and self-hosts at build time, so the static export
 * ships the woff2 files itself: no runtime request to fonts.gstatic.com, no
 * third-party connection for a privacy page to have to explain, and no FOUT
 * beyond the `swap` window.
 */
import { Inter, Inter_Tight, JetBrains_Mono } from 'next/font/google';

/** UI and body copy. */
export const sans = Inter({
    subsets: ['latin'],
    display: 'swap',
    variable: '--font-sans',
});

/**
 * Headlines. Inter Tight is the same voice as the body at display size —
 * tighter apertures, less sidebearing — so headings read dense and
 * deliberate instead of introducing a second, unrelated typeface.
 */
export const display = Inter_Tight({
    subsets: ['latin'],
    display: 'swap',
    variable: '--font-display',
});

/** Code, CLI invocations, and every measured figure. */
export const mono = JetBrains_Mono({
    subsets: ['latin'],
    display: 'swap',
    variable: '--font-mono',
});

export const fontVariables = `${sans.variable} ${display.variable} ${mono.variable}`;
