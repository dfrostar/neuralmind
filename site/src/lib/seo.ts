import type { Metadata } from 'next';

/** Absolute site origin. Mirrors `metadataBase` in the root layout. */
export const SITE_URL = 'https://neuralmind.uk';

/**
 * The shared social card. Every page keeps it — a page that declares its own
 * `openGraph` without this drops `og:image` entirely (see `pageMetadata`).
 */
const OG_IMAGE = {
    url: '/social-preview.png',
    width: 1200,
    height: 630,
    alt: 'NeuralMind — Code Memory for AI Coding Agents',
};

export type PageSeo = {
    /**
     * Route path, e.g. `/pricing`. Normalized to a trailing slash so the
     * canonical matches the URL actually served (`trailingSlash: true`).
     */
    path: string;
    title: string;
    description: string;
    keywords?: string[];
    /** Default to `title` / `description` when omitted. */
    ogTitle?: string;
    ogDescription?: string;
    type?: 'website' | 'article';
    publishedTime?: string;
    modifiedTime?: string;
    tags?: string[];
    imageAlt?: string;
};

/**
 * Build a page's metadata with a self-referencing canonical and a complete
 * Open Graph block.
 *
 * Next.js merges metadata shallowly, one top-level key at a time, and the site
 * had been bitten in both directions at once:
 *
 * - A page that *omits* `alternates` inherits the root layout's object whole.
 *   Six pages were emitting `rel=canonical` pointing at the homepage, so
 *   `/pricing/` and `/effectiveness/` told Google they were duplicates of `/`
 *   while the sitemap submitted them at priority 0.8.
 * - A page that *sets* `openGraph` replaces the root's entirely. All six
 *   `/publications/*` pages had lost `og:image` and shared as bare links.
 *
 * Routing every page through here makes both impossible to get wrong by
 * omission. `tests/test_site_seo.py` gates the built HTML so it stays that way.
 */
export function pageMetadata({
    path,
    title,
    description,
    keywords,
    ogTitle,
    ogDescription,
    type = 'website',
    publishedTime,
    modifiedTime,
    tags,
    imageAlt,
}: PageSeo): Metadata {
    const canonical = path.endsWith('/') ? path : `${path}/`;
    const image = imageAlt ? { ...OG_IMAGE, alt: imageAlt } : OG_IMAGE;

    return {
        title,
        description,
        ...(keywords ? { keywords } : {}),
        alternates: { canonical },
        openGraph: {
            title: ogTitle ?? title,
            description: ogDescription ?? description,
            url: `${SITE_URL}${canonical}`,
            siteName: 'NeuralMind',
            locale: 'en_US',
            type,
            ...(publishedTime ? { publishedTime } : {}),
            ...(modifiedTime ? { modifiedTime } : {}),
            ...(tags ? { tags } : {}),
            images: [image],
        },
        twitter: {
            card: 'summary_large_image',
            title: ogTitle ?? title,
            description: ogDescription ?? description,
            images: [`${SITE_URL}${image.url}`],
        },
    };
}
