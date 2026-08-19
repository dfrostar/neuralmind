"""Tests for commit-time pattern-drift detection (neuralmind/drift.py).

Stdlib-only, matching the rest of the synapse/structural/cohesion layer:
these operate on plain graph dicts and diff text, no ChromaDB or
tree-sitter required.
"""

from __future__ import annotations

from neuralmind.drift import (
    DriftFinding,
    GraphView,
    check_project,
    find_drift,
    format_drift,
    parse_diff_hunks,
    peer_group,
)

# --------------------------------------------------------------------- #
# Fixture: ten endpoint handlers that all verify a session, plus one
# that doesn't — the same "handler #11" shape cohesion.py's own tests
# use, but built as a graph.json rather than a bare neighbor dict.
# --------------------------------------------------------------------- #


def _handler_graph(*, drop_verify_from: str | None = "handler_10"):
    nodes = [{"id": "routes.py", "label": "routes.py", "file_type": "file"}]
    links = []
    for i in range(1, 11):
        name = f"handler_{i}"
        nodes.append(
            {
                "id": name,
                "label": f"{name}()",
                "file_type": "code",
                "source_file": "routes.py",
                "source_location": f"L{i * 10}",
            }
        )
        links.append({"source": "routes.py", "target": name, "relation": "contains"})
        if name != drop_verify_from:
            links.append({"source": name, "target": "verify_session", "relation": "calls"})
    nodes.append({"id": "verify_session", "label": "verify_session()", "file_type": "code"})
    return {"nodes": nodes, "links": links, "generated_by": "test-fixture"}


def _ranges_for_line(line: int, path: str = "routes.py"):
    return {path: [(line, line)]}


class TestParseDiffHunks:
    def test_single_hunk(self):
        diff = (
            "diff --git a/routes.py b/routes.py\n"
            "index abc..def 100644\n"
            "--- a/routes.py\n"
            "+++ b/routes.py\n"
            "@@ -10,0 +10,3 @@\n"
            "+def handler_10():\n"
            "+    pass\n"
        )
        ranges = parse_diff_hunks(diff)
        assert ranges == {"routes.py": [(10, 12)]}

    def test_deleted_file_is_skipped(self):
        diff = "diff --git a/gone.py b/gone.py\n--- a/gone.py\n+++ /dev/null\n@@ -1,3 +0,0 @@\n"
        assert parse_diff_hunks(diff) == {}

    def test_pure_deletion_hunk_is_skipped(self):
        # New-side count of 0: nothing added, nothing to attribute.
        diff = "--- a/f.py\n+++ b/f.py\n@@ -5,3 +5,0 @@\n"
        assert parse_diff_hunks(diff) == {}

    def test_multiple_files(self):
        diff = "--- a/a.py\n+++ b/a.py\n@@ -1,0 +1,2 @@\n--- a/b.py\n+++ b/b.py\n@@ -20 +20 @@\n"
        ranges = parse_diff_hunks(diff)
        assert ranges == {"a.py": [(1, 2)], "b.py": [(20, 20)]}

    def test_empty_diff(self):
        assert parse_diff_hunks("") == {}


class TestGraphView:
    def test_symbols_for_ranges_maps_line_to_owning_symbol(self):
        view = GraphView(_handler_graph())
        hits = view.symbols_for_ranges(_ranges_for_line(100))
        assert hits == ["handler_10"]

    def test_line_before_first_symbol_maps_to_nothing(self):
        view = GraphView(_handler_graph())
        assert view.symbols_for_ranges(_ranges_for_line(1)) == []

    def test_unknown_file_maps_to_nothing(self):
        view = GraphView(_handler_graph())
        assert view.symbols_for_ranges({"nope.py": [(1, 5)]}) == []

    def test_associates_uses_forward_calls_view(self):
        view = GraphView(_handler_graph())
        assert view.associates("handler_1") == [("verify_session", 1.0)]
        # verify_session is only ever a callee, never a caller in this graph.
        assert view.associates("verify_session") == []


