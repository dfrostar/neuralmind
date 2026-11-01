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
# words skipped before the command proper
PREFIX_WORDS = frozenset("sudo time nohup command builtin exec".split())
_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SPLIT = re.compile(r"\|\||&&|;|\|")
_REDIRECT = re.compile(r"(?<![0-9&])>{1,2}\s*(\S+)")


def shell_is_readonly(command: str | None) -> bool:
    if not command or not command.strip():
        return False
    # Any redirect to something other than /dev/null (2>&1 and &> are excluded by
    # the lookbehind) writes a file.
    for target in _REDIRECT.findall(command):
        if target not in ("/dev/null", "&1", "&2"):
            return False
    if "&>" in command:
        return False
    for stage in _SPLIT.split(command):
        stage = stage.strip()
        if not stage:
            continue
        try:
            words = shlex.split(stage, posix=True)
        except ValueError:
            return False
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
            continue  # a bare `cd X` stage
        head = words[i].rsplit("/", 1)[-1]
        rest = words[i + 1 :]
        if head == "git":
            sub = next((w for w in rest if not w.startswith("-")), "")
            if sub not in READ_ONLY_GIT:
                return False
            continue
        if head == "sed":
            if any(w == "-i" or w.startswith("-i") or w == "--in-place" for w in rest):
                return False
            continue
        if head in ("tail", "head", "cat") and any(w in ("-f", "--follow") for w in rest):
            continue
        if head not in READ_ONLY_WORDS:
            return False
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
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            return arguments
    if isinstance(arguments, dict):
        cmd = arguments.get("command")
        return cmd if isinstance(cmd, str) else None
    return None
