"""What the prompt-submit hook names, against the files that answer each prompt.

The ``prompt-submit`` hook action (Claude Code's ``UserPromptSubmit``, the
Hermes plugin's ``pre_llm_call``) adds a block to every prompt about the code.
This runs a fixed prompt set through the hook's own function,
``neuralmind.hooks._spread_for_prompt``, on a built project, and checks the
files each block names against the files that answer the prompt (chosen by
reading the code, before running anything). Per prompt and in total it
reports:

- **named**: the block names at least one answering file;
- **first**: the first code file the block names answers the prompt;
- **tokens**: the block's size (tiktoken ``o200k_base``, the self-benchmark's
  tokenizer; characters / 4 when tiktoken isn't installed, flagged).

It reads both block formats: the file paths and symbols of v4.11.0, and the
raw node ids (``- <node_id> (activation 0.05)``) before it, mapped to files
through the project's graph. So it measures an older release too: run this
file as a script with that release's checkout first on ``PYTHONPATH``
(``PYTHONPATH=<old checkout> python tests/benchmark/prompt_recall.py …``).

Prompt sets (JSON: ``repo``, ``commit``, ``prompts`` of ``{prompt, expect}``):

- ``tests/benchmark/prompt_recall_click.json``: pallets/click at a pinned
  commit, the set the file ranking was tuned on.
- ``tests/benchmark/prompt_recall_neuralmind.json``: this repository, at the
  commit it names, held out while the ranking was tuned.

Run it (read-only: learning is off for the run)::

    git clone https://github.com/pallets/click && git -C click checkout <commit>
    neuralmind build click
    python -m tests.benchmark.prompt_recall click \\
        --prompts tests/benchmark/prompt_recall_click.json
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import sys
from pathlib import Path

_OLD_LINE = re.compile(r"^- (\S+) \(activation [0-9.]+\)$")
_NEW_LINE = re.compile(r"^- ([^:]+?)(?::|$)")
_DOCS_LINE = re.compile(r"^Docs: (.+)$")


def _tokenizer():
    try:
        import tiktoken

        enc = tiktoken.get_encoding("o200k_base")
        return "o200k_base", lambda text: len(enc.encode(text))
    except Exception:
        return "chars/4 (tiktoken unavailable)", lambda text: (len(text) + 3) // 4


def _named_files(block: str, id_to_file: dict[str, str]) -> list[str]:
    """Files the block names, in order: paths, or node ids mapped to their file.

    A matching doc is named on the block's ``Docs: a, b`` line, not a bullet.
    """
    files: list[str] = []
    for line in block.splitlines():
        old = _OLD_LINE.match(line)
        new = None if old else _NEW_LINE.match(line)
        docs = None if old or new else _DOCS_LINE.match(line)
        if old:
            paths = [id_to_file.get(old.group(1), "")]
        elif new:
            paths = [new.group(1).strip()]
        elif docs:
            paths = [p.strip() for p in docs.group(1).split(",")]
        else:
            continue
        for path in paths:
            if path and path not in files:
                files.append(path)
    return files


# Every document format NeuralMind indexes (``ingest-content``, the docs scope).
_DOC_SUFFIXES = (
    ".md",
    ".markdown",
    ".mkd",
    ".mdx",
    ".rst",
    ".txt",
    ".text",
    ".org",
    ".adoc",
    ".pdf",
    ".html",
)


def _is_doc(path: str) -> bool:
    return path.lower().endswith(_DOC_SUFFIXES)


def measure(project: str, prompts: list[dict]) -> dict:
    os.environ["NEURALMIND_NO_LEARN"] = "1"
    # The committed figures are for the default block: drop the caller's overrides.
    for name in ("NEURALMIND_RECALL_MIN_SIMILARITY", "NEURALMIND_SYNAPSE_OUTLIERS"):
        os.environ.pop(name, None)
    from neuralmind import hooks
    from neuralmind.core import NeuralMind

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        mind = NeuralMind(project)
        if not mind._load_existing_index():
            raise SystemExit(f"no index in {project}: run `neuralmind build {project}` first")
    id_to_file = {str(n.get("id")): str(n.get("source_file") or "") for n in mind.embedder.nodes}
    tokenizer, count = _tokenizer()
    rows = []
    for item in prompts:
        block = hooks._spread_for_prompt(project, item["prompt"])
        files = _named_files(block, id_to_file)
        code = [f for f in files if not _is_doc(f)]
        rows.append(
            {
                "prompt": item["prompt"],
                "expect": item["expect"],
                "files": files,
                "named": any(f in item["expect"] for f in files),
                "first": bool(code) and code[0] in item["expect"],
                "tokens": count(block) if block else 0,
                "block": block,
            }
        )
    injected = [r["tokens"] for r in rows if r["tokens"]]
    return {
        "project": Path(project).resolve().name,
        "tokenizer": tokenizer,
        "n": len(rows),
        "named": sum(r["named"] for r in rows),
        "first": sum(r["first"] for r in rows),
        "injected": len(injected),
        "mean_tokens_injected": round(sum(injected) / len(injected), 1) if injected else 0.0,
        "max_tokens": max(injected, default=0),
        "rows": rows,
    }


def _print(report: dict, verbose: bool) -> None:
    for r in report["rows"]:
        flags = f"{'named' if r['named'] else 'MISS '} {'first' if r['first'] else '     '}"
        print(f"{flags} {r['tokens']:>4} tok  {r['prompt']}")
        print(f"      {', '.join(r['files'][:6]) or '(nothing)'}")
        if verbose and r["block"]:
            print("\n".join("      | " + line for line in r["block"].splitlines()))
    n = report["n"]
    print()
    print(f"answering file named:      {report['named']}/{n}")
    print(f"first code file answers:   {report['first']}/{n}")
    print(f"blocks injected:           {report['injected']}/{n}")
    print(
        f"tokens per injected block: mean {report['mean_tokens_injected']:.0f}, "
        f"max {report['max_tokens']} ({report['tokenizer']})"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", help="a built NeuralMind project")
    parser.add_argument("--prompts", required=True, help="prompt set JSON")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("-v", "--verbose", action="store_true", help="print each block")
    args = parser.parse_args(argv)
    data = json.loads(Path(args.prompts).read_text(encoding="utf-8"))
    report = measure(args.project, data["prompts"])
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        _print(report, args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
