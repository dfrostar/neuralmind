# LinkedIn post — 2026-08-28

Company-page post on discovering that our own claims-integrity CI guard had
been prescribing a false replacement phrase, and what we changed. Follow-up to
the 2026-08-19 post that introduced the guard.

Drafted here so `tests/test_docs_claims.py` vets it before it is posted — the
same reason `docs/social/` is a scanned glob. Note the irony this post is
about: the guard could not have caught the phrase in question, because until
this week the guard was the thing recommending it.

## Post text

Last week I wrote about the CI gate we built to stop our marketing site from making claims our code couldn't back.

This week we found the gate was recommending one.

<!-- claims-guard:allow — quotes the blocked phrase to show what the gate catches -->
Here is how it worked. If anyone wrote an absolute privacy claim — "your code never leaves your machine" — the build failed, and the error message told the author what to write instead. That replacement text was hardcoded in the guard. Thousands of engineers have shipped something similar: a linter that doesn't just say no, it says what to do.

<!-- claims-guard:allow — quoting the retired phrase in order to retire it -->
The replacement it prescribed: "NeuralMind makes no network calls of its own."

That sentence is false.

On a first install with no cached model, our own code opens an HTTPS connection and downloads an embedding model. Not a dependency doing it in the background — our module, our function call, forty lines into a file I have read many times. "Of its own" was precisely, exactly the wrong three words.

The phrase had spread to eighteen files: the README, eight pages of the marketing site including our privacy policy, the security docs, the FAQ, the machine-readable summary we publish for AI agents, two comparison pages, the business case, and two third-party plugin registries. Every one of them, correctly following the guard.

We didn't find it by auditing the claim. We found it while writing launch copy, when I went to cite the mechanism behind the claim and opened the module instead of the doc page.

Three things worth passing on.

**The true statement was stronger than the false one.** What we can defend is: no telemetry, and no repository content transmitted. One outbound request exists — a plain download of a public model — and it carries nothing about your code. An observer learns that a machine fetched a public file. That answers what people actually want to know, which was never "how many sockets do you open." It was "does my source leave." The reassuring-sounding claim was doing worse work than the accurate one.

**We made the retired phrase a build failure, rather than fixing the instances.** Search-and-replace would have felt finished. The pattern immediately found three more instances we had missed, including one on our privacy policy — the page a reader is most entitled to check with a packet capture. Human sweeps find what humans notice.

**A guard that prescribes a fix is making a claim of its own.** Ours had been reviewed as a regex — does it catch the bad phrase — and never as a statement, which is what the error message actually was. It carried no source, no reproduction command, no evidence level: precisely the standard it existed to enforce on everyone else. It has one now.

The same afternoon turned up the cost of not checking. Our air-gapped install guide told users to pre-cache the model through a library we stopped shipping by default back in June. The documented procedure didn't run. Nobody had reported it, which tells you something about how many people follow a runbook to the letter versus how many assume it works.

If you are evaluating AI tooling: ask a vendor which of their claims is checked by something other than a person remembering. Then ask who checked the checker. We hadn't.

All of it is public — the guard, the patterns, the manifest of every number we publish, and this correction: github.com/dfrostar/neuralmind

#EngineeringCulture #DeveloperTools #AIagents #TechnicalHonesty

## Image prompt (Gemini)

A dark editorial tech illustration on a near-black navy background (#070b15). Center-left: a clean geometric shield or gate form rendered in precise electric-blue linework (#3b82f6 to #60a5fa), the kind of icon that signals a validation check. Center-right, emerging from behind the shield and slightly overlapping it: a second, smaller shield in warm amber (#f59e0b), subtly misaligned with the first, as if the guard itself is casting a shadow that doesn't match its shape. A single thin line traces from the amber form back toward the blue one, suggesting the check being checked. Generous negative space, precise and quiet rather than busy. Style: high-end enterprise-software editorial illustration — Stripe, Linear, The Economist tech covers. Not photorealistic, no 3D gloss, no cartoon. Absolutely no text, numbers, letters, human figures, robots, padlocks, or circuit-board clichés. Landscape, 1.91:1.

## Claim sources

| Claim in post | Source |
|---|---|
| The guard prescribed the phrase in its failure message | `tests/test_docs_claims.py` FORBIDDEN, first entry: the reason string told authors to "say what NeuralMind itself does" and then named the phrase. Changed in this PR. |
| The phrase is false on a cold install | `neuralmind/onnx_embedder.py` — `_download_into` calls `urllib.request.urlretrieve(_ARCHIVE_URL, ...)`, resolution order `$NEURALMIND_ONNX_MODEL_DIR` → `~/.cache/neuralmind/onnx_models/` → `~/.cache/chroma/onnx_models/` → download. NeuralMind's own module, not a dependency's. |
| "Eighteen files" | Counted mechanically from the commit, not estimated: files whose pre-sweep content matched the phrase, excluding the tests and the drafts that quote it to retire it. README.md, SECURITY.md, docs/BUSINESS-CASE.md, docs/about.html, docs/comparisons/{context-engineering-stack,vs-cursor-codebase}.md, docs/llms.txt, docs/use-cases/any-llm.md, docs/wiki/FAQ.md, integrations/a0-plugins/neuralmind/index.yaml, and 8 files under site/src/ (effectiveness, layout, privacy, services, Assessment, BusinessCase, Features, Icon). The Hermes catalog manifest in the fork carried it too and was corrected separately — the post's "two third-party plugin registries" counts that one plus a0-plugins. |
| No telemetry, no repository content transmitted; one outbound request carrying no user data | Verified by reading every outbound-capable path: `onnx_embedder.py` (one hash-pinned GET for a public artifact), `daemon_client.py` (127.0.0.1), `local_client.py` (localhost:11434). No other network capability in the package. |
| Gating found three instances the sweep missed, one on the privacy policy | `site/src/app/privacy/page.tsx`, `site/src/components/ui/Icon.tsx`, `docs/wiki/FAQ.md` — all capitalised past a case-sensitive grep, all surfaced only once the pattern was added to FORBIDDEN. |
| The air-gapped guide's procedure did not run | `docs/use-cases/air-gapped.md` instructed `from chromadb.utils import embedding_functions`; the default install has been ChromaDB-free since v0.29.0, so that import raises ImportError on Linux, macOS arm64 and Windows x64. Fixed in the same PR. |
| "back in June" | v0.29.0 made the ChromaDB-free stack the default, released 2026-06-18 (`CHANGELOG.md`). An earlier draft of this post said "eleven months ago" — an invented interval, caught by the checklist below before posting. |

## Pre-post checklist

- [x] Confirmed the v0.29.0 release date: 2026-06-18, so the interval is ~2 months. The draft said "eleven months ago", which was invented; corrected to "back in June". This is the only time-relative claim in the post.
- [ ] No performance number appears in this post by design; it is a process post. Do not add a ratio without a `site/claims.json` entry.
- [ ] The retired phrase is quoted once, under an allow marker. Do not remove the marker; do not quote it again unmarked.
