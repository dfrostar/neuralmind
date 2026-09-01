"""Guard the portable skill manifest against version drift and registry rejects.

`skills/neuralmind/SKILL.md` is the copy three external registries read —
Hermes-Agent taps, OpenClaw's ClawHub, and (indirectly) Agent Zero. Its
frontmatter `version` sat at 0.5.2 while the package shipped 3.4.1, because
nothing bumped it and nothing checked. Anyone installing from a registry
would have been told they were running a version three majors old.

release-please now owns that line via `extra-files` + the
`x-release-please-version` annotation. This test is the backstop for the
wiring itself: if the annotation is edited away, or the file drops out of
`extra-files`, the bump silently stops happening again. It also asserts the
two identity rules the Agent Zero index CI enforces on submission, so a
rename is caught here rather than in a third-party PR.

Stdlib-only by repo convention — no PyYAML — so it runs without the full
dep set.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SKILL_PATH = REPO_ROOT / "skills" / "neuralmind" / "SKILL.md"
PLUGIN_PATH = REPO_ROOT / "plugin.yaml"
MANIFEST_PATH = REPO_ROOT / ".release-please-manifest.json"
CONFIG_PATH = REPO_ROOT / "release-please-config.json"

# The extra-files entry is a repo-relative POSIX path in release-please's config.
SKILL_REL = "skills/neuralmind/SKILL.md"

# Agent Zero's a0-plugins index rejects anything outside this shape, and
# requires the folder name submitted there to equal plugin.yaml's `name`.
A0_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")


def _frontmatter(path: Path) -> dict[str, str]:
    """Return top-level scalar frontmatter keys from a SKILL.md.

    Deliberately shallow: nested blocks (tags, runtime, metadata) are skipped
    rather than parsed, because the only fields registries key on are scalars
    and a real YAML parser is not available in the stdlib-only test set.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{path} does not open with a YAML frontmatter fence")
    _, _, rest = text.partition("---\n")
    body, fence, _ = rest.partition("\n---\n")
    if not fence:
        raise AssertionError(f"{path} has an unterminated frontmatter block")

    fields: dict[str, str] = {}
    for line in body.splitlines():
        if not line or line.startswith((" ", "\t", "#")):
            continue  # nested value or comment
        key, sep, value = line.partition(":")
        if not sep:
            continue
        value = value.split(" #", 1)[0].strip()  # drop inline YAML comment
        fields[key.strip()] = value.strip("'\"")
    return fields


