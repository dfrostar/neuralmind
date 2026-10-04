# NeuralMind v4.5.1 — decision memory answers questions, for every role

**Type:** Patch release | **Theme:** decision memory

Two fixes to decision memory, both meant for v4.5.0, that landed just after it
was tagged:

1. **Decision search answers questions.** A question used to find nothing
   unless every one of its words appeared in a decision.
2. **The default MCP roles reach the memory retrieval tools.**
   `neuralmind_memory_search`, `neuralmind_memory_timeline` and
   `neuralmind_memory_get` returned `security_denied` to every caller that
   didn't declare `admin`.

## 1. Decision search answers questions

Decision search required every word of the query, so `neuralmind decisions query`
found a decision for "sqlite wal" but not for "how do we handle sqlite wal?",
and agents send questions.

- **Any word of the query can match.** Common words such as "how" and "the"
  are ignored, and decisions matching more of the words, and rarer ones, rank
  first. This covers `decisions query`, the `neuralmind_query_decisions` and
  `neuralmind_memory_search` MCP tools, and the LIKE fallback used when SQLite
  lacks FTS5. A question nothing answers can still return partial matches, so
  check the titles.
- **Status filters are case-insensitive**, and `ALL` returns every status
  (over MCP, the advertised `"all"` used to match nothing). The CLI's
  `--status` also accepts `INVALIDATED`. An unknown status is an error,
  `invalid_request` over MCP, instead of an empty result.
- **`neuralmind decisions eval` leaves your decisions alone.** It used to delete
  the project's `.neuralmind/memory.db` and leave synthetic decisions with the
  author `eval-harness` behind; it now runs on a scratch store. The
  [Memory Layer wiki](../wiki/Memory-Layer.md#eval-harness) shows how to retire
  any it left. `--format md` no longer crashes.
- **`neuralmind decisions eval --queries FILE`** scores search against
  questions with known answers: recall@k and MRR as mean and range per query
  kind, with every miss and false positive listed. The committed query set and
  its measured results are in the
  [Memory Layer wiki](../wiki/Memory-Layer.md#eval-harness).
- **MCP errors say what to do.** A missing index is `code: "index_not_built"`
  with a hint to call `neuralmind_build`, not `security_denied`;
  `security_denied` carries `reason: "rbac"` or `"rate_limit"`. See
  [Troubleshooting](../wiki/Troubleshooting.md).

## 2. The default roles can use the memory retrieval tools

`neuralmind_memory_search`, `neuralmind_memory_timeline` and
`neuralmind_memory_get` were never added to the default role policy. Through
the MCP server, a caller that declared no role (which means `builder`) or
declared `reader` got `security_denied` from all three, so agents couldn't use
the progressive-retrieval path the
[Memory Layer wiki](../wiki/Memory-Layer.md#rbac) describes.

- Builder and reader now have all three. They only read.
- Recording and invalidating decisions stays builder-only.
- `synaptic_neighbors`, `structural_neighbors`, `next_likely`, `impact` and
  `review` stay admin-only by default, as the
  [Security Guide](../SECURITY-GUIDE.md#access-control) lists.
- A test now requires every MCP tool to be granted to the default roles or
  listed as left out on purpose, so a new tool can't ship outside the policy
  unnoticed.

A `security.roles` policy in `neuralmind-backend.yaml` replaces the defaults,
so a project that sets one keeps exactly the tools it lists.

## What the agent actually sees post-install

| Agent | Before | After |
|---|---|---|
| **Claude Code** (MCP + hooks) | A question to `neuralmind_query_decisions` found nothing unless every word matched; `neuralmind_memory_search`, `_timeline` and `_get` came back `security_denied` | Questions find decisions, best match first; the three memory retrieval tools return results |
| **Cursor / Cline / Continue** (MCP) | Same as Claude Code | Same fix |
| **Generic MCP client** | The memory retrieval tools needed `role: "admin"`; an unknown `status` filter returned an empty result | They work with no role or `reader`; an unknown status is `invalid_request` |

## Upgrade notes

- No reinstall and no configuration change: `pip install -U neuralmind`.
- If you passed `role: "admin"` only to reach the memory retrieval tools, you
  can drop it.
- If `neuralmind decisions eval` ever ran inside one of your projects, look for
  decisions with the author `eval-harness`; the
  [Memory Layer wiki](../wiki/Memory-Layer.md#eval-harness) shows how to retire
  them.

## Related

- CLI reference: [`decisions`](../wiki/CLI-Reference.md#decisions)
- [Memory Layer wiki](../wiki/Memory-Layer.md) ·
  [Security Guide: access control](../SECURITY-GUIDE.md#access-control)
- Previous release: [v4.5.0](RELEASE_NOTES_v4.5.0.md)
