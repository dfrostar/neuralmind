# The Pair — textures

Decals for building The Pair in VRoid Studio (see `../SPEC.md`). They are
build inputs, not site assets, so they live outside `site/public/`.

| File | Use |
|---|---|
| `engram-patch-2048.png`, `engram-patch-1024.png` | The hood patch: the engram on a stitched graphite tile, transparent outside it. Import as a new layer in the hoodie's texture editor and centre it on the hood's back panel. |
| `engram-cells-2048.png` | The engram's cells alone, transparent, for printing straight onto a dark part (a sleeve, the headphone band). |
| `palette.png` | The spec's palette as a swatch card, to keep open beside VRoid. |
| `engram-patch.svg`, `engram-cells.svg` | Sources. The grid is the one in `site/src/components/ui/Logo.tsx`; change both together. |

The PNGs are the SVGs rendered at their sizes with a transparent background
(any SVG renderer will do, for example `rsvg-convert -w 2048 engram-patch.svg
-o engram-patch-2048.png`).
