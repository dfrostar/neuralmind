# Reddit presence + roundup page — setup runbook

End-to-end, in order, from "no Reddit account" to "published, honest
`reddit-roundup.html` that ranks for `neuralmind reddit`". Nothing here requires
faking anything; the whole flow is disclosed-maker and reproducible.

The pieces already built in the repo:

- [`reddit-roundup.html`](./reddit-roundup.html) — the page (staging, unpublished).
- [`README.md`](./README.md) — honesty rules + publish gate + reusable snippet.
- [`../launch/reddit-seed-kit.md`](../launch/reddit-seed-kit.md) — the posts/comments that create real threads.
- "What developers say on Reddit" sections in
  [`vs-github-copilot.md`](../comparisons/vs-github-copilot.md) and
  [`vs-cursor-codebase.md`](../comparisons/vs-cursor-codebase.md).

---

## Phase 0 — Create the Reddit account (you, manually, ~10 min)

This part is yours — it can't be automated (verification + CAPTCHA), and
automating account creation violates Reddit's ToS.

1. Go to <https://www.reddit.com/register/> in a normal browser. Use a real
   email you control (a project address is fine, e.g. one tied to the repo).
2. Pick a username that reads as the maintainer, not a persona —
   `u/dfrostar`, `u/neuralmind-dev`, or your real handle. **Do not** create
   multiple accounts to look like multiple users; that's the sockpuppeting we
   explicitly don't do.
