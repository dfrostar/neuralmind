"""End-to-end CLI tests for Agent OS commands."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_cli(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "neuralmind.cli"] + args
    return subprocess.run(
        cmd, capture_output=True, text=True,
        env={**os.environ, **(env or {})}, timeout=30,
    )


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_TENANTS_DIR", str(tmp_path / "tenants"))
    monkeypatch.setenv("NEURALMIND_DAEMON_HOME", str(tmp_path / "daemon"))
    return tmp_path


class TestTenantsCreate:
    def test_create_tenant(self, clean_env):
        result = run_cli(["agent-os", "tenants", "create", "--id", "testcorp", "--name", "Test Corp", "--admin", "alice"])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["tenant_id"] == "testcorp"
        assert data["name"] == "Test Corp"
        emails = [r["email"] for r in data["rbac"]]
        # Email is lowercased by design
        assert "alice" in " ".join(emails)
        assert "admin" in [r["role"] for r in data["rbac"]]

    def test_create_persists_to_disk(self, clean_env):
        run_cli(["agent-os", "tenants", "create", "--id", "diskcorp", "--name", "Disk Corp", "--admin", "alice"])
        tenants_dir = Path(os.environ["NEURALMIND_TENANTS_DIR"])
        assert (tenants_dir / "diskcorp.json").exists()

    def test_create_duplicate_fails(self, clean_env):
        run_cli(["agent-os", "tenants", "create", "--id", "dupcorp", "--name", "Dup Corp", "--admin", "alice"])
        result = run_cli(["agent-os", "tenants", "create", "--id", "dupcorp", "--name", "Dup Corp 2", "--admin", "alice"])
        assert result.returncode != 0

    def test_create_with_tier(self, clean_env):
        result = run_cli(["agent-os", "tenants", "create", "--id", "tiercorp", "--name", "Tier Corp", "--admin", "alice", "--tier", "team"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["tier"] == "team"


class TestTenantsList:
    def test_list_empty(self, clean_env):
        result = run_cli(["agent-os", "tenants", "list"])
        assert result.returncode == 0
        assert json.loads(result.stdout) == []

    def test_list_shows_created(self, clean_env):
        run_cli(["agent-os", "tenants", "create", "--id", "listcorp", "--name", "List Corp", "--admin", "alice"])
        result = run_cli(["agent-os", "tenants", "list"])
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["tenant_id"] == "listcorp"


class TestTenantsDelete:
    def test_delete_tenant(self, clean_env):
        run_cli(["agent-os", "tenants", "create", "--id", "delcorp", "--name", "Delete Corp", "--admin", "alice"])
        result = run_cli(["agent-os", "tenants", "delete", "--id", "delcorp", "--admin", "alice"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["deleted"] == "delcorp"

    def test_delete_removes_file(self, clean_env):
        run_cli(["agent-os", "tenants", "create", "--id", "rmcorp", "--name", "Remove Corp", "--admin", "alice"])
        tenants_dir = Path(os.environ["NEURALMIND_TENANTS_DIR"])
        assert (tenants_dir / "rmcorp.json").exists()
        run_cli(["agent-os", "tenants", "delete", "--id", "rmcorp", "--admin", "alice"])
        assert not (tenants_dir / "rmcorp.json").exists()


class TestRbacAdd:
    def test_add_role(self, clean_env):
        run_cli(["agent-os", "tenants", "create", "--id", "rbaccorp", "--name", "RBAC Corp", "--admin", "alice"])
        result = run_cli(["agent-os", "rbac", "add", "--tenant", "rbaccorp", "--email", "alice", "--role", "operator", "--admin", "alice"])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        emails = [r["email"] for r in data["rbac"]]
        assert "alice" in emails
        assert "operator" in [r["role"] for r in data["rbac"]]

    def test_add_role_persists(self, clean_env):
        run_cli(["agent-os", "tenants", "create", "--id", "rbac2corp", "--name", "RBAC2 Corp", "--admin", "alice"])
        run_cli(["agent-os", "rbac", "add", "--tenant", "rbac2corp", "--email", "alice", "--role", "viewer", "--admin", "alice"])
        tenants_dir = Path(os.environ["NEURALMIND_TENANTS_DIR"])
        data = json.loads((tenants_dir / "rbac2corp.json").read_text())
        emails = [r["email"] for r in data["rbac"]]
        assert "alice" in emails


class TestSignalsPush:
    def test_push_signal(self, clean_env):
        result = run_cli(["agent-os", "signals", "push", "--metric", "latency_ms", "--value", "100.0"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["metric"] == "latency_ms"
        assert data["value"] == 100.0


class TestExperimentsRun:
    def test_run_experiment_promote(self, clean_env):
        result = run_cli(["agent-os", "experiments", "run", "--proposal", "p1", "--metric", "latency_ms", "--baseline", "100.0", "--candidate", "85.0"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["verdict"] in ("promoted", "rolled_back", "rejected")

    def test_run_experiment_rollback(self, clean_env):
        result = run_cli(["agent-os", "experiments", "run", "--proposal", "p2", "--metric", "latency_ms", "--baseline", "100.0", "--candidate", "120.0"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["verdict"] == "rolled_back"

    def test_run_experiment_higher_is_better(self, clean_env):
        result = run_cli(["agent-os", "experiments", "run", "--proposal", "p3", "--metric", "throughput", "--baseline", "100.0", "--candidate", "120.0", "--higher-is-better"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["verdict"] == "promoted"
