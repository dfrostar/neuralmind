const GITHUB_URL = 'https://github.com/dfrostar/neuralmind';

// Fallback used only if the GitHub API is unreachable at build time, so pages
// still render with a sane version instead of breaking the build. Keep this
// pointed at the newest known release; the live value is fetched below.
const FALLBACK = { tag: 'v1.3.0', date: '2026-07-20' };

export interface LatestRelease {
    tag: string;
    date: string;
    htmlUrl: string;
}

// Resolved at build time (static export). The displayed version therefore
// tracks whatever release is current when the site is built — no hardcoded
// version to drift out of sync with the actual latest release.
export async function getLatestRelease(): Promise<LatestRelease> {
    try {
        const res = await fetch(
            'https://api.github.com/repos/dfrostar/neuralmind/releases/latest',
            { headers: { Accept: 'application/vnd.github+json' } },
        );
        if (!res.ok) throw new Error(`GitHub API ${res.status}`);
        const data = await res.json();
        return {
            tag: data.tag_name as string,
            date: ((data.published_at as string) ?? '').slice(0, 10) || FALLBACK.date,
            htmlUrl: (data.html_url as string) ?? `${GITHUB_URL}/releases/tag/${data.tag_name}`,
        };
    } catch {
        return {
            tag: FALLBACK.tag,
            date: FALLBACK.date,
            htmlUrl: `${GITHUB_URL}/releases/tag/${FALLBACK.tag}`,
        };
    }
}
