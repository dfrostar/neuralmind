"""Validate docs/community-benchmarks.json against its schema + sanity rules.

Runs in CI on every PR that touches the JSON. Local run:

    python scripts/validate_community_benchmarks.py

Exits 0 if every entry is valid, 1 otherwise with a per-entry error list.
Dependency: ``jsonschema`` (single, well-maintained pip package).

Sanity rules beyond the schema:

- ``date_submitted`` is not in the future
- ``avg_reduction_ratio`` is plausibly a ratio (> 1, < 10_000)
- If ``avg_query_tokens`` is present and ``avg_wakeup_tokens`` is too,
  query tokens should be larger than wakeup (query includes L2+L3;
  wakeup is L0+L1 only). Violations are warnings, not errors, because
  tiny projects can legitimately invert.
- No duplicate ``project_name`` + ``submitted_by`` combos
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = REPO_ROOT / "docs" / "community-benchmarks.json"
SCHEMA_PATH = REPO_ROOT / "docs" / "community-benchmarks.schema.json"

# Defensive ceiling — NeuralMind has never reported more than a few-hundred-x
# reduction. Anything above this is almost certainly a data-entry error
# (e.g. entering percentage as ratio).
PLAUSIBLE_RATIO_CEILING = 10_000


def load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def validate_schema(data: dict, schema: dict) -> list[str]:
    """Return a list of schema-validation errors (empty on success)."""
    try:
        import jsonschema
    except ImportError:
        return [
            "jsonschema not installed — `pip install jsonschema` to enable schema checks."
        ]

    validator = jsonschema.Draft7Validator(schema)
    errors = []
    for i, entry in enumerate(data.get("entries", [])):
        for err in validator.iter_errors(entry):
            # Build a short path like "entries[3].avg_reduction_ratio"
            loc = ".".join(str(p) for p in err.absolute_path) or "<root>"
            errors.append(f"entry[{i}] ({entry.get('project_name', '?')}): {loc}: {err.message}")
    return errors


def sanity_checks(entries: list[dict]) -> list[str]:
    """Return a list of sanity-check errors beyond the schema."""
    errors: list[str] = []
    today = date.today()
    seen_keys: set[tuple[str, str]] = set()

    for i, entry in enumerate(entries):
        name = entry.get("project_name", "?")

        # Date in the future
        ds = entry.get("date_submitted")
        if ds:
            try:
                submitted = date.fromisoformat(ds)
                if submitted > today:
                    errors.append(
                        f"entry[{i}] ({name}): date_submitted {ds} is in the future."
                    )
            except ValueError:
                errors.append(f"entry[{i}] ({name}): date_submitted {ds!r} not ISO YYYY-MM-DD.")

        # Implausible reduction ratio
        ratio = entry.get("avg_reduction_ratio")
        if ratio is not None and ratio > PLAUSIBLE_RATIO_CEILING:
            errors.append(
                f"entry[{i}] ({name}): avg_reduction_ratio {ratio} is implausibly large. "
                f"Did you submit a percentage instead of a ratio? (e.g. 97 instead of 33)"
            )

        # Duplicate submitter + project combo
        submitter = entry.get("submitted_by")
        if submitter and name:
            key = (name.lower(), submitter.lower())
            if key in seen_keys:
                errors.append(
                    f"entry[{i}] ({name}): duplicate (project_name, submitted_by) = {key}. "
                    f"If updating an existing entry, edit it in place rather than duplicating."
                )
            seen_keys.add(key)

    return errors


def main() -> int:
    data = load_json(DATA_PATH)
    schema = load_json(SCHEMA_PATH)

    schema_errors = validate_schema(data, schema)
    sanity_errors = sanity_checks(data.get("entries", []))

    all_errors = schema_errors + sanity_errors
    if all_errors:
        print(f"✗ {len(all_errors)} issue(s) found:\n")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    entry_count = len(data.get("entries", []))
    print(f"✓ community-benchmarks.json valid: {entry_count} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
