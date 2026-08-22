"""
ci_check.py — CI-specific analysis for NeuralMind.

Runs compliance-aware analysis on a git diff to detect changes that
affect compliance controls. Used by the ``neuralmind ci-check`` CLI
command and the GitHub Action.

User story:
- ``neuralmind ci-check --framework cmmc --diff HEAD~1``
  detects code changes affecting CMMC controls and reports them
  as structured findings.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from neuralmind.compliance_matcher import (
    find_compliance_annotations_in_file,
)


def _get_diff_files(project_path: str | Path, base: str = "HEAD") -> list[str]:
    """Get list of files changed in the current diff vs ``base``."""
    # Validate base to prevent command injection via git ref
    import re as _re

    if not _re.match(r"^[a-zA-Z0-9_./^\-~@]+$", base):
        return []
    try:
        cmd = ["git", "-C", str(project_path), "diff", "--name-only", base]
        result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
        return [f.strip() for f in result.splitlines() if f.strip()]
    except subprocess.CalledProcessError:
        # Try staged changes
        try:
            cmd = ["git", "-C", str(project_path), "diff", "--cached", "--name-only"]
            result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
            return [f.strip() for f in result.splitlines() if f.strip()]
        except Exception:
            return []
    except Exception:
        return []


def _detect_framework(framework_arg: str) -> list[str]:
    """Expand a framework arg to known prefix patterns.

    Returns list of framework names to search for (e.g., CMMC, NIST, SOX, HIPAA).
    """
    framework = (framework_arg or "").upper().strip()
    if framework == "ALL" or not framework:
        return ["CMMC", "NIST", "SOX ITGC", "HIPAA", "ISO 27001", "SOC2"]
    # Map user input to registered pattern names
    framework_map = {
        "CMMC": "CMMC",
        "NIST": "NIST",
        "SOX": "SOX ITGC",
        "SOX ITGC": "SOX ITGC",
        "HIPAA": "HIPAA",
        "ISO": "ISO 27001",
        "ISO 27001": "ISO 27001",
        "SOC": "SOC2",
        "SOC2": "SOC2",
        "SOC 2": "SOC2",
    }
    mapped = framework_map.get(framework)
    return [mapped] if mapped else [framework]


def run_ci_check(
    project_path: str | Path,
    *,
    framework: str = "all",
    base: str = "HEAD",
    json_output: bool = False,
) -> dict:
    """Run CI compliance check on the project.

    Args:
        project_path: Path to git repo root.
        framework: Compliance framework to check (``cmmc``, ``all``, etc.).
        base: Git ref to diff against (default: HEAD, i.e., uncommitted changes).
        json_output: If True, return structured data suitable for PR comments.

    Returns:
        Dict with findings, warnings, and counts.
    """
    project_path = Path(project_path)

    changed_files = _get_diff_files(project_path, base=base)

    findings: list[dict] = []
    affected_controls: set[str] = set()
    files_with_annotations: list[str] = []

    # _detect_framework existed but was never called, so `--framework cmmc`
    # printed "Framework: CMMC" and then reported findings from every
    # framework anyway.
    wanted_frameworks = set(_detect_framework(framework))

    for rel_path in changed_files:
        full_path = project_path / rel_path
        if not full_path.is_file():
            continue

        matches = [
            m
            for m in find_compliance_annotations_in_file(full_path)
            if m.get("framework", "") in wanted_frameworks
        ]
        if matches:
            files_with_annotations.append(rel_path)
            for m in matches:
                ctrl_id = m.get("control_id", "")
                if ctrl_id:
                    affected_controls.add(ctrl_id)
                findings.append(
                    {
                        "file": rel_path,
                        "control_id": ctrl_id,
                        "framework": m.get("framework", ""),
                        "label": m.get("label", ""),
                        "action": "annotation_detected",
                    }
                )

        # Check if this file touches known compliance-annotated code
        # (synapse lookup — files that have been linked to controls historically)
        if not matches:
            # Mark for informational scan
            pass

    # Build warning messages
    warnings: list[str] = []
    for ctrl_id in sorted(affected_controls):
        matching_files = [f["file"] for f in findings if f["control_id"] == ctrl_id]
        if matching_files:
            warnings.append(
                f"PR touches {', '.join(matching_files)} ({ctrl_id}). "
                f"Verify compliance controls are maintained."
            )

    result = {
        "framework": framework,
        "base": base,
        "changed_files": len(changed_files),
        "files_with_compliance_annotations": len(files_with_annotations),
        "affected_controls": sorted(affected_controls),
        "findings": findings,
        "warnings": warnings,
        "summary": "",
    }

    # Summary text
    summary_parts = []
    if affected_controls:
        summary_parts.append(
            f"Found {len(affected_controls)} affected compliance "
            f"control(s): {', '.join(sorted(affected_controls))}"
        )
    if findings:
        summary_parts.append(
            f"{len(findings)} compliance annotation(s) detected in "
            f"{len(files_with_annotations)} file(s)"
        )
        result["summary"] = "; ".join(summary_parts)
        result["warnings"] = warnings
        result["pass"] = True
    else:
        result["summary"] = "No compliance annotations affected by this diff."
        result["pass"] = True

    return result


def format_ci_output(result: dict) -> str:
    """Format CI check result for human-readable output."""
    lines = []

    # Header
    lines.append("NeuralMind CI Compliance Check")
    lines.append(f"Framework: {result.get('framework', 'all').upper()}")
    lines.append(f"Base ref: {result.get('base', 'HEAD')}")
    lines.append(f"Changed files: {result.get('changed_files', 0)}")
    lines.append("")

    # Findings
    findings = result.get("findings", [])
    if findings:
        lines.append(f"Compliance Findings ({len(findings)}):")
        lines.append("")
        for f in findings:
            ctrl = f.get("control_id", "?")
            fw = f.get("framework", "?")
            file_ = f.get("file", "?")
            label = f.get("label", "")
            lines.append(f"  [{fw:>10}] {ctrl}")
            if label:
                lines.append(f"             {label}")
            lines.append(f"             {file_}")
            lines.append("")
    else:
        lines.append("No compliance annotations affected by this diff.")
        lines.append("")

    # Warnings
    warnings = result.get("warnings", [])
    if warnings:
        lines.append("Warnings:")
        for w in warnings:
            lines.append(f"  ⚠  {w}")
        lines.append("")

    # Summary
    summary = result.get("summary", "")
    if summary:
        lines.append(f"Summary: {summary}")

    return "\n".join(lines)
