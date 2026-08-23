"""Tests for `neuralmind ingest-content` — the content-corpus indexer.

Covers the failure a book corpus actually hit: the project root resolving
up to the enclosing git repo, so ingesting `book/chapters` indexed the
whole repository. Plus the flags added alongside the fix — incremental
re-runs, `--content-only`, `--dry-run`, `--timeout`, and the chunk-size
environment variables.

The vector backend is faked throughout: these assert CLI behavior, not
embedding quality, and they must run without turbovec or chromadb.
"""

import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from neuralmind.cli import (
    _delete_content_nodes,
    _ensure_content_project_marker,
    _env_int_option,
    _resolve_chunk_params,
    _resolve_project_path,
)
from neuralmind.content_manifest import ContentManifest


class FakeEmbedder:
    """Stands in for the vector backend. Records what it was asked to embed."""

    def __init__(self, graph_nodes=None):
        self.nodes = list(graph_nodes or [])
        self._graph_nodes = list(graph_nodes or [])
        self.embedded: list[list[dict]] = []
        self.deleted: list[str] = []
        self.load_graph_calls = 0

    def load_graph(self) -> bool:
        self.load_graph_calls += 1
        return bool(self._graph_nodes)

    def embed_content(self, nodes, force: bool = False):
        self.embedded.append(list(nodes))
        return {"added": len(nodes), "updated": 0, "skipped": 0}

    def delete_nodes(self, node_ids) -> int:
        ids = list(node_ids)
        self.deleted.extend(ids)
        return len(ids)

    @property
    def embedded_ids(self) -> list[str]:
        return [n.get("id", "") for batch in self.embedded for n in batch]


class FakeMind:
    def __init__(self, graph_nodes=None):
        self.embedder = FakeEmbedder(graph_nodes)
        self._built = True


@pytest.fixture
def fake_backend(monkeypatch):
    """Replace create_mind so no real embedding backend is constructed."""
    created: dict = {}

    def _create_mind(project_path, auto_build=True):
        mind = FakeMind(created.get("graph_nodes"))
        created["mind"] = mind
        created["project_path"] = project_path
        created["auto_build"] = auto_build
        return mind

    monkeypatch.setattr("neuralmind.core.create_mind", _create_mind)
    return created


@pytest.fixture
def book_repo(tmp_path: Path) -> Path:
    """A git repo with code at the root and a book corpus in a subdirectory.

    This is the shape that misresolved: `.git` at the top, prose below.
    """
    (tmp_path / ".git").mkdir()
    (tmp_path / "app.py").write_text("def handler():\n    return 1\n")
    chapters = tmp_path / "book" / "chapters"
    chapters.mkdir(parents=True)
    for i in (1, 2, 3):
        (chapters / f"ch{i}.md").write_text(
            f"# Chapter {i}\n\n" + ("Prose about retrieval and chunking. " * 40)
        )
    return tmp_path


def run_cli(monkeypatch, *argv: str) -> int:
    """Invoke the real CLI parser + dispatch. Returns the exit code."""
    from neuralmind.cli import main

    monkeypatch.setattr(sys, "argv", ["neuralmind", *argv])
    try:
        main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


class TestProjectPathResolution:
    def test_explicit_project_path_wins(self, book_repo: Path):
        target = book_repo / "book" / "chapters"
        args = Namespace(project_path=str(target))
        assert _resolve_project_path(target, args) == target

    def test_directory_with_its_own_marker_beats_the_git_root(self, book_repo: Path):
        """A folder carrying .neuralmind/ is its own project, even inside a repo."""
        book = book_repo / "book"
        (book / ".neuralmind").mkdir()
        (book / ".neuralmind" / "index_ir.json").write_text("{}")
        resolved = _resolve_project_path(book / "chapters", Namespace(project_path=None))
        assert resolved == book

    def test_target_is_consulted_before_the_cwd(self, tmp_path: Path, monkeypatch):
        """Running from project A while ingesting into project B must not
        silently index into A."""
        project_a = tmp_path / "a"
        project_b = tmp_path / "b" / "docs"
        (project_a / ".neuralmind").mkdir(parents=True)
        (project_a / ".neuralmind" / "index_ir.json").write_text("{}")
        (project_b / ".neuralmind").mkdir(parents=True)
        (project_b / ".neuralmind" / "index_ir.json").write_text("{}")
        monkeypatch.chdir(project_a)

        resolved = _resolve_project_path(project_b, Namespace(project_path=None))
        assert resolved == project_b

    def test_falls_back_to_cwd_when_the_target_has_no_marker(self, tmp_path: Path, monkeypatch):
        project = tmp_path / "proj"
        (project / ".neuralmind").mkdir(parents=True)
        (project / ".neuralmind" / "index_ir.json").write_text("{}")
        loose = tmp_path / "loose"
        loose.mkdir()
        monkeypatch.chdir(project)

        assert _resolve_project_path(loose, Namespace(project_path=None)) == project

    def test_returns_none_when_nothing_is_marked(self, tmp_path: Path, monkeypatch):
        loose = tmp_path / "loose"
        loose.mkdir()
        monkeypatch.chdir(loose)
        # tmp_path has no .git/.neuralmind anywhere up to /, on any sane runner.
        assert _resolve_project_path(loose, Namespace(project_path=None)) in (None, loose)


