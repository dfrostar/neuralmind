import fs from 'node:fs';
import path from 'node:path';

export const GITHUB_URL = 'https://github.com/dfrostar/neuralmind';
export const PYPI_PROJECT_URL = 'https://pypi.org/project/neuralmind/';

// Fallback used only if the GitHub API is unreachable at build time, so the
// page still renders with a sane version instead of breaking the build. Keep
// this pointed at the newest known release; the live value is fetched below.
const FALLBACK = { tag: 'v1.3.0', date: '2026-07-20' };

export interface LatestRelease {
    tag: string; // e.g. "v1.3.0"
    version: string; // e.g. "1.3.0"
    date: string; // e.g. "2026-07-20"
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

// PyPI can lag GitHub (a publish job failure once left it 3 versions behind),
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
function sbomUrlFor(tag: string, assets: { name?: string; browser_download_url?: string }[]): string | null {
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
    let date = FALLBACK.date;
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
        date = ((data.published_at as string) ?? '').slice(0, 10) || FALLBACK.date;
        htmlUrl = (data.html_url as string) ?? `${GITHUB_URL}/releases/tag/${tag}`;
        if (Array.isArray(data.assets)) assets = data.assets;
    } catch {
        // keep the fallback values
    }
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
