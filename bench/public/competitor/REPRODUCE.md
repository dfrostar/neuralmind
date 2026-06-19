# Competitor head-to-head — `codebase-memory-mcp` (documented external run)

This file is the **auditable provenance** for any `codebase-memory-mcp` row in
the public benchmark. The competitor's retrieval stack does not install in our
CI sandbox (network policy + heavyweight model deps), so — rather than omit the
comparison or fake it — we run it in a **scripted, documented environment** and
commit the raw output here. Anyone can re-run these exact steps independently.

We never tune the competitor to lose. Where a config materially changes its
numbers, we disclose both. If you can represent it more fairly, open a PR.

## Pinned version

- Tool: `codebase-memory-mcp`
- Version / commit: _**TODO: pin exact tag + SHA at run time**_
- Install + run docs (theirs): _**TODO: link upstream README / quickstart**_

## Environment

- Same pinned repos and the **same `evals/public/manifest.json` query set** used
  for every other backend (identical questions, identical objective gold files).
- Same tokenizer (`tiktoken o200k_base`) applied to the competitor's assembled
  context, so the cost axis is apples-to-apples.

## Procedure

1. Check out each repo from `evals/public/manifest.json` at its pinned `commit`.
2. Index it with `codebase-memory-mcp` per its own docs (record the exact
   commands run, here).
3. For each query, capture the context the competitor would supply and the files
   it references; score gold-file recall with the **same** `neuralmind.quality`
   code the other backends use. A thin `competitor_adapter` shell-out (to be
   added when this is first executed — it does **not** exist in the repo yet, by
   design) will do this, e.g.:

   ```bash
   # Illustrative — module not yet implemented; see "Status" below.
   python -m evals.public.competitor_adapter \
       --tool codebase-memory-mcp --repo requests --out raw/requests.json
   ```

   It is intentionally NOT wired into the default `python -m evals.public.run`,
   so the public table never silently depends on an un-pinned external tool.

4. Commit the raw per-query output under `bench/public/competitor/raw/` and add
   the summarized rows to the report, marked **"reproduced externally."**

## Status

> **Not yet run.** The baseline matrix (`full-file` / `ripgrep` /
> `embedding-rag` / `neuralmind`) ships first and is fully reproducible in CI.
> The competitor row lands once the pinned external run above is executed and its
> raw traces committed here — tracked as a fast-follow so the head-to-head is
> honest and auditable rather than rushed.
