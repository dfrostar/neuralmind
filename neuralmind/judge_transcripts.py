"""
D3 — Populate judge transcripts for offline --judge evaluation.

The offline judge needs real query→answer→expected triples. These are
reference standards that the RAGAS-axis metrics score against. This
module populates bench/public/judge/ with fixture queries and
reference answers derived from the existing golden suites in
evals/quality/runner.py.

Local-first. Stdlib-only.
"""

from __future__ import annotations

import json
from pathlib import Path

JUDGE_DIR = Path(__file__).resolve().parent.parent / "bench" / "public" / "judge"

# Reference answers keyed by query_id. Each entry has the query text,
# reference_answer (ground truth), and source_files where the answer
# can be found in the fixture repo.
JUDGE_TRANSCRIPTS: dict[str, dict] = {
    "py_auth_flow": {
        "query": "How does authentication work in the sample project?",
        "reference_answer": (
            "Authentication is handled by the AuthManager class in "
            "pkg/auth.py, which validates tokens against the UserStore. "
            "The login() method returns a session token."
        ),
        "source_files": ["sample_project/pkg/auth.py", "sample_project/pkg/user.py"],
        "category": "architecture",
    },
    "py_data_model": {
        "query": "What is the data model for users?",
        "reference_answer": (
            "The User dataclass in pkg/user.py has fields: id (str), "
            "name (str), email (str), and role (str). It is persisted "
            "by UserStore in pkg/store.py."
        ),
        "source_files": ["sample_project/pkg/user.py", "sample_project/pkg/store.py"],
        "category": "architecture",
    },
    "ts_api_surface": {
        "query": "What API endpoints are defined?",
        "reference_answer": (
            "The API surface is defined in src/router.ts with GET /users, "
            "POST /users, GET /users/:id. Each handler delegates to the "
            "Controller class."
        ),
        "source_files": ["sample_project_ts/src/router.ts", "sample_project_ts/src/controller.ts"],
        "category": "architecture",
    },
    "go_package_struct": {
        "query": "How is the Go project structured?",
        "reference_answer": (
            "The project follows standard Go layout with cmd/ for main "
            "packages and internal/ for library code. The root go.mod "
            "declares the module path."
        ),
        "source_files": ["sample_project_go/cmd/main.go", "sample_project_go/internal/service.go"],
        "category": "architecture",
    },
}


def populate_judge_transcripts() -> dict[str, Path]:
    """
    Write fixture judge transcripts to bench/public/judge/.
    
    Returns: {transcript_id: written_path}
    """
    JUDGE_DIR.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    for tid, content in JUDGE_TRANSCRIPTS.items():
        path = JUDGE_DIR / f"{tid}.json"
        path.write_text(
            json.dumps(content, indent=2) + "\n",
            encoding="utf-8",
        )
        written[tid] = path

    # Write a manifest describing all transcripts
    manifest = {
        "description": "Offline judge transcripts for CI evaluation",
        "transcripts": sorted(JUDGE_TRANSCRIPTS.keys()),
        "n_transcripts": len(JUDGE_TRANSCRIPTS),
    }
    manifest_path = JUDGE_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    written["manifest"] = manifest_path

    return written


def load_judge_transcripts() -> dict[str, dict]:
    """Load all judge transcripts from bench/public/judge/."""
    transcripts: dict[str, dict] = {}
    if not JUDGE_DIR.exists():
        return transcripts

    for f in sorted(JUDGE_DIR.glob("*.json")):
        if f.name == "manifest.json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            transcripts[f.stem] = data
        except (json.JSONDecodeError, OSError):
            continue

    return transcripts


if __name__ == "__main__":
    written = populate_judge_transcripts()
    print(f"Wrote {len(written)} judge transcript files to {JUDGE_DIR}")
    for tid, path in written.items():
        print(f"  {tid}: {path}")
