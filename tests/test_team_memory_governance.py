"""Team governance is enforced on the team-memory flow, not just stored.

- ``memory publish`` honours the publishing scope and weight threshold;
- publishes, imports, review approvals/rejections and removals are audited;
- ``team governance list-shared`` lists the project's shared memory;
- ``team governance remove-edge`` removes an association and retracts it in
  the committed bundle, so teammates drop it and no publish re-adds it.

Every test points the tier2 config at tmp_path; the conftest autouse fixture
keeps a developer's real ~/.config/neuralmind/tier2.yaml out of the rest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuralmind.synapses import DEFAULT_NAMESPACE, SHARED_NAMESPACE, SynapseStore, default_db_path
from neuralmind.team_memory import (
    TEAM_BUNDLE_FILENAME,
    PublishBlockedError,
    maybe_import_team_memory,
    publish_team_memory,
    retract_team_edge,
    team_bundle_path,
)
from neuralmind.tier2 import config as tier2_config
from neuralmind.tier2.audit import AuditLog
from neuralmind.tier2.config import Tier2Config, save_config
from neuralmind.tier2.governance import PublishPolicy, load_publish_policy

ADMIN = "lead@example.org"


def _store(project: Path) -> SynapseStore:
    return SynapseStore(default_db_path(project))


def _seed(store: SynapseStore) -> None:
    """Strong personal triangle + one weak personal edge + one shared edge."""
    for _ in range(30):
        store.reinforce(
            ["auth/handlers.py", "auth/jwt_utils.py", "users/crud.py"],
            strength=5.0,
            namespace=DEFAULT_NAMESPACE,
        )
    store.import_edges([("docs/a.md", "docs/b.md", 0.05, 1)], namespace=DEFAULT_NAMESPACE)
    store.import_edges(
        [("billing/api.py", "billing/models.py", 0.9, 6)], namespace=SHARED_NAMESPACE
    )


def _pairs(bundle: dict) -> set[tuple[str, str]]:
    return {tuple(sorted((e["source"], e["target"]))) for e in bundle["synapses"]}


@pytest.fixture
def governance(tmp_path, monkeypatch):
    """Configure tier2 governance in tmp_path; returns (configure, audit_log)."""
    config_path = tmp_path / "tier2" / "tier2.yaml"
    audit_path = tmp_path / "tier2" / "audit.db"
    monkeypatch.setattr(tier2_config, "DEFAULT_CONFIG_PATH", config_path)
    monkeypatch.setenv("NEURALMIND_ACTOR_EMAIL", ADMIN)

    def configure(scope="both", threshold=0.1, enabled=True) -> None:
        cfg = Tier2Config(
            license_file=str(tmp_path / "tier2" / "license.json"),
            audit_db=str(audit_path),
        )
        cfg.governance.enabled = enabled
        cfg.governance.publishing_scope = scope
        cfg.governance.weight_threshold = threshold
        cfg.governance.admin_emails = [ADMIN]
        save_config(cfg, config_path)

    def audit() -> list:
        return AuditLog(audit_path).export()

    return configure, audit


@pytest.fixture
def project(tmp_path) -> Path:
    path = tmp_path / "project"
    path.mkdir()
    return path


class TestPublishPolicy:
    def test_unconfigured_governance_changes_nothing(self, project):
        store = _store(project)
        _seed(store)
        summary = publish_team_memory(project, store)
        assert summary["governance"] is None
        assert summary["audited"] is None
        bundle = json.loads(team_bundle_path(project).read_text())
        # personal + shared, weak edges included — today's behaviour.
        assert ("docs/a.md", "docs/b.md") in _pairs(bundle)
        assert ("billing/api.py", "billing/models.py") in _pairs(bundle)

    def test_scope_personal_blocks_publishing(self, project, governance):
        configure, audit = governance
        configure(scope="personal")
        store = _store(project)
        _seed(store)
        with pytest.raises(PublishBlockedError, match="scope is 'personal'"):
            publish_team_memory(project, store)
        assert not team_bundle_path(project).exists()
        entry = audit()[-1]
        assert entry.action == "publish"
        assert entry.details["blocked"] is True

    def test_scope_shared_publishes_only_the_team_baseline(self, project, governance):
        configure, _ = governance
        configure(scope="shared", threshold=0.0)
        store = _store(project)
        _seed(store)
        publish_team_memory(project, store)
        bundle = json.loads(team_bundle_path(project).read_text())
        assert _pairs(bundle) == {("billing/api.py", "billing/models.py")}
        assert bundle["provenance"]["source_namespaces"] == [SHARED_NAMESPACE]
        assert bundle["provenance"]["governance"] == {"scope": "shared", "weight_threshold": 0.0}

    def test_weight_threshold_leaves_weak_edges_out(self, project, governance):
        configure, audit = governance
        configure(scope="both", threshold=0.1)
        store = _store(project)
        _seed(store)
        summary = publish_team_memory(project, store)
        bundle = json.loads(team_bundle_path(project).read_text())
        assert ("docs/a.md", "docs/b.md") not in _pairs(bundle)
        assert ("auth/handlers.py", "auth/jwt_utils.py") in _pairs(bundle)
        assert all(e["weight"] >= 0.1 for e in bundle["synapses"])
        assert summary["left_out"]["below_threshold"] == 1
        assert summary["audited"] is True
        entry = audit()[-1]
        assert (entry.action, entry.actor) == ("publish", ADMIN)
        assert entry.details["content_hash"] == bundle["content_hash"]
        assert entry.details["left_out"]["below_threshold"] == 1

    def test_disabled_governance_does_not_gate_but_still_audits(self, project, governance):
        configure, audit = governance
        configure(scope="personal", threshold=0.9, enabled=False)
        store = _store(project)
        _seed(store)
        summary = publish_team_memory(project, store)
        assert summary["governance"] is None
        assert ("docs/a.md", "docs/b.md") in _pairs(
            json.loads(team_bundle_path(project).read_text())
        )
        assert audit()[-1].action == "publish"

    def test_unreadable_governance_config_fails_closed(self, project, governance):
        configure, _ = governance
        configure()
        path = Path(tier2_config.DEFAULT_CONFIG_PATH)
        path.write_text(
            path.read_text().replace("publishing_scope: both", "publishing_scope: everyone")
        )
        store = _store(project)
        _seed(store)
        with pytest.raises(PublishBlockedError, match="could not be read"):
            publish_team_memory(project, store)
        assert not team_bundle_path(project).exists()

    def test_policy_object(self, governance):
        configure, _ = governance
        assert load_publish_policy() is None  # nothing configured yet
        configure(scope="shared", threshold=0.25)
        policy = load_publish_policy()
        assert policy == PublishPolicy(scope="shared", weight_threshold=0.25)
        assert policy.source_namespaces == (SHARED_NAMESPACE,)
        assert not policy.blocks_publishing
        assert PublishPolicy(scope="personal", weight_threshold=0.1).blocks_publishing


class TestImportAudit:
    def _publish_elsewhere(self, tmp_path: Path) -> Path:
        teammate = tmp_path / "teammate"
        teammate.mkdir()
        store = _store(teammate)
        _seed(store)
        publish_team_memory(teammate, store, policy=None)
        return team_bundle_path(teammate)

    def test_import_is_audited_when_governance_is_configured(self, project, governance, tmp_path):
        configure, audit = governance
        configure()
        (project / TEAM_BUNDLE_FILENAME).write_text(self._publish_elsewhere(tmp_path).read_text())
        result = maybe_import_team_memory(project, _store(project))
        assert result is not None
        entry = audit()[-1]
        assert entry.action == "import"
        assert entry.details["content_hash"] == result["content_hash"]
        assert entry.details["promoted"] == result["promoted"]

    def test_import_writes_no_audit_without_governance(self, project, tmp_path):
        (project / TEAM_BUNDLE_FILENAME).write_text(self._publish_elsewhere(tmp_path).read_text())
        assert maybe_import_team_memory(project, _store(project)) is not None
        assert not Path(tier2_config.DEFAULT_CONFIG_PATH).parent.exists()


class TestRetraction:
    def test_retraction_reaches_teammates_and_is_never_republished(self, project, tmp_path):
        # The admin's machine: publish, then retract one association.
        admin = _store(project)
        _seed(admin)
        publish_team_memory(project, admin, policy=None)
        result = retract_team_edge(project, admin, "auth/jwt_utils.py", "auth/handlers.py")
        assert result["removed_from_bundle"] == 1
        bundle = json.loads(team_bundle_path(project).read_text())
        assert ("auth/handlers.py", "auth/jwt_utils.py") not in _pairs(bundle)
        assert bundle["retracted"][0]["source"] == "auth/handlers.py"  # stored order-independent

        # A teammate who had already inherited the association drops it.
        teammate = tmp_path / "teammate"
        teammate.mkdir()
        mate = _store(teammate)
        mate.import_edges(
            [("auth/handlers.py", "auth/jwt_utils.py", 0.8, 5)], namespace=SHARED_NAMESPACE
        )
        (teammate / TEAM_BUNDLE_FILENAME).write_text(team_bundle_path(project).read_text())
        imported = maybe_import_team_memory(teammate, mate)
        assert imported is not None and imported["retracted"] == 1
        shared = {tuple(sorted(e[:2])) for e in mate.edges(namespaces=[SHARED_NAMESPACE])}
        assert ("auth/handlers.py", "auth/jwt_utils.py") not in shared

        # Republishing from personal memory (which still has it) leaves it out.
        summary = publish_team_memory(project, admin, policy=None)
        republished = json.loads(team_bundle_path(project).read_text())
        assert ("auth/handlers.py", "auth/jwt_utils.py") not in _pairs(republished)
        assert summary["left_out"]["retracted"] >= 1
        assert republished["retracted"] == bundle["retracted"]

    def test_retraction_without_a_bundle_creates_one(self, project):
        store = _store(project)
        store.import_edges([("a.py", "b.py", 0.9, 3)], namespace=SHARED_NAMESPACE)
        result = retract_team_edge(project, store, "a.py", "b.py")
        assert result["removed_from_store"] == 1
        bundle = json.loads(team_bundle_path(project).read_text())
        assert bundle["synapses"] == [] and bundle["counts"]["synapses"] == 0
        assert [(r["source"], r["target"]) for r in bundle["retracted"]] == [("a.py", "b.py")]

    def test_retraction_changes_the_content_hash(self, project):
        store = _store(project)
        _seed(store)
        before = publish_team_memory(project, store, policy=None)["content_hash"]
        retract_team_edge(project, store, "docs/a.md", "docs/b.md")
        after = json.loads(team_bundle_path(project).read_text())["content_hash"]
        assert after != before  # teammates import the update

    def test_retraction_refuses_to_overwrite_a_corrupt_bundle(self, project):
        store = _store(project)
        store.import_edges([("a.py", "b.py", 0.9, 3)], namespace=SHARED_NAMESPACE)
        team_bundle_path(project).write_text("{not json")
        with pytest.raises(ValueError, match="not a valid team bundle"):
            retract_team_edge(project, store, "a.py", "b.py")
        assert team_bundle_path(project).read_text() == "{not json"
        # Nothing was half-done: the local association is still there.
        assert len(store.edges(namespaces=[SHARED_NAMESPACE])) == 1

    def test_retracted_pair_leaves_the_review_queue(self, project):
        from neuralmind.team_memory import _load_pending_review, _save_pending_review

        store = _store(project)
        _save_pending_review(
            store,
            [
                {
                    "source": "x.py",
                    "target": "y.py",
                    "score": 0.4,
                    "reason": "",
                    "reviewer_hint": "",
                },
                {
                    "source": "p.py",
                    "target": "q.py",
                    "score": 0.4,
                    "reason": "",
                    "reviewer_hint": "",
                },
            ],
        )
        retract_team_edge(project, store, "y.py", "x.py")
        assert [e["source"] for e in _load_pending_review(store)] == ["p.py"]


class TestGovernanceCLI:
    def _team(self, argv: list[str]) -> int:
        from neuralmind.tier2.cli import main

        return main(argv)

    def test_list_shared_lists_the_projects_shared_memory(self, project, governance, capsys):
        configure, _ = governance
        configure()
        _seed(_store(project))
        assert self._team(["governance", "list-shared", "--project", str(project), "--json"]) == 0
        edges = json.loads(capsys.readouterr().out)
        assert [(e["source"], e["target"]) for e in edges] == [
            ("billing/api.py", "billing/models.py")
        ]

    def test_list_shared_without_memory(self, project, governance, capsys):
        configure, _ = governance
        configure()
        assert self._team(["governance", "list-shared", "--project", str(project), "--json"]) == 0
        assert json.loads(capsys.readouterr().out) == []

    def test_remove_edge_requires_an_admin(self, project, governance, capsys, monkeypatch):
        configure, _ = governance
        configure()
        store = _store(project)
        _seed(store)
        rc = self._team(
            [
                "governance",
                "remove-edge",
                "billing/api.py",
                "billing/models.py",
                "--project",
                str(project),
                "--admin",
                "intruder@example.org",
            ]
        )
        assert rc == 1
        assert "Permission denied" in capsys.readouterr().err
        assert len(store.edges(namespaces=[SHARED_NAMESPACE])) == 1
        assert not team_bundle_path(project).exists()

    def test_remove_edge_removes_and_audits(self, project, governance, capsys):
        configure, audit = governance
        configure()
        store = _store(project)
        _seed(store)
        rc = self._team(
            [
                "governance",
                "remove-edge",
                "billing/models.py",
                "billing/api.py",
                "--project",
                str(project),
                "--admin",
                ADMIN,
            ]
        )
        assert rc == 0
        assert "retraction recorded" in capsys.readouterr().out
        assert store.edges(namespaces=[SHARED_NAMESPACE]) == []
        entry = audit()[-1]
        assert (entry.action, entry.target, entry.actor) == (
            "remove",
            "billing/models.py -> billing/api.py",
            ADMIN,
        )
        assert entry.details["removed_from_store"] == 1


class TestReviewAudit:
    def _queue(self, store: SynapseStore) -> None:
        from neuralmind.team_memory import _save_pending_review

        _save_pending_review(
            store,
            [
                {
                    "source": "x.py",
                    "target": "y.py",
                    "score": 0.4,
                    "reason": "r",
                    "reviewer_hint": "h",
                },
                {
                    "source": "p.py",
                    "target": "q.py",
                    "score": 0.4,
                    "reason": "r",
                    "reviewer_hint": "h",
                },
            ],
        )

    def _memory(self, argv: list[str]) -> None:
        from neuralmind.cli import build_parser

        args = build_parser().parse_args(["memory", *argv])
        args.func(args)

    def test_approve_and_reject_are_audited(self, project, governance):
        configure, audit = governance
        configure()
        store = _store(project)
        self._queue(store)
        self._memory(["review-approve", "x.py", "y.py", str(project)])
        self._memory(["review-reject", "p.py", "q.py", str(project)])
        actions = [(e.action, e.target) for e in audit()]
        assert ("review_approve", "x.py -> y.py") in actions
        assert ("review_reject", "p.py -> q.py") in actions

    def test_review_without_governance_writes_no_audit(self, project):
        store = _store(project)
        self._queue(store)
        self._memory(["review-approve", "x.py", "y.py", str(project)])
        assert not Path(tier2_config.DEFAULT_CONFIG_PATH).parent.exists()
