# The Pair — mascot build spec (VRoid Studio 2.14)

The Pair is NeuralMind's mascot: the pair programmer who sits in the corner
of your editor and remembers what you'd otherwise explain twice. Short, in an
oversized hoodie with the engram on the hood, headphones on. Upbeat,
curious, helpful. Its one line is **"Want me to remember that?"**

This file is the whole brief. A person can build from it, and so can a
computer-use agent driving VRoid Studio (see [Running it with an
agent](#running-it-with-an-agent)). Every colour is a site token from
`site/tailwind.config.ts`, so the character and the site are one palette.

## Who it is

| | |
|---|---|
| Role | The pair programmer. Not a guru, not a robot: a colleague who was paying attention. |
| Silhouette | Short, big hood, headphones. Recognisable as a shape in solid black at 64px. |
| Voice | Short sentences, first person, offers rather than announces. "Want me to remember that?" "That's in `auth.py`, line 40." Never "I'm an AI". |
| Signature | The hood: the 4×4 engram patch on its back panel, the same grid as the logo. |
| What it isn't | A chat widget, a sexualised avatar, a brain with a face, a robot. |

## Palette

Colour meanings follow the site: **amber is a person** (the eyes, the
drawstrings, the learned edge on the patch), **blue is an instrument** (the
headphone LEDs, and nothing else), graphite for everything else.

| Part | Hex | Token | Note |
|---|---|---|---|
| Hair | `#ECEFF2` | `ink` | Silver-white. The mark's two "file" columns are this colour. Shade `#C3C8CC` (`body`). |
| Iris | `#F7B83D` | `electric` | Amber. Pupil `#1C0E00`. Keep the highlights large and white. |
| Hoodie | `#484E54` | `carbon-line` | Light enough to separate from the site's `#0D1013` ground. Shade `#2D3135`. |
| Hoodie lining, cuffs | `#2D3135` | `carbon-border` | |
| Drawstrings | `#F7B83D` | `electric` | Aglets `#FFCC69` (`electric-bright`). |
| Hood patch | from `textures/` | | Graphite tile `#15191C`, ink cells, amber diagonal. Import, don't redraw. |
| Headphone shells | `#15191C` | `carbon-card` | Cushions `#2D3135`. |
| Headphone LEDs | `#92B3FB` | `proton` | The only blue on the character. Small. |
| Trousers | `#15191C` | `carbon-card` | Straight, a little long. |
| Shoes | `#2D3135` | `carbon-border` | Soles `#ECEFF2`. No amber on the shoes. |
| Skin | VRoid default | | Don't push it toward grey to match the palette. |

`textures/palette.png` is this table as a swatch card, to keep open beside
VRoid.

## Build, section by section

VRoid Studio 2.14's labels may differ from the ones here; the sections are
its stable ones (Face, Hairstyle, Body, Outfit, Accessories, Look). Where a
step names a value, type it into the slider's number field or the colour
picker's hex field rather than dragging.

### 0. Start

1. New model, the base closest to a young adult with a short build.
2. Save as `the-pair-00-base.vroid`.

### 1. Face

1. Pick a face preset with a soft, open expression (round eyes, small mouth).
2. Eyes: slightly larger than default, iris `#F7B83D`, pupil `#1C0E00`,
   highlights white and large. No coloured eyeshadow.
3. Brows: soft, slightly raised at the inner ends (curious, not surprised).
4. Leave makeup and face paint off.
5. Check the expression set is intact (blink, happy, surprised and the
   vowels). The site uses blink and happy.
6. Save as `the-pair-01-face.vroid`. **Checkpoint: face.**

### 2. Hairstyle

1. Start from a short, slightly messy preset: chin length at most, fringe
   above the eyes so the amber reads.
2. Hair colour `#ECEFF2`, shade `#C3C8CC`, no gradient, no second colour.
3. Leave a little hair over the headphone band, so the headphones sit in it
   rather than on top of it.
4. Spring bones: modest stiffness, so the hair moves when the head turns but
   doesn't swing.
5. Save as `the-pair-02-hair.vroid`.

### 3. Body

1. Height: short of the slider's midpoint. Head a step larger than default:
   friendly proportions, not chibi.
2. Build: slight, neutral. Nothing exaggerated.
3. Save as `the-pair-03-body.vroid`. **Checkpoint: silhouette.** Hide the
   textures (or view as a silhouette) and check that the hood and headphones
   make the shape.

### 4. Outfit

1. Top: the largest, longest-sleeved hooded top VRoid offers, sleeves past
   the wrists. If no preset has a hood, take the closest long-sleeve top and
   see [If a part isn't in VRoid](#if-a-part-isnt-in-vroid).
2. Hoodie `#484E54`, shade `#2D3135`, lining and cuffs `#2D3135`.
3. Drawstrings `#F7B83D`, aglets `#FFCC69`.
4. Hood patch: open the hoodie's texture editor, import
   `textures/engram-patch-2048.png` as a new layer, and place it centred on
   the hood's back panel, about a third of the hood's width. Keep it square;
   don't stretch it to the UV.
5. Trousers `#15191C`; shoes `#2D3135` with `#ECEFF2` soles.
6. Save as `the-pair-04-outfit.vroid`. **Checkpoint: outfit.**

### 5. Accessories: headphones

1. Over-ear headphones worn on the head, band over the crown.
2. Shells `#15191C`, cushions `#2D3135`, one small LED dot per shell
   `#92B3FB`. If the material has an emission colour, put the blue there at
   low strength. A glow halo is off-brand.
3. Save as `the-pair-05-headphones.vroid`.

### 6. Look and export

1. Look: keep the rim light subtle. The site's ground is near-black, so a
   faint cool rim helps the silhouette; a bright one makes it a sticker.
2. Export as **VRM 1.0**.
   - Reduce polygons to keep the file small (aim for roughly 20–40k
     triangles).
   - Texture atlas at **1024** (2048 only if the patch blurs).
   - Merge materials where VRoid offers it; delete transparent meshes.
   - **Budget: under 8 MB.** The site lazy-loads it, and Cloudflare Pages
     refuses any file over 25 MiB.
3. Avatar info, which the VRM file carries to anyone who downloads it from
   the site:

   | Field | Value |
   |---|---|
   | Name | The Pair |
   | Version | 1.0 |
   | Author | NeuralMind (Cheval-Volant LLC) |
   | Contact | hello@neuralmind.uk |
   | Avatar use | Only the author |
   | Violent / sexual / political-religious use | Not allowed |
   | Commercial use | Corporation (allowed for the author) |
   | Redistribution | Not allowed |
   | Modification | Not allowed |
   | Credit | Required |

4. Save the export as `pair.vrm`, and keep the last `.vroid` too.

## Hand it over

- `pair.vrm` goes in **`site/public/mascot/pair.vrm`**. The homepage shows
  The Pair beside the hero's record as soon as that file exists, with no code
  change needed; without it, the site renders exactly as before.
- Commit the final `.vroid` beside this file as `site/mascot/the-pair.vroid`,
  so the source is kept.
- Optional: a transparent PNG still (front, chest up, 1024×1024) at
  `site/public/mascot/pair.png`, shown while the 3D model loads.

## If a part isn't in VRoid

VRoid's presets change between versions, so a hood or headphones may not be
there as such. In order of preference:

1. **Build it from VRoid's own tools.** Hair guides can model solid shapes,
   which is how VRoid users make hoods and headphones. It's slower, but
   everything stays in the `.vroid` and needs no licence.
2. **A BOOTH asset**, only if its terms allow **corporate** commercial use.
   That's a separate permission from individual use. Save the listing's terms
   page beside the `.vroid` as `site/mascot/licences/<asset>.pdf` or `.md`.
   Don't buy anything without asking.
3. **Finish it in Blender** with the VRM add-on, and re-export VRM 1.0.

VRoid's own preset parts are pixiv's. Before the mascot goes on the site,
read the current VRoid Studio terms for commercial and corporate use of
models made with presets, and note the date you checked here:

> Terms checked: _not yet_

## Running it with an agent

VRoid Studio has no scripting API, so automation means a computer-use agent
(Hermes, for one) operating the app's GUI on the machine where it's
installed. It is good at the deterministic steps above: presets, typed
values, hex colours, importing the patch, the export dialog. It is weak at
freehand work and taste. Run it like this:

- **Supervised, on a desktop with only VRoid open.** It controls your real
  mouse and keyboard.
- **One section per run**, starting from the previous section's `.vroid`. If
  a step goes wrong, reopen the last save rather than undoing piecemeal.
- **Stop at every checkpoint** (face, silhouette, outfit), take a screenshot
  of the 3D view and wait for a person to say go.
- **Never** buy assets, sign in, upload to VRoid Hub or change VRoid's
  settings. If a part isn't in VRoid, stop and report.
- **Type values, don't drag:** slider number fields and the hex field of the
  colour picker.
- At the end, report the export dialog's final settings and the file size of
  `pair.vrm`.

A prompt to start it with:

> Open VRoid Studio and follow `site/mascot/SPEC.md` from section 0, one
> section at a time. Save the `.vroid` named in each section before moving
> on. Stop at each **Checkpoint**, take a screenshot of the 3D view, and wait
> for my go. Type every value; don't drag sliders. Don't buy, sign in or
> upload anything. If a part the spec asks for isn't in VRoid, stop and tell
> me what's there instead.