def _plugin_name(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("name:"):
            return line.partition(":")[2].split(" #", 1)[0].strip().strip("'\"")
    raise AssertionError(f"{path} has no top-level `name:` key")


def _released_version() -> str:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["."]


class TestSkillVersionTracksTheRelease:
    def test_version_matches_the_release_manifest(self):
        declared = _frontmatter(SKILL_PATH)["version"]
        assert declared == _released_version(), (
            f"{SKILL_REL} advertises v{declared} but the package is "
            f"v{_released_version()}. Registries publish the frontmatter "
            "version verbatim. Do not hand-edit it — release-please bumps it "
            "via extra-files; if it drifted, that wiring is broken."
        )

    def test_version_line_carries_the_release_please_annotation(self):
        """Without the annotation the generic updater silently no-ops."""
        lines = SKILL_PATH.read_text(encoding="utf-8").splitlines()
        version_lines = [ln for ln in lines if ln.startswith("version:")]
        assert len(version_lines) == 1, f"expected one version line, got {version_lines}"
        assert "x-release-please-version" in version_lines[0], (
            "the frontmatter version line lost its `# x-release-please-version` "
            "annotation — release-please will stop bumping it and the file will "
            "drift out of date again"
        )

    def test_skill_is_registered_as_a_release_please_extra_file(self):
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        extra = config["packages"]["."].get("extra-files", [])
        assert SKILL_REL in extra, (
            f"{SKILL_REL} is not in release-please's extra-files, so the "
            "annotation above will never fire"
        )


class TestRegistryIdentityIsStable:
    """The identity fields three registries key on, and a0-plugins CI enforces."""

    def test_required_frontmatter_fields_are_present(self):
        fields = _frontmatter(SKILL_PATH)
        for key in ("name", "description", "version", "author", "license"):
            assert fields.get(key), f"SKILL.md frontmatter is missing `{key}`"

    def test_skill_name_matches_the_plugin_manifest(self):
        skill_name = _frontmatter(SKILL_PATH)["name"]
        plugin_name = _plugin_name(PLUGIN_PATH)
        assert skill_name == plugin_name, (
            f"SKILL.md name `{skill_name}` != plugin.yaml name `{plugin_name}`. "
            "Agent Zero's index requires plugin.yaml's name to equal the folder "
            "submitted to a0-plugins; keeping the skill in step avoids shipping "
            "two different identities for one tool."
        )

    def test_plugin_name_is_a_legal_a0_folder_name(self):
        plugin_name = _plugin_name(PLUGIN_PATH)
        assert A0_NAME_RE.match(plugin_name), (
            f"`{plugin_name}` is not a legal a0-plugins folder name "
            "(lowercase letters, digits and underscores; no leading underscore)"
        )


class TestHostCoverage:
    """The skill is shipped *for* these hosts; it should tell the agent about them."""

    def test_skill_documents_every_target_host(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        for host in ("Hermes-Agent", "OpenClaw", "Agent Zero"):
            assert host in text, f"SKILL.md never mentions {host}, but ships to that ecosystem"


# ---------------------------------------------------------------------------
# Staged a0-plugins index entry (integrations/a0-plugins/neuralmind/).
#
# These re-run agent0ai/a0-plugins' submission CI locally (rules from their
# README @ 05305da) so a reject happens here, not in a third-party PR:
# one folder holding only index.yaml + an optional square <=20KB thumbnail;
# index.yaml <=2000 chars with only title/description/github/tags/screenshots
# (title <=50, description <=500, tags <=5); the `github` repo must carry
# plugin.yaml at its root whose `name` equals the index folder name.
# ---------------------------------------------------------------------------

A0_INDEX_DIR = REPO_ROOT / "integrations" / "a0-plugins" / "neuralmind"
A0_INDEX = A0_INDEX_DIR / "index.yaml"
A0_ALLOWED_FIELDS = {"title", "description", "github", "tags", "screenshots"}
A0_REQUIRED_FIELDS = {"title", "description", "github"}
A0_THUMB_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
A0_THUMB_MAX_BYTES = 20 * 1024


def _index_fields() -> tuple[dict[str, str], dict[str, list[str]]]:
    """Shallow-parse index.yaml: scalar fields and list fields (stdlib-only)."""
    scalars: dict[str, str] = {}
    lists: dict[str, list[str]] = {}
    current: str | None = None
    for line in A0_INDEX.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") and current is not None:
            lists.setdefault(current, []).append(line[4:].strip())
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        current = key
        if value:
            scalars[key] = value
    return scalars, lists


def test_a0_index_folder_holds_only_index_and_thumbnail() -> None:
    assert A0_INDEX.is_file(), "staged submission is missing index.yaml"
    extras = [
        p.name
        for p in A0_INDEX_DIR.iterdir()
        if p.name != "index.yaml" and not (p.stem == "thumbnail" and p.suffix in A0_THUMB_SUFFIXES)
    ]
    assert not extras, (
        "a0-plugins CI rejects folders with extra files (only index.yaml and "
        f"an optional thumbnail are allowed): {extras}"
    )


def test_a0_index_fields_and_lengths() -> None:
    text = A0_INDEX.read_text(encoding="utf-8")
    assert len(text) <= 2000, f"index.yaml is {len(text)} chars; registry cap is 2000"
    scalars, lists = _index_fields()
    fields = set(scalars) | set(lists)
    assert fields <= A0_ALLOWED_FIELDS, f"disallowed field(s): {sorted(fields - A0_ALLOWED_FIELDS)}"
    missing = [k for k in A0_REQUIRED_FIELDS if not scalars.get(k)]
    assert not missing, f"required field(s) empty or absent: {missing}"
    assert len(scalars["title"]) <= 50, f"title is {len(scalars['title'])} chars; cap is 50"
    assert (
        len(scalars["description"]) <= 500
    ), f"description is {len(scalars['description'])} chars; cap is 500"
    assert len(lists.get("tags", [])) <= 5, "registry allows at most 5 tags"
    assert len(lists.get("screenshots", [])) <= 5, "registry allows at most 5 screenshots"


def test_a0_index_github_points_home_and_name_matches_folder() -> None:
    scalars, _ = _index_fields()
    assert (
        scalars["github"].rstrip("/") == "https://github.com/dfrostar/neuralmind"
    ), "index.yaml must point at the repository that carries plugin.yaml at its root"
    assert PLUGIN_PATH.is_file(), "plugin.yaml must sit at the repo root for their CI fetch"
    name_match = re.search(r"^name:\s*(\S+)\s*$", PLUGIN_PATH.read_text(encoding="utf-8"), re.M)
    assert name_match and name_match.group(1) == A0_INDEX_DIR.name, (
        "Agent Zero's index requires plugin.yaml's name to equal the submitted "
        f"folder name ({A0_INDEX_DIR.name!r})"
    )


def test_a0_thumbnail_is_square_and_under_20kb() -> None:
    thumbs = [p for p in A0_INDEX_DIR.iterdir() if p.stem == "thumbnail"]
    if not thumbs:  # thumbnail is optional; the registry generates one if absent
        return
    thumb = thumbs[0]
    size = thumb.stat().st_size
    assert size <= A0_THUMB_MAX_BYTES, f"thumbnail is {size} bytes; registry cap is 20KB"
    if thumb.suffix == ".png":
        import struct

        header = thumb.read_bytes()[:24]
        assert header[:8] == b"\x89PNG\r\n\x1a\n", "thumbnail.png is not a PNG"
        width, height = struct.unpack(">II", header[16:24])
        assert width == height, f"registry requires a square thumbnail; got {width}x{height}"
