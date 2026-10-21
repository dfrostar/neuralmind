import fs from 'node:fs';
import path from 'node:path';

const GITHUB_URL = 'https://github.com/dfrostar/neuralmind';

export const PYPI_PROJECT_URL = 'https://pypi.org/project/neuralmind/';

// Fallback used only if the GitHub API is unreachable at build time, so pages
// still render with a sane version instead of breaking the build; the live
// value is fetched below. release-please keeps the tag current: this file is
// in release-please-config.json's extra-files, and the generic updater bumps
// the version on the line marked x-release-please-version on every release.
// There is no fallback date to go stale beside it: the date comes from the
// tag's CHANGELOG.md heading, which release-please writes in the same release
// PR (see releaseDateFromChangelog).
const FALLBACK = { tag: 'v4.18.1' }; // x-release-please-version

// "## [4.18.1](…compare/v4.18.0...v4.18.1) (2026-10-19)" → "2026-10-19".
// Returns '' when the heading isn't there (a build outside the repo, or a tag
// the changelog doesn't have yet), and callers then omit the date rather than
// show one that belongs to another release.
export function releaseDateFromChangelog(tag: string, changelog?: string): string {
    let text = changelog;
    if (text === undefined) {
        try {
            // next build runs from site/, so the repo-root changelog is one up.
            text = fs.readFileSync(path.join(process.cwd(), '..', 'CHANGELOG.md'), 'utf8');
        } catch {
            return '';
        }
    }
    // Escape every regex metacharacter, backslash included, not just the dots.
    const version = tag.replace(/^v/, '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const m = text.match(new RegExp(`^## \\[${version}\\]\\([^)]*\\) \\((\\d{4}-\\d{2}-\\d{2})\\)`, 'm'));
    return m ? m[1] : '';
}

/**
 * True when `tag` ("v4.19.0") is `min` ("4.19.0") or later. Pages use it to
 * say whether a feature on main has reached a release yet, against the latest
 * release this build read, so the site never names a version as current by
 * hand.
 */
export function tagAtLeast(tag: string, min: string): boolean {
    const parse = (v: string) => v.replace(/^v/, '').split('.').map((p) => parseInt(p, 10));
    const have = parse(tag);
    const want = parse(min);
    if (have.length < 3 || have.some(Number.isNaN)) return false;
    for (let i = 0; i < 3; i++) {
        if (have[i] !== want[i]) return have[i] > want[i];
    }
    return true;
}

export interface LatestRelease {
    tag: string; // e.g. "v1.9.1"
    version: string; // e.g. "1.9.1"
    date: string; // e.g. "2026-07-28"; '' when nothing dates this tag
    htmlUrl: string; // GitHub release page (always exists)
    pypiUrl: string; // verified at build time — never a dead link
    sbomUrl: string | null; // direct SBOM download, or null if none exists yet
}

function githubHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
        Accept: 'application/vnd.github+json',
    };
    // deploy-site.yml passes the workflow token so CI builds don't hit the
    // unauthenticated rate limit and silently render the FALLBACK version.
    if (process.env.GITHUB_TOKEN) {
        headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;
    }
    return headers;
}

// PyPI can lag GitHub (a publish-job failure once left it 3 versions behind),
// so the versioned URL is only used when that exact version really exists.
async function verifiedPypiUrl(version: string): Promise<string> {
    try {
        const res = await fetch(`https://pypi.org/pypi/neuralmind/${version}/json`);
        if (res.ok) return `https://pypi.org/project/neuralmind/${version}/`;
    } catch {
        // fall through to the project page
    }
    return PYPI_PROJECT_URL;
}

// Prefer an SBOM asset on the release itself; otherwise use the copy that
// sbom.yml commits into site/public/sbom/ (GitHub releases on this repo are
// immutable, so assets can't be attached after release-please publishes).
function sbomUrlFor(
    tag: string,
    assets: { name?: string; browser_download_url?: string }[],
): string | null {
    const asset = assets.find(
        (a) => typeof a?.name === 'string' && a.name.endsWith('.sbom.json'),
    );
    if (asset?.browser_download_url) return asset.browser_download_url;
    const served = `sbom/neuralmind-${tag}.sbom.json`;
    if (fs.existsSync(path.join(process.cwd(), 'public', served))) {
        return `/${served}`;
    }
    return null;
}

// Resolved at build time (static export). Displayed versions therefore track
// whatever release is current when the site is built — no hardcoded version
// to drift out of sync with the actual latest release. Next.js dedupes the
// fetch, so layout.tsx and security/page.tsx share one request per build.
export async function getLatestRelease(): Promise<LatestRelease> {
    let tag = FALLBACK.tag;
    let date = '';
    let htmlUrl = `${GITHUB_URL}/releases/tag/${FALLBACK.tag}`;
    let assets: { name?: string; browser_download_url?: string }[] = [];
    try {
        const res = await fetch(
            'https://api.github.com/repos/dfrostar/neuralmind/releases/latest',
            { headers: githubHeaders() },
        );
        if (!res.ok) throw new Error(`GitHub API ${res.status}`);
        const data = await res.json();
        tag = data.tag_name as string;
        date = ((data.published_at as string) ?? '').slice(0, 10);
        htmlUrl = (data.html_url as string) ?? `${GITHUB_URL}/releases/tag/${tag}`;
        if (Array.isArray(data.assets)) assets = data.assets;
    } catch {
        // keep the fallback values
    }
    // The API's published_at, else the changelog heading for the same tag, so
    // the date always belongs to the tag it is shown with.
    if (!date) date = releaseDateFromChangelog(tag);
    const version = tag.replace(/^v/, '');
    return {
        tag,
        version,
        date,
        htmlUrl,
        pypiUrl: await verifiedPypiUrl(version),
        sbomUrl: sbomUrlFor(tag, assets),
    };
}
