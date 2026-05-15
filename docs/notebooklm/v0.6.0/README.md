# NotebookLM source pack — NeuralMind v0.6.0

These three documents are designed to be loaded as sources in
NotebookLM (or any similar tool — opennotebooklm, etc.) to
generate a video, podcast, or audio overview about NeuralMind
v0.6.0.

## How to use

1. Open NotebookLM (or your equivalent).
2. Create a new notebook.
3. Add the three files in this directory as sources, in order:
   - `01-the-origin-story.md`
   - `02-what-shipped.md`
   - `03-the-numbers-and-the-honest-take.md`
4. Generate a Video Overview (or Audio Overview / Podcast).
5. Optional: feed it a prompt like "make this developer-focused
   and honest about limitations" if you want to nudge the voice.

## Why three docs, in this order

The three sources are deliberately written in *different
registers* so NotebookLM has multiple angles to weave from:

| Doc | Register | What it provides |
|---|---|---|
| `01-the-origin-story.md` | First-person founder narrative | The conceptual arc — why retrieval, why a synapse layer, why a visible brain. Emotional beats and the "hippocampus you can watch learn" framing. |
| `02-what-shipped.md` | Neutral third-person technical tour | Concrete feature-by-feature breakdown of every v0.6.0 change. Specs, behavior, env vars, compatibility notes. |
| `03-the-numbers-and-the-honest-take.md` | Mixed developer-experience + skeptic's-view | A day-in-the-life walkthrough, the measurable claims with honest caveats, the "when to skip this" section. |

Together they cover the *why*, the *what*, and the *should you*.
Each is self-contained, plain prose (not bullet-heavy), and
narratable as continuous text.

## What this pack is *not*

- **Not the release notes.** Those live at
  [`/RELEASE_NOTES_v0.6.0.md`](../../../RELEASE_NOTES_v0.6.0.md)
  and exist for humans skimming changelogs, not AI narration.
- **Not the LinkedIn drafts.** Those live at
  [`/docs/LINKEDIN-POST-DRAFT.md`](../../LINKEDIN-POST-DRAFT.md)
  and are shorter, posty, with hashtags.
- **Not the screencast script.** That lives at
  [`/docs/SCREENCAST-v0.6.0.md`](../../SCREENCAST-v0.6.0.md) and
  is a beat-by-beat narration script for a 60-second demo recorded
  in person against a real terminal.

These NotebookLM sources are the *long-form prose* pack
specifically optimized for AI hosts to digest into conversational
output.

## Editing notes

- Keep prose narratable. Don't add tables, dense code blocks, or
  bullet lists past a sentence or two — they trip up generative
  audio.
- The three docs deliberately overlap a little (e.g. all three
  mention the live activity feed). That redundancy gives NotebookLM
  multiple phrasings to mix; don't dedupe.
- If you change product positioning, update all three. The
  registers are different but the *claims* must stay consistent.
- New major release? Copy this directory to
  `docs/notebooklm/v0.X.0/`, update the three docs, and you have a
  fresh source pack.

## Suggested prompts for NotebookLM

After loading the sources, try one of these to steer the output:

- **For a developer-honest video (default):**
  > "Make a 5-minute video overview targeted at experienced
  > developers. Honest about limitations. No marketing
  > superlatives. Include the day-in-the-life walkthrough and at
  > least one concrete number with the caveat about end-to-end
  > versus retrieval-stage reduction."

- **For a shorter cost-pitch video:**
  > "3-minute video. Focus on the cost reduction angle. Lead
  > with the bill-going-from-450-to-7 example. End on the
  > graph-view debugging story."

- **For a conceptual / "why" video:**
  > "5-7 minute video. Story-driven. Lead with the founder origin,
  > the hippocampus / cortex analogy, the moment the pitch flipped
  > with v0.6.0. Light on feature specs, heavy on the conceptual
  > leap."

## Re-using outside NotebookLM

These files are plain markdown and work as sources for any
AI-driven content tool — Descript, Claude Artifacts, ChatGPT
custom GPTs, etc. The structure (narrative-prose, mixed
registers) is the part that matters; the tool is interchangeable.
