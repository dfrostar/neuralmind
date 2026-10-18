"""The machine policy: CUI settings a project directory's owner can't switch off.

``security.profile: cui`` used to live only in ``neuralmind-backend.yaml`` in
the project root. Whoever owns that directory can delete the file, even when an
administrator owns it, and every CUI control then switched off without a word.
``/etc/neuralmind/policy.yaml`` (``C:\\ProgramData\\NeuralMind\\policy.yaml``)
applies to every project on the machine and only tightens.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from neuralmind import doctor, security_config
from neuralmind import security_profile as sp
from neuralmind.mcp_security import IdentityDeniedError, MCPSecurityManager
from neuralmind.security_config import (
    IDENTITY_DECLARED,
    IDENTITY_INVALID,
    IDENTITY_OS,
    PROFILE_CUI,
    load_security_settings,
)
from neuralmind.storage_guard import StorageStatus

PROJECT_CUI = "security:\n  profile: cui\n  users:\n    alice: reader\n"


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """Write the machine policy; ownership is checked by its own tests."""
    path = tmp_path / "etc" / "neuralmind" / "policy.yaml"
    path.parent.mkdir(parents=True)
    monkeypatch.setattr(security_config, "MACHINE_POLICY_PATH", path)
    monkeypatch.setattr(security_config, "_untrusted_machine_policy", lambda _p: None)

    def write(text: str) -> Path:
        path.write_text(text, encoding="utf-8")
        return path

    return write


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    return root


def _project_config(project: Path, text: str) -> Path:
    path = project / "neuralmind-backend.yaml"
    path.write_text(text, encoding="utf-8")
    if sys.platform != "win32":
        path.chmod(0o644)
    return path


def _strictest(settings) -> bool:
    return (
        settings.identity == IDENTITY_INVALID
        and settings.require_encrypted_storage
        and settings.profile == PROFILE_CUI
    )


# --- the finding ------------------------------------------------------------


def test_without_a_machine_policy_deleting_the_project_file_drops_the_profile(project):
    # The behaviour the machine policy exists to prevent, kept as a baseline.
    path = _project_config(project, PROJECT_CUI)
    assert load_security_settings(project).profile == PROFILE_CUI
    path.unlink()
    assert load_security_settings(project).profile is None


def test_deleting_the_project_file_leaves_the_machine_profile_on(project, machine):
    machine("security:\n  profile: cui\n")
    path = _project_config(project, PROJECT_CUI)
    path.unlink()

    s = load_security_settings(project)
    assert (s.profile, s.identity, s.require_encrypted_storage) == (PROFILE_CUI, IDENTITY_OS, True)
    assert s.machine_policy == security_config.MACHINE_POLICY_PATH
    # Every refusal keyed off the profile still holds...
    assert sp.llm_seeding_refusal(project)
    with pytest.raises(sp.ProfileRefusedError):
        sp.refuse_exposed_listener(project, "0.0.0.0", True, "serve")
    # ...and with the role mapping gone, MCP calls are refused, not opened up.
    manager = MCPSecurityManager(str(project), settings=s)
    with pytest.raises(IdentityDeniedError, match="has no role"):
        manager.resolve_caller(None, "admin")


def test_the_storage_guard_follows_the_machine_policy(project, machine, monkeypatch):
    from neuralmind.storage_guard import StorageNotVerifiedError, enforce_storage_policy

    machine("security:\n  require_encrypted_storage: true\n")
    monkeypatch.setattr(
        "neuralmind.storage_guard.check_storage",
        lambda _p: StorageStatus(False, None, None, "not encrypted"),
    )
    with pytest.raises(StorageNotVerifiedError):
        enforce_storage_policy(str(project))


# --- tighten only -----------------------------------------------------------


def test_a_project_file_cannot_loosen_the_machine_policy(project, machine):
    machine("security:\n  profile: cui\n")
    _project_config(
        project,
        "security:\n  identity: declared\n  require_encrypted_storage: false\n"
        "  users:\n    alice: builder\n",
    )
    s = load_security_settings(project)
    assert (s.profile, s.identity, s.require_encrypted_storage) == (PROFILE_CUI, IDENTITY_OS, True)
    assert s.problem is None
    # Roles still come from the project file.
    assert s.users == {"alice": "builder"}


def test_a_project_can_be_stricter_than_the_machine(project, machine):
    machine("security:\n  require_encrypted_storage: true\n")
    _project_config(project, PROJECT_CUI)
    s = load_security_settings(project)
    assert (s.profile, s.identity, s.require_encrypted_storage) == (PROFILE_CUI, IDENTITY_OS, True)


@pytest.mark.parametrize("value", ["true", "false", "yes", "off", "'on'", "1", "0"])
def test_a_machine_policy_spelling_out_encryption_is_valid(project, machine, value):
    machine(f"security:\n  require_encrypted_storage: {value}\n")
    s = load_security_settings(project)
    assert s.problem is None and s.identity == IDENTITY_DECLARED


def test_an_empty_machine_policy_changes_nothing(project, machine):
    machine("security: {}\n")
    s = load_security_settings(project)
    assert (s.profile, s.identity, s.require_encrypted_storage) == (None, IDENTITY_DECLARED, False)


def test_a_broken_project_file_stays_refused_under_the_machine_policy(project, machine):
    machine("security:\n  require_encrypted_storage: true\n")
    _project_config(project, "security:\n  identity: sometimes\n")
    s = load_security_settings(project)
    assert s.identity == IDENTITY_INVALID and "security.identity" in s.problem


# --- a machine policy that can't be trusted holds everything ----------------


@pytest.mark.parametrize(
    "text, needle",
    [
        ("security:\n  profile: cui\n  users:\n    mallory: admin\n", "users and roles stay"),
        ("security:\n  default_role: admin\n", "not default_role"),
        ("security:\n  profile: [cui\n", "does not parse"),
        ("security: cui\n", "needs a `security` mapping"),
        ("security:\n  profile: cuii\n", "security.profile must be 'cui'"),
        # A valid key with an invalid value: _parse alone refused MCP calls but
        # left the profile and the encryption check off.
        ("security:\n  identity: sometimes\n", "security.identity must be"),
        ("security:\n  profile: cui\n  identity: declared\n", "requires identity: os"),
        # A project file reads a misspelling as on; a machine policy is held to
        # the strictest settings, as for any other invalid value.
        ("security:\n  require_encrypted_storage: flase\n", "must be true or false"),
        ("security:\n  require_encrypted_storage:\n", "must be true or false"),
        ("security:\n  require_encrypted_storage: 2\n", "must be true or false"),
    ],
)
def test_a_malformed_machine_policy_holds_every_project_to_the_strictest(
    project, machine, text, needle
):
    machine(text)
    s = load_security_settings(project)
    assert _strictest(s), s
    assert needle in s.problem
    assert str(security_config.MACHINE_POLICY_PATH) in s.problem


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX ownership and mode bits")
def test_a_machine_policy_others_can_write_is_not_trusted(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text("security:\n  profile: cui\n", encoding="utf-8")
    path.chmod(0o664)
    problem = security_config._untrusted_machine_policy(path)
    assert problem and ("writable by users other than root" in problem or "root" in problem)


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0, reason="needs a non-root POSIX account"
)
def test_a_machine_policy_not_owned_by_root_is_not_trusted(tmp_path, monkeypatch):
    path = tmp_path / "policy.yaml"
    path.write_text("security:\n  profile: cui\n", encoding="utf-8")
    path.chmod(0o644)
    monkeypatch.setattr(security_config, "MACHINE_POLICY_PATH", path)
    assert "not owned by root" in security_config._untrusted_machine_policy(path)
    assert _strictest(load_security_settings(tmp_path))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX path")
def test_the_posix_machine_policy_lives_in_etc():
    assert security_config._default_machine_policy_path() == Path("/etc/neuralmind/policy.yaml")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path")
def test_the_windows_machine_policy_ignores_the_programdata_variable(tmp_path, monkeypatch):
    # A user can set %ProgramData%; pointing it at an empty folder must not
    # hide the policy.
    monkeypatch.setenv("ProgramData", str(tmp_path))
    path = security_config._default_machine_policy_path()
    assert not str(path).startswith(str(tmp_path))
    assert path.parts[-2:] == ("NeuralMind", "policy.yaml")


# --- doctor -----------------------------------------------------------------


def test_doctor_names_the_machine_policy(project, machine, monkeypatch):
    machine("security:\n  profile: cui\n")
    monkeypatch.setattr(
        "neuralmind.storage_guard.check_storage",
        lambda _p: StorageStatus(True, "LUKS", True, "encrypted"),
    )
    from neuralmind.onnx_embedder import OnnxMiniLMEmbedder

    monkeypatch.setattr(OnnxMiniLMEmbedder, "local_model_dir", lambda self: Path("/models"))
    monkeypatch.setattr(doctor, "_running_daemon_exposure", lambda: None)
    monkeypatch.delenv("NEURALMIND_LLM_SEED", raising=False)

    check = doctor._check_security_profile(project)
    assert check.status == doctor.OK
    assert f"machine policy {security_config.MACHINE_POLICY_PATH} applies" in check.detail


def test_doctor_fails_on_a_malformed_machine_policy(project, machine):
    machine("security:\n  users:\n    mallory: admin\n")
    check = doctor._check_security_policy(project)
    assert check.status == doctor.FAIL
    assert "users and roles stay" in check.detail
