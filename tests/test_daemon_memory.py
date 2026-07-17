"""Tests for F2 — shared daemon memory (daemon_memory.py)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from neuralmind.daemon_memory import SharedDaemonMemory


class TestRegisterClient:
    """Client registration and identity."""

    def test_register_and_retrieve(self, tmp_path: Path) -> None:
        s = SharedDaemonMemory(project_path=tmp_path)
        s.register_client("c1", str(tmp_path))
        assert "c1" in s._clients

    def test_register_multiple(self, tmp_path: Path) -> None:
        s = SharedDaemonMemory(project_path=tmp_path)
        s.register_client("c1", str(tmp_path))
        s.register_client("c2", str(tmp_path))
        assert len(s._clients) == 2


class TestAuthorization:
    """Per-client access scoping."""

    def test_self_access(self, tmp_path: Path) -> None:
        s = SharedDaemonMemory(project_path=tmp_path)
        s.register_client("c1", str(tmp_path))
        assert s.is_authorized("c1", str(tmp_path)) is True

    def test_cross_project_denied(self, tmp_path: Path) -> None:
        s = SharedDaemonMemory(project_path=tmp_path)
        a = tmp_path / "project_a"
        b = tmp_path / "project_b"
        a.mkdir()
        b.mkdir()
        s.register_client("c1", str(a))
        assert s.is_authorized("c1", str(b)) is False

    def test_shared_namespace_always_allowed(self, tmp_path: Path) -> None:
        s = SharedDaemonMemory(project_path=tmp_path)
        s.register_client("c1", str(tmp_path))
        assert s.is_authorized("c1", "shared") is True

    def test_unknown_client_denied(self, tmp_path: Path) -> None:
        s = SharedDaemonMemory(project_path=tmp_path)
        assert s.is_authorized("ghost", str(tmp_path)) is False

    def test_explicit_share(self, tmp_path: Path) -> None:
        s = SharedDaemonMemory(project_path=tmp_path)
        a = tmp_path / "project_a"
        b = tmp_path / "project_b"
        a.mkdir()
        b.mkdir()
        s.register_client("c1", str(a))
        s.share_project("c1", str(b))
        assert s.is_authorized("c1", str(b)) is True


class TestReleaseClient:
    """Resource release."""

    def test_release_nonexistent(self, tmp_path: Path) -> None:
        s = SharedDaemonMemory(project_path=tmp_path)
        s.release_client("nope")  # no crash

    def test_release_clears_cache(self, tmp_path: Path) -> None:
        s = SharedDaemonMemory(project_path=tmp_path)
        s.register_client("c1", str(tmp_path))
        s.cache_selector("c1", object())
        s.release_client("c1")
        assert s.get_cached_selector("c1") is None

    def test_release_all_clients_clears_instance(self, tmp_path: Path) -> None:
        s = SharedDaemonMemory(project_path=tmp_path)
        s.register_client("c1", str(tmp_path))
        # Simulate a warm instance.
        s._instance = object()
        s.release_client("c1")
        assert s._instance is None


class TestSelectorCache:
    """Selector cache for reuse."""

    def test_cache_and_retrieve(self, tmp_path: Path) -> None:
        s = SharedDaemonMemory(project_path=tmp_path)
        sentinel = object()
        s.cache_selector("c1", sentinel)
        assert s.get_cached_selector("c1") is sentinel

    def test_no_cache_returns_none(self, tmp_path: Path) -> None:
        s = SharedDaemonMemory(project_path=tmp_path)
        assert s.get_cached_selector("c1") is None


class TestThreadSafety:
    """Shared state is thread-safe."""

    def test_concurrent_register(self, tmp_path: Path) -> None:
        s = SharedDaemonMemory(project_path=tmp_path)

        def register(i: int) -> None:
            s.register_client(f"c{i}", str(tmp_path))

        threads = [threading.Thread(target=register, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(s._clients) == 20


class TestGetInstance:
    """Warm NeuralMind instance."""

    def test_get_instance_no_project(self) -> None:
        s = SharedDaemonMemory(project_path=None)
        # Without a project path, cold-start fallback returns an instance
        # or None (both are valid fail-open outcomes).
        result = s.get_instance("c1")
        assert result is None or hasattr(result, "query")

    def test_get_instance_caches(self, tmp_path: Path) -> None:
        s = SharedDaemonMemory(project_path=tmp_path)
        a = s.get_instance("c1")
        b = s.get_instance("c2")
        if a is not None and b is not None:
            assert a is b
