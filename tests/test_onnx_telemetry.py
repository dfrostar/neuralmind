"""Ensure ONNX Runtime telemetry is disabled before runtime initialization."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class OnnxTelemetryTest(unittest.TestCase):
    def test_package_import_disables_onnxruntime_telemetry(self) -> None:
        env = os.environ.copy()
        env["ORT_DISABLE_TELEMETRY"] = "0"
        code = (
            "import os, sys, neuralmind; "
            "assert os.environ['ORT_DISABLE_TELEMETRY'] == '1'; "
            "assert 'onnxruntime' not in sys.modules"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