class TestChunkParams:
    def test_defaults(self):
        assert _resolve_chunk_params(Namespace(chunk_size=None, overlap=None)) == (500, 50)

    def test_env_vars_apply(self, monkeypatch):
        monkeypatch.setenv("NEURALMIND_CHUNK_SIZE", "1200")
        monkeypatch.setenv("NEURALMIND_OVERLAP", "100")
        assert _resolve_chunk_params(Namespace(chunk_size=None, overlap=None)) == (1200, 100)

    def test_flags_beat_env_vars(self, monkeypatch):
        monkeypatch.setenv("NEURALMIND_CHUNK_SIZE", "1200")
        assert _resolve_chunk_params(Namespace(chunk_size=300, overlap=None)) == (300, 50)

    def test_malformed_env_warns_and_falls_back(self, monkeypatch, capsys):
        monkeypatch.setenv("NEURALMIND_CHUNK_SIZE", "not-a-number")
        assert _resolve_chunk_params(Namespace(chunk_size=None, overlap=None)) == (500, 50)
        assert "not an integer" in capsys.readouterr().err

    def test_overlap_at_or_above_chunk_size_is_rejected(self, capsys):
        """The chunker would loop forever; fail before touching the project."""
        with pytest.raises(SystemExit) as exc:
            _resolve_chunk_params(Namespace(chunk_size=100, overlap=200))
        assert exc.value.code == 2
        assert "must be greater than overlap" in capsys.readouterr().err

    @pytest.mark.parametrize(
        ("raw", "expected"), [("", 7), ("  ", 7), ("-3", 7), ("0", 0), ("42", 42)]
    )
    def test_env_int_option(self, monkeypatch, raw, expected):
        monkeypatch.setenv("NM_TEST_OPT", raw)
        assert _env_int_option("NM_TEST_OPT", 7, minimum=0) == expected


class TestContentProjectMarker:
    def test_writes_a_loadable_ir(self, tmp_path: Path):
        """The hand-rolled workaround wrote `{"is_content_project": true}`,
        which is not a loadable IR. This writes a real, empty one."""
        from neuralmind import ir as ir_mod

        marker = _ensure_content_project_marker(tmp_path)
        assert marker == tmp_path / ".neuralmind" / "index_ir.json"

        index = ir_mod.IndexIR.from_dict(json.loads(marker.read_text()))
        assert index.nodes == []
        assert index.source_backend == "content"

    def test_does_not_clobber_an_existing_index(self, tmp_path: Path):
        marker = tmp_path / ".neuralmind" / "index_ir.json"
        marker.parent.mkdir(parents=True)
        marker.write_text('{"ir_version": 1, "nodes": [{"id": "keep"}]}')
        _ensure_content_project_marker(tmp_path)
        assert "keep" in marker.read_text()


class TestDeleteContentNodes:
    def test_removes_from_backend_and_node_list(self):
        mind = FakeMind()
        mind.embedder.nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        removed = _delete_content_nodes(mind, ["a", "c"])
        assert removed == 2
        assert mind.embedder.deleted == ["a", "c"]
        assert [n["id"] for n in mind.embedder.nodes] == ["b"]

    def test_empty_list_is_a_noop(self):
        mind = FakeMind()
        assert _delete_content_nodes(mind, []) == 0

    def test_backend_without_delete_support_still_prunes_locally(self):
        class _Old(FakeEmbedder):
            delete_nodes = None

        mind = FakeMind()
        mind.embedder = _Old()
        mind.embedder.nodes = [{"id": "a"}, {"id": "b"}]
        assert _delete_content_nodes(mind, ["a"]) == 0
        assert [n["id"] for n in mind.embedder.nodes] == ["b"]


