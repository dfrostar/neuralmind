"""Aggregate session rows by agent and source group; apply the pre-registered reading."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from .classify import CATEGORIES, EDIT, EXPLORATION, SHELL
from .rows import BLOCK

GROUP_ORDER = ("interactive", "automated", "subagent", "benchmark")


def read_rows(paths: list[str | Path]) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for p in paths:
        with Path(p).expanduser().open() as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                key = (r["agent"], r["session_id"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(r)
    return rows


def _share(num: int, den: int) -> float | None:
    return (num / den) if den else None


def aggregate(rows: list[dict]) -> dict:
    out: dict = {"groups": {}, "n_sessions": len(rows)}
    by: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        by.setdefault((r["agent"], r["source_group"]), []).append(r)
    for (agent, group), rs in sorted(
        by.items(),
        key=lambda kv: (kv[0][0], GROUP_ORDER.index(kv[0][1]) if kv[0][1] in GROUP_ORDER else 9),
    ):
        ctx = sum(r["context_tokens_est"] for r in rs)
        billed = sum(r["prompt_tokens_billed"] for r in rs)
        kinds = set()
        for r in rs:
            kinds |= set(r["billed_tokens"]) | set(r["first_tokens"])
        first = {k: sum(r["first_tokens"].get(k, 0) for r in rs) for k in kinds}
        billed_kind = {k: sum(r["billed_tokens"].get(k, 0) for r in rs) for k in kinds}
        first_total = sum(first.values())
        per_session = [
            r["billed_tokens"].get(EXPLORATION, 0) / r["context_tokens_est"]
            for r in rs
            if r["context_tokens_est"]
        ]
        out["groups"][f"{agent}/{group}"] = {
            "agent": agent,
            "source_group": group,
            "sessions": len(rs),
            "calls": sum(r["calls"] for r in rs),
            "tokenizers": sorted({r["tokenizer"] for r in rs}),
            "prompt_tokens_billed": billed,
            "context_tokens_est": ctx,
            "calibration_est_over_billed": _share(ctx, billed),
            "exploration_share_billed": _share(billed_kind.get(EXPLORATION, 0), ctx),
            "exploration_share_first": _share(first.get(EXPLORATION, 0), first_total),
            "exploration_share_median_session": (
                statistics.median(per_session) if per_session else None
            ),
            "block_share_billed": _share(billed_kind.get(BLOCK, 0), ctx),
            "edit_share_billed": _share(billed_kind.get(EDIT, 0), ctx),
            "shell_share_billed": _share(billed_kind.get(SHELL, 0), ctx),
            "first_tokens": first,
            "billed_tokens": billed_kind,
            "tool_calls": {c: sum(r["tool_calls"].get(c, 0) for r in rs) for c in CATEGORIES},
            "sessions_with_block": sum(1 for r in rs if r["first_tokens"].get(BLOCK)),
        }
    out["reading"] = reading(out)
    return out


def reading(agg: dict) -> dict:
    """The spec's pre-registered thresholds, on interactive sessions per agent."""
    verdicts = {}
    for key, g in agg["groups"].items():
        if g["source_group"] != "interactive":
            continue
        s = g["exploration_share_billed"]
        if s is None:
            verdicts[key] = "no data"
        elif s < 0.10:
            verdicts[key] = "under 10%: arithmetic, not felt on a bill"
        elif s < 0.30:
            verdicts[key] = "10% to 30%: the claim stands with the share beside it"
        else:
            verdicts[key] = "30% or more: a material part of the bill"
    return verdicts


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{100 * x:.1f}%"


def to_markdown(agg: dict, title: str) -> str:
    lines = [f"# {title}", "", f"Sessions: {agg['n_sessions']}.", ""]
    lines.append(
        "| Agent / source | Sessions | API calls | Prompt tokens billed | Context est. ÷ billed | Exploration share (billed) | median per session | first-time | Block share | Edit | Shell |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for key, g in agg["groups"].items():
        lines.append(
            f"| {key} | {g['sessions']} | {g['calls']} | {g['prompt_tokens_billed']:,} | "
            f"{_pct(g['calibration_est_over_billed'])} | **{_pct(g['exploration_share_billed'])}** | "
            f"{_pct(g['exploration_share_median_session'])} | {_pct(g['exploration_share_first'])} | "
            f"{_pct(g['block_share_billed'])} | {_pct(g['edit_share_billed'])} | {_pct(g['shell_share_billed'])} |"
        )
    lines += ["", "Pre-registered reading (interactive sessions):", ""]
    for key, v in agg["reading"].items():
        lines.append(f"- {key}: {v}")
    toks = sorted({t for g in agg["groups"].values() for t in g["tokenizers"]})
    lines += [
        "",
        f"Tokenizer(s): {', '.join(toks) or '—'}. Shares are billed exploration tokens over estimated context tokens, both with the same tokenizer and presence model (`docs/specs/EXPLORATION-SHARE-SPEC.md`).",
    ]
    return "\n".join(lines) + "\n"
