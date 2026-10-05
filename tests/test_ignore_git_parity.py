"""``neuralmind.ignore`` agrees with ``git check-ignore`` (gitignore(5)).

The matcher decides ``.neuralmindignore`` everywhere and ``.gitignore`` when
the project isn't a git repository, so it has to mean exactly what git means.
Each case writes a ``.gitignore`` into a fresh repository, creates the files,
and asks git and :func:`neuralmind.ignore.matches` the same question for every
file and every directory above it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from neuralmind.ignore import load_patterns, matches, pattern_regex

pytestmark = [
    pytest.mark.skipif(shutil.which("git") is None, reason="git not installed"),
    # Names with '*', '?', '"' or trailing spaces can't exist on Windows.
    pytest.mark.skipif(sys.platform == "win32", reason="POSIX file names"),
]

# (id, .gitignore lines -- or raw file content --, files to create)
CASES = [
    (
        "character-classes",
        ["*.py[co]", "[Oo]bj/", "[Bb]in/"],
        [
            "a.pyc",
            "x/a.pyo",
            "a.py",
            "a.pyd",
            "obj/Debug/App.cs",
            "src/Obj/b.cs",
            "lib/OBJ/c.cs",
            "Bin/x.cs",
            "src/bin/y.cs",
            "binx/z.cs",
        ],
    ),
    (
        "class-syntax",
        [
            "[a-c]1.py",
            "[]x]2.py",
            "[!]x]3.py",
            "[[:digit:]]4.py",
            "[a-]5.py",
            "[\\]]6.py",
            "[^x]7.py",
            "u[8.py",
            "[[:bogus:]]9.py",
            "[[:a]0.py",
            "[c-a]r.py",
        ],
        [
            "a1.py",
            "d1.py",
            "]2.py",
            "x2.py",
            "y2.py",
            "q3.py",
            "]3.py",
            "x3.py",
            "94.py",
            "a4.py",
            "-5.py",
            "a5.py",
            "b5.py",
            "]6.py",
            "x7.py",
            "y7.py",
            "u[8.py",
            "u8.py",
            "b9.py",
            "a0.py",
            "sub/:0.py",  # at the top, ':' would read as pathspec magic
            "[0.py",
            "b0.py",
            "cr.py",
            "br.py",
        ],
    ),
    (
        "escapes-and-comments",
        [
            "\\#notes.py",
            "#comment.py",
            "\\!important.py",
            "\\*star.py",
            "q\\?.py",
            "e\\scape.py",
        ],
        [
            "#notes.py",
            "#comment.py",
            "!important.py",
            "*star.py",
            "xstar.py",
            "q?.py",
            "qa.py",
            "escape.py",
        ],
    ),
    (
        "trailing-and-leading-spaces",
        ["foo\\ ", "bar  ", "baz\\ \\ ", " lead.py"],
        ["foo ", "foo", "bar", "bar  ", "baz  ", "baz", " lead.py", "lead.py"],
    ),
    (
        "directory-only",
        ["build/", "**/cache/", "/out/"],
        [
            "build",
            "src/build",
            "x/build/y.py",
            "build.py",
            "cache",
            "a/cache/b.py",
            "out/o.py",
            "lib/out/p.py",
        ],
    ),
    (
        "excluded-parent-cannot-be-re-included",
        ["logs/", "!logs/keep.py", "vendor", "!vendor/keep.py", "tmp/*", "!tmp/keep.py"]
        + ["deep/", "!deep/a/"],
        [
            "logs/keep.py",
            "logs/a.py",
            "vendor/keep.py",
            "vendor/b.py",
            "tmp/keep.py",
            "tmp/c.py",
            "deep/a/d.py",
        ],
    ),
    (
        "whitelist-directories",
        ["*", "!*/", "!*.py"],
        ["a.py", "a.txt", "src/b.py", "src/c.txt", "src/deep/d.py"],
    ),
    (
        "anchored-whitelist",
        ["/*", "!/src/", "!/README.md"],
        ["a.py", "README.md", "src/a.py", "src/deep/b.py", "lib/c.py", "lib/README.md"],
    ),
    (
        "double-star",
        [
            "/**/gen",
            "a/**/b",
            "doc/**",
            "!doc/keep.md",
            "**/*.log",
            "x/**y/z.py",
            "m**n.py",
            "deep/**/",
        ],
        [
            "p/q/gen/x.py",
            "gen/y.py",
            "a/b",
            "a/x/y/b",
            "q/a/b",
            "doc/a.md",
            "doc/keep.md",
            "doc/sub/s.md",
            "r/doc/a.md",
            "app.log",
            "s/t/u.log",
            "x/qy/z.py",
            "x/q/y/z.py",
            "mxn.py",
            "sub/mzzn.py",
            "deep/f.py",
            "deep/e/g.py",
        ],
    ),
    (
        "anchoring",
        ["/root.py", "sub/name.py", "doc/*.txt", "name2.py", "!x/name2.py"],
        [
            "root.py",
            "x/root.py",
            "sub/name.py",
            "y/sub/name.py",
            "doc/a.txt",
            "doc/s/a.txt",
            "q/doc/a.txt",
            "name2.py",
            "x/name2.py",
            "z/x/name2.py",
        ],
    ),
    (
        "single-character",
        ["abc?", "?"],
        ["abcd", "abc", "abcde", "x/abcd", "yy/z.py"],
    ),
    (
        "last-match-wins",
        ["*.py", "!*.py", "*.py", "!keep.py", "keep*", "!"],
        ["a.py", "keep.py", "keeper.txt"],
    ),
    (
        "contents-of-a-directory",
        ["foo/**", "!foo/keep.py", "!foo/sub/", "bar/**/", "**", "!**/*.md"],
        [
            "foo/a.py",
            "foo/keep.py",
            "foo/sub/b.py",
            "x/foo/c.py",
            "bar/d.py",
            "bar/e/f.py",
            "top.md",
            "g/h.md",
        ],
    ),
    (
        "crlf-and-bom",
        "﻿*.tmp\r\nbuild/\r\n!keep.tmp\r\n",
        ["a.tmp", "keep.tmp", "build/x.py", "src/build"],
    ),
]


def _git_ignored(root: Path, home: Path, paths: list[str]) -> set[str]:
    """The subset of ``paths`` git reports as ignored."""
    env = {
        **os.environ,
        # No system or user config, no global excludes file.
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home),
    }
    proc = subprocess.run(
        ["git", "-c", "core.ignorecase=false", "-C", str(root)]
        + ["check-ignore", "--no-index", "-z", "--stdin"],
        input="\0".join(paths).encode() + b"\0",
        capture_output=True,
        env=env,
        check=False,
    )
    assert proc.returncode in (0, 1), proc.stderr.decode(errors="replace")
    return {p for p in proc.stdout.decode().split("\0") if p}


@pytest.mark.parametrize(("lines", "files"), [c[1:] for c in CASES], ids=[c[0] for c in CASES])
def test_matches_agrees_with_git_check_ignore(tmp_path, lines, files):
    root, home = tmp_path / "repo", tmp_path / "home"
    home.mkdir()
    for rel in files:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x\n", encoding="utf-8")
    content = lines if isinstance(lines, str) else "\n".join(lines) + "\n"
    (root / ".gitignore").write_bytes(content.encode("utf-8"))
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    (root / ".git" / "info").mkdir(parents=True, exist_ok=True)
    (root / ".git" / "info" / "exclude").write_text("", encoding="utf-8")

    dirs = sorted({"/".join(f.split("/")[:i]) for f in files for i in range(1, f.count("/") + 1)})
    git_says = _git_ignored(root, home, files + dirs)
    patterns = load_patterns(root, ".gitignore")

    mismatches = [
        f"{kind} {path!r}: git={path in git_says} neuralmind={path not in git_says}"
        for kind, paths, is_dir in (("file", files, False), ("dir ", dirs, True))
        for path in paths
        if matches(path, patterns, is_dir=is_dir) != (path in git_says)
    ]
    assert not mismatches, f"patterns {patterns!r}:\n" + "\n".join(mismatches)


def test_trailing_slash_in_the_path_marks_a_directory():
    assert matches("build/", ("build/",))
    assert matches("build", ("build/",), is_dir=True)
    assert not matches("build", ("build/",), is_dir=False)


def test_unknown_type_never_prunes_a_directory_git_would_enter():
    # A directory walk that doesn't say what it is asking about must still
    # enter src/, which `!/src/` re-includes; as a file, `src` stays ignored.
    patterns = ("/*", "!/src/")
    assert not matches("src", patterns)
    assert matches("src", patterns, is_dir=False)
    assert matches("lib", patterns)
    assert not matches("build", ("build/",))  # could be a plain file git keeps
    assert matches("build/x.py", ("build/",))
    assert matches("logs/keep.py", ("logs/", "!logs/keep.py"))


@pytest.mark.parametrize(
    ("gitignore", "files"),
    [
        (
            "[Oo]bj/\n[Bb]in/\nout/\n!out/keep.py\nlogs/*\n!logs/keep.py\n",
            ["app.py", "src/App.cs", "obj/Debug/A.cs", "src/Bin/B.cs"]
            + ["out/keep.py", "out/x.py", "logs/keep.py", "logs/y.py"],
        ),
        ("/*\n!/src/\n", ["a.py", "src/b.py", "src/deep/c.py", "lib/d.py"]),
    ],
    ids=["classes-and-excluded-parents", "anchored-whitelist"],
)
def test_directory_walk_outside_git_indexes_what_git_would(tmp_path, gitignore, files):
    from neuralmind import graphgen

    for rel in files:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(gitignore, encoding="utf-8")

    def indexed() -> list[str]:
        found = graphgen._iter_source_files(tmp_path, graphgen._DEFAULT_IGNORES)
        return [f.relative_to(tmp_path).as_posix() for f in found]

    walked = indexed()  # not a repository: the walk applies .gitignore itself
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    assert walked == indexed()  # in a repository git lists the files


def test_pattern_regex_still_matches_paths_under_a_named_directory():
    rx = pattern_regex("[Oo]bj/")
    assert rx.match("obj/Debug/a.cs") and rx.match("src/Obj/b.cs")
    assert not rx.match("obj") and not rx.match("objx/a.cs")
    assert pattern_regex("# comment") is None
