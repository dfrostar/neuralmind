# services.html cross-links — apply AFTER PR #315 merges

`docs/services.html` ships on the marketing branch, but the pages it
should be linked *from* (`index.html`, `about.html`, `sitemap.xml`) are
rewritten wholesale by PR #315's redesign. Editing them on this branch
would guarantee merge conflicts, so the link-through edits live here as
exact paste-ready snippets. After #315 merges, rebase this branch onto
main and apply the five edits below (then delete this file).

## 1. index.html — nav link

In the `#navlinks` div, insert after the Quickstart link:

```html
            <a href="services.html">Services</a>
```

Resulting order: How it works · Proof · Compare · Quickstart ·
**Services** · Docs · About · GitHub.

## 2. index.html — #enterprise link-through card

Append as the fifth card inside `#enterprise .cards` (the `doc-card`
class gives the green heading + ↗ suffix used for outbound cards):

```html
            <a class="card doc-card" href="services.html">
                <h3>Hands-on help</h3>
                <p>Guided rollouts, team-memory onboarding, benchmark-your-repo reports, and compliance review — engagements from the maintainer, scoped individually.</p>
            </a>
```

## 3. index.html — footer link

In `.foot-links`, insert after the Benchmarks link:

```html
            <a href="services.html">Services</a>
```

## 4. about.html — nav link

Same nav treatment as index.html: insert
`<a href="services.html">Services</a>` immediately before the
`<a href="about.html">About</a>` entry (line ~77 on the #315 version).

## 5. sitemap.xml — new URL

Insert after the `about.html` entry:

```xml
  <url>
    <loc>https://dfrostar.github.io/neuralmind/services.html</loc>
    <lastmod>2026-07-09</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
```

(Bump `lastmod` to the actual apply date.)
