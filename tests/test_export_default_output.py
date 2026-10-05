"""`neuralmind export` with no --output writes to the documented default path.

argparse always sets ``args.output`` (``None`` when the flag is omitted), so a
``getattr(args, "output", default)`` fallback never fired and the default
invocation crashed with ``TypeError: expected str, bytes or os.PathLike
object, not NoneType``.
"""

from __future__ import annotations

from types import SimpleNamespace

from neuralmind.cli import build_parser
from neuralmind.export import run_export


def _fake_mind():
    node = {
        "id": "pkg_a_py__f_fn",
        "label": "f()",
        "file_type": "code",
        "source_file": "pkg/a.py",
        "source_location": "L1",
        "community": 0,
    }
    return SimpleNamespace(embedder=SimpleNamespace(nodes=[node]), synapses=None)


def test_csv_export_without_output_uses_default_filename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    args = build_parser().parse_args(["export", str(tmp_path)])
    assert args.output is None  # the case that used to crash

    result = run_export(args, mind=_fake_mind())

    assert "error" not in result
    assert (tmp_path / "neuralmind_export.csv").is_file()


def test_nodes_csv_export_without_output_uses_default_filename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    args = build_parser().parse_args(["export", str(tmp_path), "--nodes"])

    result = run_export(args, mind=_fake_mind())

    assert "error" not in result
    assert "pkg_a_py__f_fn" in (tmp_path / "neuralmind_export.csv").read_text(encoding="utf-8")


def test_pdf_export_without_output_defaults_to_pdf_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seen = {}

    def fake_export_pdf(mind, output_path, report="ssp"):
        seen["path"] = output_path
        return {"path": str(output_path)}

    monkeypatch.setattr("neuralmind.export.export_pdf", fake_export_pdf)
    args = build_parser().parse_args(["export", str(tmp_path), "--format", "pdf"])

    run_export(args, mind=_fake_mind())

    assert str(seen["path"]) == "neuralmind_export.pdf"


def test_explicit_output_is_still_honoured(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "sub" / "audit.csv"
    args = build_parser().parse_args(["export", str(tmp_path), "--output", str(out)])

    run_export(args, mind=_fake_mind())

    assert out.is_file()
    assert not (tmp_path / "neuralmind_export.csv").exists()
