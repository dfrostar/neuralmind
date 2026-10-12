"""evals/retrieval/run.py: --full-repo and --no-build, without cloning or embedding."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from evals.retrieval import run


@pytest.fixture
def work(tmp_path, monkeypatch):
    """A work dir whose 'clones' are empty directories at the manifest's subdirs."""

    def fake_clone(work_dir, repo):
        root = work_dir / repo["name"] / (repo.get("subdir") or "")
        root.mkdir(parents=True, exist_ok=True)
        return root

    monkeypatch.setattr(run, "_pinned_clone", fake_clone)
    return tmp_path


def manifest_repo(name):
    repos = json.loads(run.MANIFEST.read_text(encoding="utf-8"))["repos"]
    return next(r for r in repos if r["name"] == name)


def test_source_dir_by_default(work):
    (repo,) = run.prepare(work, {"click"}, None, fresh=False)
    sub = manifest_repo("click")["subdir"]
    assert repo["root"] == work / "click" / sub
    assert repo["gold_prefix"] == ""


def test_full_repo_indexes_the_root_and_prefixes_gold(work):
    (repo,) = run.prepare(work, {"click"}, None, fresh=False, full_repo=True)
    sub = manifest_repo("click")["subdir"].strip("/")
    assert repo["root"] == work / "click"
    assert repo["gold_prefix"] == sub + "/"


def test_no_build_reuses_the_built_neuralmind_copy(work, monkeypatch):
    built = work / "neuralmind" / ".neuralmind"
    built.mkdir(parents=True)

    def no_copy(*_):
        raise AssertionError("a fresh copy would have no index")

    monkeypatch.setattr(run, "_copy_git_visible", no_copy)
    (repo,) = run.prepare(work, {"neuralmind"}, None, fresh=False)
    assert repo["root"] == work / "neuralmind" and built.exists()


def test_eval_config_scores_against_prefixed_gold(tmp_path, monkeypatch):
    questions = tmp_path / "q.yaml"
    questions.write_text('- q: "where is the parser?"\n  gold: [parser.py]\n', encoding="utf-8")
    seen = {}

    def fake_run_eval(root, qs, mind=None):
        seen["gold"] = [q.gold for q in qs]
        return SimpleNamespace(
            n_questions=1,
            hit_at_1=1.0,
            hit_at_5=1.0,
            mrr=1.0,
            avg_context_tokens=10.0,
            results=[SimpleNamespace(rank=1)],
        )

    import neuralmind.core
    import neuralmind.project_eval

    monkeypatch.setattr(neuralmind.project_eval, "run_eval", fake_run_eval)
    monkeypatch.setattr(neuralmind.core, "NeuralMind", lambda root: object())
    run.eval_config(tmp_path, questions, {}, gold_prefix="src/click/")
    assert seen["gold"] == [["src/click/parser.py"]]
