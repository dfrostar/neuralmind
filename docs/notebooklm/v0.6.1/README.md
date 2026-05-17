# NotebookLM source pack — NeuralMind v0.6.1

Three documents designed to be loaded as sources in NotebookLM (or
any similar tool) to generate a video, podcast, or audio overview
about NeuralMind v0.6.1.

## How to use

1. Open NotebookLM (or your equivalent).
2. Create a new notebook.
3. Add the three files in this directory as sources, in order:
   - `01-installs-anywhere.md`
   - `02-what-shipped.md`
   - `03-the-honest-take.md`
4. Generate a Video Overview (or Audio Overview / Podcast).
5. Optional: feed it a prompt like "make this developer-focused and
   honest about limitations" if you want to nudge the voice.

## Why three docs, in this order

The three sources are deliberately written in *different registers*
so NotebookLM has multiple angles to weave from. Same template as
the v0.6.0 pack ([`../v0.6.0/`](../v0.6.0/README.md)).

| Doc | Register | What it provides |
|---|---|---|
| `01-installs-anywhere.md` | First-person founder narrative | The conceptual arc — why the v0.6.1 release is about distribution, not features, and why that matters more than it sounds. |
| `02-what-shipped.md` | Neutral third-person technical tour | Concrete feature-by-feature breakdown of every v0.6.1 change. Each install path, the Dockerfile, the keyword bump, the deferred review-feedback patches. |
| `03-the-honest-take.md` | Mixed developer-experience + skeptic's-view | When is "five install paths" actually one too many? When does pipx beat pip beat uv? What's *not* in v0.6.1 that the install-anywhere framing might let you assume? |

Together they cover the *why*, the *what*, and the *should you*.

## What this pack is *not*

- **Not the release notes.** Those live at
  [`/RELEASE_NOTES_v0.6.1.md`](../../../RELEASE_NOTES_v0.6.1.md)
  (once cut) and exist for humans skimming changelogs.
- **Not the LinkedIn drafts.** Those live at
  [`/docs/LINKEDIN-POST-DRAFT.md`](../../LINKEDIN-POST-DRAFT.md)
  and are shorter, posty, with hashtags.
- **Not the screencast script.** That lives at
  [`/docs/SCREENCAST-v0.6.1.md`](../../SCREENCAST-v0.6.1.md) and is
  a beat-by-beat narration script for a 60-second demo.

## Editing notes

- Keep prose narratable. Don't add tables, dense code blocks, or
  bullet lists past a sentence or two.
- The three docs deliberately overlap a little. Don't dedupe.
- If you change product positioning, update all three.
- **Don't oversell.** v0.6.1 adds install paths, not features.
  Calling it a "major release" or a "new chapter" is the trap to
  avoid — it makes the v0.7 release ("Always-On") harder to land
  later. Frame v0.6.1 as a clean, small, distribution-focused
  patch.

## Suggested prompts for NotebookLM

After loading the sources, try one of these:

- **For a developer-honest video (default):**
  > "Make a 4-minute video overview targeted at experienced
  > developers. Focus on the install-method choice — when does pipx
  > beat pip, when does uv matter, when is Docker worth it. Stay
  > honest about what v0.6.1 doesn't add."

- **For a shorter distribution-pitch video:**
  > "3-minute video. Lead with the five install paths. End on the
  > screencast image: two terminals, two install paths, same canvas
  > pulsing. Frame as 'install anywhere'."

- **For a Python-tooling-fans audience:**
  > "4-minute video. Heavy on the pipx/uv/Docker tradeoffs. Treat
  > the audience as people with strong opinions about how they
  > install Python applications. The v0.6.1 release is for them."

## Re-using outside NotebookLM

Plain markdown, works as sources for any AI content tool.