3. Verify the email. Enable 2FA.
4. Fill the profile: one line of bio ("building NeuralMind, an open-source local
   memory layer for AI coding agents"), link to <https://github.com/dfrostar/neuralmind>.
   Transparency up front is the entire credibility play.
5. **Season the account before posting anything of your own.** Brand-new
   zero-karma accounts that immediately self-post get auto-removed by most subs'
   spam filters. For ~1–2 weeks: comment genuinely in
   `r/LocalLLaMA`, `r/ClaudeAI`, `r/ChatGPTCoding` using the
   [comment templates](../launch/reddit-seed-kit.md#comment-templates--answering-supportquestions-as-the-maintainer)
   only where they actually answer a thread. Get to a few hundred comment karma.

> Why the wait: it's not a growth hack, it's how you avoid the spam filter and
> how the sub learns you're a participant, not a drive-by. Skipping it is the
> single most common reason a maker post vanishes.

---

## Phase 1 — Seed real threads (you, over 1–3 weeks)

Goal: produce **≥3 real threads** that mention NeuralMind, so the roundup page
has honest material. Use [`../launch/reddit-seed-kit.md`](../launch/reddit-seed-kit.md).

1. **Read each target sub's rules + flair requirements the day you post** — they
   change, and many gate self-promo behind a karma ratio.
2. **Post 1 (genuine question)** in `r/LocalLLaMA` or `r/ChatGPTCoding`. This is
   a real methodology question; the disclosure is honest but the post earns its
   place. Be around to reply for a few hours.
3. **Answer support questions** as they appear (search `r/ClaudeAI`,
   `r/ChatGPTCoding` for "token cost", "codebase context", "MCP memory"). Lead
   with substance, disclose when you name the project, one link max.
4. **Post 2 (AMA)** within a day or two of a release with a concrete headline
   (e.g. the next `feat:` that lands). Answer hostile questions first and fully.
5. **Never** ask for upvotes, never post the same link across many threads in a
   short window, never delete critical comments.

You'll know you're ready for Phase 2 when you have at least 3 threads with
working `https://reddit.com/...` permalinks — yours or, ideally, others'.

---

## Phase 2 — Populate the roundup page (real data only)

Open [`reddit-roundup.html`](./reddit-roundup.html). For each real thread:

1. **Live threads table:** unhide the `<table>` (remove `hidden`), delete the
   `[[ ADD REAL THREADS ]]` placeholder, and add one row per thread — real
   title, subreddit, date, and a one-line takeaway. Link the title to the
   permalink.
2. **"What developers like" quotes:** replace each
   `[[ ADD REAL QUOTE + reddit permalink ]]` with a real `<blockquote>` —
   exact quote, real `u/handle`, real permalink in the `.src`. If a theme has no
   real quote yet, delete that subsection rather than invent one.
3. **Criticism section:** already honest (sourced from `HONEST-ASSESSMENT.md`).
   When a real thread raises one of these, add the linked quote above the
   response. Keep responses truthful; link the fix/benchmark.
4. **Leave the benchmark table as-is** unless `benchmarks/public.md` changes —
   every number there is already real and cited. Never add an unmeasured number
   (no SWE-bench, etc.).
5. **`vs <tool>` threads:** also paste a linked quote into that comparison
   page's "What developers say on Reddit" section (template in
   [`README.md`](./README.md#reusable-what-reddit-says-snippet-for-comparison-pages)).

**Rule of thumb:** if you can't link it, it doesn't go on the page.

---

## Phase 3 — Publish (flip from staging to live)

Only when the [publish gate](./README.md#publish-gate-for-reddit-rounduphtml) is
met (≥3 real linked threads, every quote real). Then, in `reddit-roundup.html`:

1. Delete the top `<!-- STAGING … -->` build comment.
2. Delete the visible `.staging` notice block.
3. Remove the `<meta name="robots" content="noindex,nofollow">` line.
4. Set the visible **"Last reviewed"** date and the JSON-LD **`dateModified`**
   (replace both `REPLACE-…` markers) and the year in the `<title>` if you want it.

Then wire it into the site (mirrors the docs + SEO checklist in root `CLAUDE.md`):

5. **`sitemap.xml`** — add:
   ```xml
   <url>
     <loc>https://dfrostar.github.io/neuralmind/community/reddit-roundup.html</loc>
     <changefreq>monthly</changefreq>
     <priority>0.6</priority>
   </url>
   ```
6. **Homepage footer** (`docs/index.html`) — add a link:
   `<a href="community/reddit-roundup.html">What developers say on Reddit</a>`.
7. **`docs/index.html` `<meta name="keywords">`** — ensure `neuralmind reddit`,
   `neuralmind review` are present (add if missing).
8. Commit with a normal `docs:` message. GitHub Pages serves it on push to `main`.

> Note: GitHub Pages serves `.html` directly. The page lives at
> `…/community/reddit-roundup.html`. If you later want the prettier
> `…/community/reddit-roundup/` slug, add a folder with an `index.html` and a
> redirect — not required to rank.

---

## Phase 4 — Maintain (monthly, ~20 min)

LLMs and Google favor fresh pages on brand queries. Once live:

1. Search Reddit for new NeuralMind mentions; add real rows/quotes.
2. Bump the "Last reviewed" date and `dateModified` **only when you actually
   review** — don't fake freshness.
3. When a release addresses a criticism on the page, add one line under that
   criticism: "Addressing this: v0.X.Y shipped …" with a link. This is the
   "Reddit feedback → our fix" loop that gets the page cited.
4. Re-check each cited thread still resolves (Reddit posts get deleted); remove
   dead links.

---

## Measuring whether it's working (60-day horizon)

- **Google Search Console** (add the Pages property if not already): impressions
  for `neuralmind reddit`-type queries should climb once indexed.
- **LLM citations:** periodically ask ChatGPT / Claude / Perplexity "what do
  developers on Reddit say about NeuralMind?" and note whether the roundup page
  is cited.
- **Referral traffic** from `perplexity.ai` / `chat.openai.com` = LLMs sending
  users to the page.
- **Inbound links:** if the summary is good, people link to *it* from Reddit —
  the real win.

---

## The line we don't cross (recap)

No fake usernames or personas. No invented quotes, scores, or benchmarks. No
`DiscussionForumPosting` schema or `/reddit/`-impersonation URLs. No
upvote-asking or vote-rings. No deleting honest criticism. Disclose the maker
relationship every time. The page wins precisely *because* it's the honest,
verifiable, up-to-date answer — that's what LLMs prefer to cite and what
developers bookmark instead of resent.
