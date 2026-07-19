#!/usr/bin/env python3
"""Port expected_facts from evals/faithfulness/queries.json into the per-language
benchmark query files, adapting file paths to each language's convention."""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FAITH = REPO / "evals" / "faithfulness" / "queries.json"

# Map query-id → (python-fact-ids to port). We port the subset that maps cleanly;
# queries unique to the benchmark files get auto-generated facts below.
LANGS: dict[str, dict[str, str]] = {
    "ts": {
        "file": "tests/fixtures/benchmark_queries_ts.json",
        "ext": ".ts",
        "prefix": "src/",
    },
    "go": {
        "file": "tests/fixtures/benchmark_queries_go.json",
        "ext": ".go",
        "prefix": "",
    },
    "rust": {
        "file": "tests/fixtures/benchmark_queries_rust.json",
        "ext": ".rs",
        "prefix": "src/",
    },
    "java": {
        "file": "tests/fixtures/benchmark_queries_java.json",
        "ext": ".java",
        "prefix": "src/main/java/com/example/",
    },
}


def adapt_path(py_path: str, ext: str, prefix: str) -> str:
    """Convert a Python fixture path to the target language's path."""
    # e.g. "auth/handlers.py" → "src/auth/handlers.ts"
    stem = Path(py_path).stem
    return f"{prefix}{stem}{ext}"


def main() -> None:
    faith = json.loads(FAITH.read_text(encoding="utf-8"))
    faith_by_id = {q["id"]: q for q in faith["queries"]}

    for _lang, cfg in LANGS.items():
        path = REPO / cfg["file"]
        data = json.loads(path.read_text(encoding="utf-8"))
        ext = cfg["ext"]
        prefix = cfg["prefix"]
        for q in data["queries"]:
            fid = q["id"]
            if fid in faith_by_id:
                # Port facts: adapt each fact's aliases that mention specific
                # python file paths to the language-specific path.
                src = faith_by_id[fid]
                facts = []
                for f in src.get("expected_facts", []):
                    new_aliases = []
                    for alias in f.get("aliases", []):
                        # Replace python paths with language-specific ones.
                        new_alias = alias
                        for py_mod in src.get("expected_modules", []):
                            if py_mod in new_alias:
                                new_alias = new_alias.replace(
                                    py_mod, adapt_path(py_mod, ext, prefix)
                                )
                        new_aliases.append(new_alias)
                    facts.append(
                        {
                            "id": f["id"],
                            "fact": f["fact"],
                            "aliases": new_aliases,
                        }
                    )
                q["expected_facts"] = facts
            else:
                # Generate basic facts from expected_modules for
                # debug/refactor/next-edit queries unique to the benchmark set.
                facts = []
                mods = q.get("expected_modules", [])
                q_lower = q["question"].lower()
                # Add intent-derived facts
                if "database" in q_lower or "db" in q_lower:
                    facts.append(
                        {
                            "id": f"{fid}-db",
                            "fact": "the project uses SQLite as its database",
                            "aliases": ["sqlite", "sqlite3", "database"],
                        }
                    )
                if "refund" in q_lower or "billing" in q_lower:
                    facts.append(
                        {
                            "id": f"{fid}-billing",
                            "fact": "the billing logic uses the Stripe API",
                            "aliases": ["stripe", "charge", "billing"],
                        }
                    )
                if "auth" in q_lower or "jwt" in q_lower or "login" in q_lower:
                    facts.append(
                        {
                            "id": f"{fid}-auth",
                            "fact": "authentication uses JWT tokens with HMAC-SHA256",
                            "aliases": ["jwt", "hs256", "auth", "hmac"],
                        }
                    )
                if "user" in q_lower:
                    facts.append(
                        {
                            "id": f"{fid}-users",
                            "fact": "user records are stored in a users table",
                            "aliases": ["users table", "user", "crud"],
                        }
                    )
                if "webhook" in q_lower or "stripe" in q_lower:
                    facts.append(
                        {
                            "id": f"{fid}-webhook",
                            "fact": "webhook signatures are verified with HMAC-SHA256",
                            "aliases": ["webhook", "signature", "verify"],
                        }
                    )
                if not facts and mods:
                    # Fallback: one fact per module
                    for m in mods[:2]:
                        facts.append(
                            {
                                "id": f"{fid}-{Path(m).stem}",
                                "fact": f"the module {m} is relevant",
                                "aliases": [Path(m).stem],
                            }
                        )
                q["expected_facts"] = facts
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"  updated {path.relative_to(REPO)} ({len(data['queries'])} queries)")


if __name__ == "__main__":
    main()
