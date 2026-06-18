"""Guard the platform-gated vector-backend dependency markers (v0.29.0).

`pip install neuralmind` must resolve to a prebuilt-wheel vector backend on
every supported platform — turbovec/ONNX where turbovec publishes wheels
(Linux, macOS arm64, Windows x86_64) and ChromaDB as the fallback elsewhere
(Intel macOS, Windows ARM). CI only runs the wheel-covered platforms, so this
test evaluates the `pyproject.toml` environment markers for the *other*
platforms too — catching a regression (no backend, or both) that CI cannot.

stdlib + `packaging`; skips cleanly if TOML/`packaging` aren't importable.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    if sys.version_info >= (3, 11):
        import tomllib  # type: ignore[import-not-found]
    else:  # pragma: no cover - 3.10 fallback
        import tomli as tomllib  # type: ignore[no-redef]
    from packaging.requirements import Requirement

    _DEPS_AVAILABLE = True
except Exception:  # pragma: no cover
    _DEPS_AVAILABLE = False


# Representative (platform_system, platform_machine) environments.
_PLATFORMS = {
    "linux-x86_64": {"platform_system": "Linux", "platform_machine": "x86_64"},
    "linux-aarch64": {"platform_system": "Linux", "platform_machine": "aarch64"},
    "macos-arm64": {"platform_system": "Darwin", "platform_machine": "arm64"},
    "macos-x86_64": {"platform_system": "Darwin", "platform_machine": "x86_64"},
    "windows-amd64": {"platform_system": "Windows", "platform_machine": "AMD64"},
    "windows-arm64": {"platform_system": "Windows", "platform_machine": "ARM64"},
}
# Where turbovec publishes wheels → the ChromaDB-free default; elsewhere chroma.
_TURBOVEC_PLATFORMS = {"linux-x86_64", "linux-aarch64", "macos-arm64", "windows-amd64"}
_BACKEND_PKGS = {"turbovec", "onnxruntime", "tokenizers", "chromadb"}


@unittest.skipUnless(_DEPS_AVAILABLE, "needs tomllib/tomli + packaging")
class BackendMarkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        data = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        cls.deps = [Requirement(r) for r in data["project"]["dependencies"]]

    def _selected_backends(self, env: dict[str, str]) -> set[str]:
        # Augment with the marker vars packaging needs to evaluate every line.
        full = {
            "os_name": "posix",
            "sys_platform": "linux",
            "python_version": "3.12",
            "python_full_version": "3.12.0",
            "implementation_name": "cpython",
            "platform_release": "",
            "platform_version": "",
            **env,
        }
        return {
            r.name
            for r in self.deps
            if r.name in _BACKEND_PKGS and (r.marker is None or r.marker.evaluate(full))
        }

    def test_every_platform_gets_exactly_one_backend(self) -> None:
        for name, env in _PLATFORMS.items():
            got = self._selected_backends(env)
            has_turbovec = "turbovec" in got
            has_chroma = "chromadb" in got
            self.assertTrue(
                has_turbovec ^ has_chroma,
                f"{name}: expected exactly one vector backend, got {sorted(got)}",
            )

    def test_turbovec_default_on_wheel_covered_platforms(self) -> None:
        for name in _TURBOVEC_PLATFORMS:
            got = self._selected_backends(_PLATFORMS[name])
            self.assertEqual(
                {"turbovec", "onnxruntime", "tokenizers"},
                got,
                f"{name}: must resolve to the ChromaDB-free turbovec/ONNX stack, got {sorted(got)}",
            )
            self.assertNotIn("chromadb", got, f"{name}: chromadb must NOT be a base dep here")

    def test_chroma_fallback_on_uncovered_platforms(self) -> None:
        for name in set(_PLATFORMS) - _TURBOVEC_PLATFORMS:
            got = self._selected_backends(_PLATFORMS[name])
            self.assertEqual(
                {"chromadb"}, got, f"{name}: must fall back to chromadb, got {sorted(got)}"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
