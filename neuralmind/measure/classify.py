# SPDX-License-Identifier: MIT
"""Tool categories (see the spec's "Tool categories"): exploration, edit, web,
shell, other. Shell commands are exploration only when every pipeline stage is
read-only and nothing is redirected to a file."""

from __future__ import annotations

import json
import re
import shlex

EXPLORATION = "exploration"
EDIT = "edit"
WEB = "web"
SHELL = "shell"
OTHER = "other"
CATEGORIES = (EXPLORATION, EDIT, WEB, SHELL, OTHER)

READ_ONLY_WORDS = frozenset(
    """cat head tail less more wc ls ll tree find grep rg ag egrep fgrep stat file
    which type pwd echo printf du df diff cut sort uniq awk jq yq tr column nl od
    xxd strings realpath readlink basename dirname test true false env printenv
    date hostname uname id whoami ps pgrep md5sum sha256sum shasum b2sum
    tokei cloc sloccount fd fdfind bat rga ripgrep""".split()
)
READ_ONLY_GIT = frozenset(
    "log show diff status blame grep ls-files ls-tree rev-parse branch remote describe "
    "shortlog name-rev cat-file merge-base rev-list tag worktree reflog".split()
)
# git's own options that take the next word as their operand, before the subcommand
_GIT_OPTIONS_WITH_VALUE = frozenset(
    "-C -c --git-dir --work-tree --namespace --config-env --super-prefix --attr-source".split()
)
# words skipped before the command proper
PREFIX_WORDS = frozenset("sudo time nohup command builtin exec".split())
_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# Operators are split out by shlex itself, so a `|` or `;` inside quotes stays part of
# its word (`rg 'foo|bar'`), and an unquoted newline separates stages like `;` does.
_PUNCT = "|&;()<>\n"
# shlex drops the quotes from a quoted word, so a quoted `>` or `|` (`rg '>' src`) would come
# back looking like the operator. Operator characters inside quotes or after a backslash are
# swapped for private-use stand-ins before shlex runs, and words get the originals back.
_STAND_IN = {c: chr(0xE000 + n) for n, c in enumerate(_PUNCT)}
_RESTORE = str.maketrans({v: k for k, v in _STAND_IN.items()})


def _protect_quoted_operators(command: str) -> str:
    out: list[str] = []
    quote = ""  # the quote character while inside one
    escaped = False
    for c in command:
        if escaped:
            out.append(_STAND_IN.get(c, c))
            escaped = False
        elif c == "\\" and quote != "'":
            out.append(c)
            escaped = True
        elif quote:
            out.append(c if c == quote else _STAND_IN.get(c, c))
            if c == quote:
                quote = ""
        else:
            out.append(c)
            if c in "'\"":
                quote = c
    return "".join(out)


def _stages(command: str) -> list[list[str]] | None:
    """Split a shell command into pipeline stages (lists of words), quote-aware.

    Returns None when the command can't be tokenized (unbalanced quotes) or when a
    redirection writes to something other than /dev/null or another descriptor.
    """
    lex = shlex.shlex(_protect_quoted_operators(command), posix=True, punctuation_chars=_PUNCT)
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    try:
        tokens = list(lex)
    except ValueError:
        return None
    stages: list[list[str]] = [[]]
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t and all(c in _PUNCT for c in t):
            if ">" in t:
                # a redirection: `>` / `>>` to a file writes unless the target is /dev/null;
                # `>&` / `&>` with a descriptor number is a dup (2>&1) and writes nothing
                target = tokens[i + 1].translate(_RESTORE) if i + 1 < len(tokens) else ""
                dup = t.endswith("&") and target.isdigit()
                if not dup and target != "/dev/null":
                    return None
                i += 2
                continue
            if "<" in t:
                i += 2  # input redirection or heredoc marker: skip the operand
                continue
            if stages[-1]:
                stages.append([])
            i += 1
            continue
        stages[-1].append(t.translate(_RESTORE))
        i += 1
    return stages


def shell_is_readonly(command: str | None) -> bool:
    if not command or not command.strip():
        return False
    stages = _stages(command)
    if stages is None:
        return False
    for words in stages:
        i = 0
        # skip `cd X`, assignments and prefixes
        while i < len(words):
            w = words[i]
            if w == "cd":
                i += 2
                continue
            if _ASSIGN.match(w) or w in PREFIX_WORDS or w.startswith("-"):
                i += 1
                continue
            break
        if i >= len(words):
            continue  # a bare `cd X` stage, or nothing
        head = words[i].rsplit("/", 1)[-1]
        rest = words[i + 1 :]
        if head == "git":
            if not _git_is_readonly(rest):
                return False
            continue
        if head == "sed":
            if any(w == "-i" or w.startswith("-i") or w == "--in-place" for w in rest):
                return False
            continue
        if head not in READ_ONLY_WORDS:
            return False
    return True


def _git_is_readonly(words: list[str]) -> bool:
    """`git <sub> …` with a subcommand that only reads, in a form that only reads:
    `branch`, `tag` and `remote` mutate when given a name, `worktree` unless `list`."""
    i = 0
    while i < len(words):
        if words[i] in _GIT_OPTIONS_WITH_VALUE:
            i += 2  # `git -C /repo diff`: the operand is not the subcommand
        elif words[i].startswith("-"):
            i += 1
        else:
            break
    if i >= len(words):
        return True  # `git --version` and the like
    sub, rest = words[i], words[i + 1 :]
    if sub not in READ_ONLY_GIT:
        return False
    positional = [w for w in rest if not w.startswith("-")]
    if sub == "worktree":
        return bool(positional) and positional[0] == "list"
    if sub == "tag":
        return not positional or any(w in ("-l", "--list") for w in rest)
    if sub == "branch":
        listing = ("-l", "--list", "-a", "-r", "-v", "-vv", "--show-current")
        return not positional or any(w in listing for w in rest)
    if sub == "remote":
        return not positional or positional[0] in ("show", "get-url")
    return True


def categorize_hermes(tool_name: str | None, arguments: str | dict | None) -> str:
    name = tool_name or ""
    if name in ("read_file", "search_files"):
        return EXPLORATION
    if name == "terminal":
        return EXPLORATION if shell_is_readonly(_command_of(arguments)) else SHELL
    if name in ("patch", "write_file"):
        return EDIT
    if name in ("web_search", "web_extract", "web_fetch"):
        return WEB
    return OTHER


def categorize_claude(tool_name: str | None, tool_input: dict | None) -> str:
    name = tool_name or ""
    if name in ("Read", "Grep", "Glob", "LS", "NotebookRead"):
        return EXPLORATION
    if name == "Bash":
        return EXPLORATION if shell_is_readonly((tool_input or {}).get("command")) else SHELL
    if name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        return EDIT
    if name in ("WebFetch", "WebSearch"):
        return WEB
    return OTHER


def _command_of(arguments: str | dict | None) -> str | None:
    parsed = arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except Exception:
            return arguments
    if isinstance(parsed, dict):
        cmd = parsed.get("command")
        return cmd if isinstance(cmd, str) else None
    return None