class TestPeerGroup:
    def test_groups_by_shared_container(self):
        view = GraphView(_handler_graph())
        group = peer_group(view, "handler_10")
        assert set(group) == {f"handler_{i}" for i in range(1, 11)}

    def test_no_container_is_empty(self):
        view = GraphView(_handler_graph())
        assert peer_group(view, "verify_session") == []

    def test_too_few_siblings_is_empty(self):
        graph = {
            "nodes": [
                {"id": "f.py", "label": "f.py", "file_type": "file"},
                {
                    "id": "only_one",
                    "label": "only_one()",
                    "file_type": "code",
                    "source_file": "f.py",
                    "source_location": "L1",
                },
            ],
            "links": [{"source": "f.py", "target": "only_one", "relation": "contains"}],
        }
        view = GraphView(graph)
        assert peer_group(view, "only_one") == []

    def test_role_token_narrows_group(self):
        # create_endpoint / update_endpoint / delete_endpoint share "endpoint";
        # a stray helper() in the same file must not join their peer group.
        nodes = [{"id": "f.py", "label": "f.py", "file_type": "file"}]
        links = []
        names = ["create_endpoint", "update_endpoint", "delete_endpoint", "read_endpoint", "helper"]
        for i, name in enumerate(names):
            nodes.append(
                {
                    "id": name,
                    "label": f"{name}()",
                    "file_type": "code",
                    "source_file": "f.py",
                    "source_location": f"L{i * 10 + 1}",
                }
            )
            links.append({"source": "f.py", "target": name, "relation": "contains"})
        view = GraphView({"nodes": nodes, "links": links})
        group = peer_group(view, "create_endpoint", min_peers=3)
        assert set(group) == {
            "create_endpoint",
            "update_endpoint",
            "delete_endpoint",
            "read_endpoint",
        }
        assert "helper" not in group


class TestFindDrift:
    def test_flags_the_handler_that_skips_verify_session(self):
        graph = _handler_graph(drop_verify_from="handler_10")
        findings = find_drift(graph, _ranges_for_line(100), cohesion=0.6, min_peers=3)
        assert len(findings) == 1
        finding = findings[0]
        assert finding.node == "handler_10"
        assert finding.associate == "verify_session"
        assert finding.peers == 9
        assert finding.group_size == 10

    def test_consistent_change_is_quiet(self):
        # handler_10 keeps its call to verify_session — nothing to flag.
        graph = _handler_graph(drop_verify_from=None)
        findings = find_drift(graph, _ranges_for_line(100))
        assert findings == []

    def test_only_reports_symbols_actually_in_the_diff(self):
        # handler_10 is the pre-existing outlier, but the diff only touches
        # handler_5 — a compliant handler. Nothing should be blamed.
        graph = _handler_graph(drop_verify_from="handler_10")
        findings = find_drift(graph, _ranges_for_line(50))
        assert findings == []

    def test_empty_ranges_yields_no_findings(self):
        graph = _handler_graph(drop_verify_from="handler_10")
        assert find_drift(graph, {}) == []

    def test_cold_graph_yields_no_findings(self):
        assert find_drift({"nodes": [], "links": []}, _ranges_for_line(10)) == []

    def test_max_findings_caps_output(self):
        graph = _handler_graph(drop_verify_from="handler_10")
        ranges = _ranges_for_line(100)
        findings = find_drift(graph, ranges, max_findings=0)
        assert findings == []


class TestFormatDrift:
    def test_empty_findings_render_empty_string(self):
        assert format_drift([]) == ""

    def test_warn_mode_mentions_proceeding(self):
        finding = DriftFinding(
            node="handler_10",
            label="handler_10()",
            source_file="routes.py",
            line=100,
            associate="verify_session",
            associate_label="verify_session()",
            peers=9,
            group_size=10,
        )
        text = format_drift([finding], strict=False)
        assert "routes.py:100" in text
        assert "handler_10()" in text
        assert "verify_session()" in text
        assert "proceeds" in text

    def test_strict_mode_mentions_blocked(self):
        finding = DriftFinding(
            node="handler_10",
            label="handler_10()",
            source_file="routes.py",
            line=100,
            associate="verify_session",
            associate_label="verify_session()",
            peers=9,
            group_size=10,
        )
        text = format_drift([finding], strict=True)
        assert "blocked" in text.lower()

    def test_share_property(self):
        finding = DriftFinding(
            node="n",
            label="n",
            source_file="f.py",
            line=1,
            associate="a",
            associate_label="a",
            peers=9,
            group_size=10,
        )
        assert finding.share == 1.0  # 9 of 9 *other* members

    def test_to_dict_roundtrip(self):
        finding = DriftFinding(
            node="n",
            label="n()",
            source_file="f.py",
            line=5,
            associate="a",
            associate_label="a()",
            peers=3,
            group_size=4,
        )
        d = finding.to_dict()
        assert d["node"] == "n"
        assert d["skips"] == "a"
        assert d["share"] == 1.0


class TestCheckProject:
    def test_no_git_repo_yields_empty_result(self, tmp_path):
        result = check_project(str(tmp_path))
        assert result["findings"] == []
        assert result["changed_files"] == []

    def test_missing_graph_is_reported(self, tmp_path):
        import subprocess

        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=t@t.com",
                "-c",
                "user.name=t",
                "commit",
                "--allow-empty",
                "-m",
                "init",
            ],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "a.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "a.py"], cwd=tmp_path, check=True, capture_output=True)
        result = check_project(str(tmp_path), staged=True, refresh=False)
        assert result["graph"] == "missing"
        assert result["changed_files"] == ["a.py"]
