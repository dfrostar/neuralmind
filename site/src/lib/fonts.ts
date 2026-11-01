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
import { Atkinson_Hyperlegible_Mono, Host_Grotesk } from 'next/font/google';

/**
 * Host Grotesk for everything a person reads, heads included: Console sets
 * one face at two weights (400 body, 500 heads) rather than pairing a display
 * face with a text face, so a head reads as the same voice, calmer and larger.
 */
export const sans = Host_Grotesk({
    subsets: ['latin'],
    display: 'swap',
    variable: '--font-sans',
});

/**
 * Atkinson Hyperlegible Mono for what an instrument wrote: a measured figure,
 * a command, a path, a version, a sha. Its slashed zero and tailed one are the
 * point. Never a label, a head or a button.
 */
export const mono = Atkinson_Hyperlegible_Mono({
    subsets: ['latin'],
    display: 'swap',
    variable: '--font-mono',
});

/** `font-display` resolves to the same face; the token stays so 130 heads keep their class. */
export const fontVariables = `${sans.variable} ${mono.variable}`;
