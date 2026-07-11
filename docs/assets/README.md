# docs/assets

Static visual assets for the repository (social preview, etc.).

## `social-preview.svg` — GitHub Social Preview

The 1280 × 640 image used for GitHub's social preview card (shown on LinkedIn, Twitter/X, Slack, and other link-unfurl surfaces when the repo URL is shared).

### How to update it

Edit the SVG directly. Tweak the headline, supported tools, or palette — everything is inline, no external fonts or assets.

### How to upload it

GitHub requires a **PNG** upload (not SVG). Convert once, then drop the PNG into **Settings → General → Social preview**.

**Any of these will work:**

```bash
# librsvg (fast, good fidelity)
rsvg-convert -w 1280 -h 640 docs/assets/social-preview.svg -o social-preview.png

# Inkscape (handles any SVG feature)
inkscape docs/assets/social-preview.svg --export-type=png --export-filename=social-preview.png -w 1280 -h 640

# ImageMagick
magick -background none -density 144 docs/assets/social-preview.svg -resize 1280x640 social-preview.png

# Or just open the SVG in any browser and "Save as image"
```

### Design notes

- **Safe zone:** important content is kept inside the center 1100 × 580 region — some unfurl surfaces crop the edges.
- **Palette:** deep indigo/purple background, cyan → mint accent on the headline number, muted lavender for secondary text.
- **Typography:** Inter → Segoe UI → system-ui fallback stack. Renders fine with sans-serif fallback if Inter isn't installed locally; install Inter for the best output.
- **No external references:** fully self-contained, no network fetches at render time.