class TestDryRun:
    def test_lists_files_and_chunk_counts_without_embedding(
        self, book_repo: Path, fake_backend, monkeypatch, capsys
    ):
        chapters = book_repo / "book" / "chapters"
        code = run_cli(
            monkeypatch,
            "ingest-content",
            str(chapters),
            "--project-path",
            str(book_repo / "book"),
            "--dry-run",
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "would-index" in out
        assert "ch1.md" in out and "ch3.md" in out
        assert "Nothing was written." in out
        # No backend was constructed and no manifest written.
        assert "mind" not in fake_backend
        assert not (book_repo / "book" / ".neuralmind" / "content_manifest.json").exists()

    def test_json_dry_run_is_machine_readable(
        self, book_repo: Path, fake_backend, monkeypatch, capsys
    ):
        code = run_cli(
            monkeypatch,
            "ingest-content",
            str(book_repo / "book" / "chapters"),
            "--project-path",
            str(book_repo / "book"),
            "--dry-run",
            "--json",
        )
        payload = json.loads(capsys.readouterr().out)
        assert code == 0
        assert payload["dry_run"] is True
        assert payload["files_total"] == 3
        assert payload["files_would_index"] == 3
        assert payload["chunks_would_embed"] > 0
        assert len(payload["files"]) == 3


class TestIngest:
    def test_content_only_skips_the_code_graph_build(
        self, book_repo: Path, fake_backend, monkeypatch
    ):
        run_cli(
            monkeypatch,
            "ingest-content",
            str(book_repo / "book" / "chapters"),
            "--project-path",
            str(book_repo / "book"),
            "--content-only",
            "--no-progress",
            "--quiet",
        )
        assert fake_backend["auto_build"] is False
        # ...and never leaves the seed .py file the old path needed.
        assert not (book_repo / "book" / "_content_seed.py").exists()

    def test_default_path_still_builds_the_code_graph(
        self, book_repo: Path, fake_backend, monkeypatch
    ):
        run_cli(
            monkeypatch,
            "ingest-content",
            str(book_repo / "book" / "chapters"),
            "--project-path",
            str(book_repo / "book"),
            "--no-progress",
            "--quiet",
        )
        assert fake_backend["auto_build"] is True

    def test_first_run_embeds_everything_and_records_a_manifest(
        self, book_repo: Path, fake_backend, monkeypatch, capsys
    ):
        book = book_repo / "book"
        code = run_cli(
            monkeypatch,
            "ingest-content",
            str(book / "chapters"),
            "--project-path",
            str(book),
            "--content-only",
            "--no-progress",
            "--json",
        )
        payload = json.loads(capsys.readouterr().out)
        assert code == 0
        assert payload["files_processed"] == 3
        assert payload["files_skipped"] == 0
        assert payload["total_nodes"] > 0

        manifest = ContentManifest.load(book)
        assert len(manifest) == 3

    def test_second_run_skips_unchanged_files(
        self, book_repo: Path, fake_backend, monkeypatch, capsys
    ):
        book = book_repo / "book"
        argv = (
            "ingest-content",
            str(book / "chapters"),
            "--project-path",
            str(book),
            "--content-only",
            "--no-progress",
            "--json",
        )
        run_cli(monkeypatch, *argv)
        capsys.readouterr()

        run_cli(monkeypatch, *argv)
        payload = json.loads(capsys.readouterr().out)
        assert payload["files_processed"] == 0
        assert payload["files_skipped"] == 3
        assert payload["embed_time_seconds"] == 0.0
        # The corpus is still fully accounted for, just not re-embedded.
        assert payload["total_chunks"] > 0

    def test_only_the_edited_file_is_re_embedded(
        self, book_repo: Path, fake_backend, monkeypatch, capsys
    ):
        book = book_repo / "book"
        argv = (
            "ingest-content",
            str(book / "chapters"),
            "--project-path",
            str(book),
            "--content-only",
            "--no-progress",
            "--json",
        )
        run_cli(monkeypatch, *argv)
        capsys.readouterr()

        (book / "chapters" / "ch2.md").write_text("# Chapter 2\n\nCompletely rewritten.\n")
        run_cli(monkeypatch, *argv)
        payload = json.loads(capsys.readouterr().out)
        assert payload["files_processed"] == 1
        assert payload["files_skipped"] == 2
        assert all("ch2" in nid for nid in fake_backend["mind"].embedder.embedded_ids)

    def test_force_re_embeds_everything(self, book_repo: Path, fake_backend, monkeypatch, capsys):
        book = book_repo / "book"
        argv = (
            "ingest-content",
            str(book / "chapters"),
            "--project-path",
            str(book),
            "--content-only",
            "--no-progress",
            "--json",
        )
        run_cli(monkeypatch, *argv)
        capsys.readouterr()

        run_cli(monkeypatch, *argv, "--force")
        payload = json.loads(capsys.readouterr().out)
        assert payload["files_processed"] == 3
        assert payload["files_skipped"] == 0
        assert payload["incremental"] is False

    def test_shrunk_file_evicts_its_orphaned_chunks(
        self, book_repo: Path, fake_backend, monkeypatch, capsys
    ):
        book = book_repo / "book"
        argv = (
            "ingest-content",
            str(book / "chapters"),
            "--project-path",
            str(book),
            "--content-only",
            "--no-progress",
            "--json",
        )
        run_cli(monkeypatch, *argv)
        capsys.readouterr()

        (book / "chapters" / "ch1.md").write_text("# Chapter 1\n\nTiny.\n")
        run_cli(monkeypatch, *argv)
        payload = json.loads(capsys.readouterr().out)
        assert payload["orphans_removed"] > 0

    def test_deleted_file_is_evicted_from_the_index(
        self, book_repo: Path, fake_backend, monkeypatch, capsys
    ):
        book = book_repo / "book"
        argv = (
            "ingest-content",
            str(book / "chapters"),
            "--project-path",
            str(book),
            "--content-only",
            "--no-progress",
            "--json",
        )
        run_cli(monkeypatch, *argv)
        capsys.readouterr()

        (book / "chapters" / "ch3.md").unlink()
        run_cli(monkeypatch, *argv)
        payload = json.loads(capsys.readouterr().out)
        assert payload["orphans_removed"] > 0
        assert len(ContentManifest.load(book)) == 2

    def test_changing_chunk_size_invalidates_the_manifest(
        self, book_repo: Path, fake_backend, monkeypatch, capsys
    ):
        book = book_repo / "book"
        base = (
            "ingest-content",
            str(book / "chapters"),
            "--project-path",
            str(book),
            "--content-only",
            "--no-progress",
            "--json",
        )
        run_cli(monkeypatch, *base)
        capsys.readouterr()

        run_cli(monkeypatch, *base, "--chunk-size", "900")
        payload = json.loads(capsys.readouterr().out)
        assert payload["files_processed"] == 3
        assert payload["chunk_size"] == 900

    def test_empty_directory_exits_cleanly(self, tmp_path: Path, monkeypatch, capsys):
        empty = tmp_path / "empty"
        empty.mkdir()
        code = run_cli(monkeypatch, "ingest-content", str(empty), "--json")
        payload = json.loads(capsys.readouterr().out)
        assert code == 0
        assert payload["files_processed"] == 0
        assert payload["success"] is True

    def test_empty_corpus_json_matches_the_normal_shape(
        self, book_repo: Path, tmp_path: Path, monkeypatch, capsys
    ):
        """A consumer shouldn't have to special-case an empty corpus."""
        book = book_repo / "book"
        run_cli(
            monkeypatch,
            "ingest-content",
            str(book / "chapters"),
            "--project-path",
            str(book),
            "--content-only",
            "--no-progress",
            "--dry-run",
            "--json",
        )
        capsys.readouterr()

        empty = tmp_path / "empty"
        empty.mkdir()
        run_cli(monkeypatch, "ingest-content", str(empty), "--json")
        empty_payload = json.loads(capsys.readouterr().out)

        expected = {
            "success",
            "project_path",
            "content_only",
            "incremental",
            "files_processed",
            "files_skipped",
            "files_total",
            "total_chunks",
            "chunks_embedded",
            "total_nodes",
            "orphans_removed",
            "chunk_size",
            "overlap",
            "wall_time_seconds",
            "embed_time_seconds",
            "timed_out",
            "errors",
        }
        assert expected <= set(empty_payload)

    def test_missing_path_errors(self, tmp_path: Path, monkeypatch, capsys):
        code = run_cli(monkeypatch, "ingest-content", str(tmp_path / "nope"))
        assert code == 1
        assert "path not found" in capsys.readouterr().err

    def test_timeout_zero_means_no_limit(self, book_repo: Path, fake_backend, monkeypatch, capsys):
        book = book_repo / "book"
        code = run_cli(
            monkeypatch,
            "ingest-content",
            str(book / "chapters"),
            "--project-path",
            str(book),
            "--content-only",
            "--no-progress",
            "--timeout",
            "0",
            "--json",
        )
        payload = json.loads(capsys.readouterr().out)
        assert code == 0
        assert payload["timed_out"] is False
        assert payload["files_processed"] == 3

    def test_timeout_stops_cleanly_and_keeps_what_it_indexed(
        self, book_repo: Path, fake_backend, monkeypatch, capsys
    ):
        """A slow corpus stops at the deadline, reports it, and still writes
        a manifest so the next run resumes instead of starting over."""
        book = book_repo / "book"
        slow = FakeMind()
        original_embed = slow.embedder.embed_content

        def _slow_embed(nodes, force=False):
            import time as _time

            _time.sleep(0.7)
            return original_embed(nodes, force)

        slow.embedder.embed_content = _slow_embed
        monkeypatch.setattr("neuralmind.core.create_mind", lambda *a, **k: slow)

        code = run_cli(
            monkeypatch,
            "ingest-content",
            str(book / "chapters"),
            "--project-path",
            str(book),
            "--content-only",
            "--no-progress",
            "--timeout",
            "1",
            "--json",
        )
        payload = json.loads(capsys.readouterr().out)
        assert code == 1
        assert payload["timed_out"] is True
        assert payload["success"] is False
        assert 0 < payload["files_processed"] < 3
        # What did land is recorded, so the next run picks up from there.
        assert 0 < len(ContentManifest.load(book)) < 3

    def test_timeout_does_not_evict_files_it_never_reached(
        self, book_repo: Path, fake_backend, monkeypatch, capsys
    ):
        """Pruning on a partial run would delete chapters that are simply
        still queued."""
        book = book_repo / "book"
        argv = (
            "ingest-content",
            str(book / "chapters"),
            "--project-path",
            str(book),
            "--content-only",
            "--no-progress",
            "--json",
        )
        run_cli(monkeypatch, *argv)
        capsys.readouterr()

        slow = FakeMind()

        def _slow_embed(nodes, force=False):
            import time as _time

            _time.sleep(0.7)
            return {"added": len(nodes), "updated": 0, "skipped": 0}

        slow.embedder.embed_content = _slow_embed
        monkeypatch.setattr("neuralmind.core.create_mind", lambda *a, **k: slow)

        run_cli(monkeypatch, *argv, "--force", "--timeout", "1")
        payload = json.loads(capsys.readouterr().out)
        assert payload["timed_out"] is True
        assert payload["orphans_removed"] == 0
        assert len(ContentManifest.load(book)) == 3

    def test_warns_when_resolving_to_an_unindexed_git_root(
        self, book_repo: Path, fake_backend, monkeypatch, capsys
    ):
        """The silent version of this is what indexed a whole repo."""
        run_cli(
            monkeypatch,
            "ingest-content",
            str(book_repo / "book" / "chapters"),
            "--content-only",
            "--no-progress",
            "--quiet",
        )
        err = capsys.readouterr().err
        assert "--project-path" in err
        assert str(book_repo) in err

    def test_single_file_suggestion_names_a_directory(
        self, book_repo: Path, fake_backend, monkeypatch, capsys
    ):
        """--project-path takes a directory; suggesting the .md file itself
        would hand back an unusable command."""
        run_cli(
            monkeypatch,
            "ingest-content",
            str(book_repo / "book" / "chapters" / "ch1.md"),
            "--content-only",
            "--no-progress",
            "--quiet",
        )
        err = capsys.readouterr().err
        assert "--project-path" in err
        assert str(book_repo / "book" / "chapters") in err
        assert "--project-path " + str(book_repo / "book" / "chapters" / "ch1.md") not in err

    def test_no_warning_when_the_root_is_explicit(
        self, book_repo: Path, fake_backend, monkeypatch, capsys
    ):
        run_cli(
            monkeypatch,
            "ingest-content",
            str(book_repo / "book" / "chapters"),
            "--project-path",
            str(book_repo / "book"),
            "--content-only",
            "--no-progress",
            "--quiet",
        )
        assert "--project-path" not in capsys.readouterr().err


class TestVerbose:
    def test_verbose_reports_per_file_detail_on_stderr(
        self, book_repo: Path, fake_backend, monkeypatch, capsys
    ):
        book = book_repo / "book"
        run_cli(
            monkeypatch,
            "ingest-content",
            str(book / "chapters"),
            "--project-path",
            str(book),
            "--content-only",
            "--no-progress",
            "--verbose",
        )
        err = capsys.readouterr().err
        assert "project root:" in err
        assert "chunk size 500, overlap 50" in err
        assert "ch1.md:" in err

    def test_verbose_keeps_json_stdout_clean(
        self, book_repo: Path, fake_backend, monkeypatch, capsys
    ):
        book = book_repo / "book"
        run_cli(
            monkeypatch,
            "ingest-content",
            str(book / "chapters"),
            "--project-path",
            str(book),
            "--content-only",
            "--no-progress",
            "--verbose",
            "--json",
        )
        # Parses cleanly: diagnostics never leaked onto stdout.
        json.loads(capsys.readouterr().out)
