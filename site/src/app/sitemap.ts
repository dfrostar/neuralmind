import { execFileSync } from 'node:child_process';
import { readdirSync } from 'node:fs';
import path from 'node:path';
import type { MetadataRoute } from 'next';
import { SITE_URL } from '@/lib/seo';

// `output: 'export'` requires the sitemap route to be statically evaluated;
// it reads the filesystem and git at build time, so pin it explicitly.
export const dynamic = 'force-static';

const APP_DIR = path.join(process.cwd(), 'src', 'app');

/**
 * Every static route, discovered from the route tree rather than listed by
 * hand. The previous `public/sitemap.xml` was hand-maintained and had drifted
 * three ways: `/team/` was missing entirely, the `/publications/*` entries
 * omitted the trailing slash the pages actually canonicalize to, and `lastmod`
 * had gone stale. Deriving the list means a new page cannot be forgotten.
 */
function routes(dir = APP_DIR, prefix = ''): string[] {
    const found: string[] = [];
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
        if (!entry.isDirectory()) {
            // `trailingSlash: true`, so every route ends in a slash.
            if (entry.name === 'page.tsx') found.push(`${prefix || ''}/`);
            continue;
        }
        // Skip Next.js private/dynamic conventions — this site has none today,
        // but a `[slug]` or `_component` directory must never become a URL.
        if (/^[[(_@]/.test(entry.name)) continue;
        found.push(...routes(path.join(dir, entry.name), `${prefix}/${entry.name}`));
    }
    return found;
}

/**
 * Last commit date for a route's page file, so `lastmod` reflects the content
 * rather than the build clock. Falls back to build time outside a git checkout.
 */
function lastModified(route: string): Date {
    const file = path.join(APP_DIR, route === '/' ? '' : route, 'page.tsx');
    try {
        const iso = execFileSync('git', ['log', '-1', '--format=%cI', '--', file], {
            encoding: 'utf8',
            stdio: ['ignore', 'pipe', 'ignore'],
        }).trim();
        if (iso) return new Date(iso);
    } catch {
        // Not a git checkout (or git unavailable) — fall through.
    }
    return new Date();
}

/** Commercial and evidence pages lead; policy pages trail. */
function priority(route: string): number {
    if (route === '/') return 1.0;
    if (['/privacy/', '/terms/'].includes(route)) return 0.5;
    if (route.startsWith('/publications/') || route.startsWith('/field-reports/')) return 0.8;
    return 0.8;
}

export default function sitemap(): MetadataRoute.Sitemap {
    return routes()
        .sort()
        .map((route) => ({
            url: `${SITE_URL}${route}`,
            lastModified: lastModified(route),
            priority: priority(route),
        }));
}
