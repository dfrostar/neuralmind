"""
export.py — Audit export generation for NeuralMind.

Generates auditor-ready exports of synapse state, code graph structure,
and compliance linkage. Supports CSV (spreadsheet) and PDF (report)
formats.

User stories:
- ``neuralmind export --format csv --controls`` — exports all practices
  mapped to code as a CSV
- ``neuralmind export --format pdf --report ssp`` — generates a System
  Security Plan section with timestamps, node IDs, synapse weights
- ``neuralmind export --format csv`` — exports the full code graph with
  node metadata and synapse weights
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------- #
# CSV Export
# --------------------------------------------------------------------------- #


def export_csv(
    mind,
    output_path: str | Path,
    *,
    controls: bool = False,
    nodes: bool = False,
) -> dict:
    """Export NeuralMind state to CSV.

    Args:
        mind: A ``NeuralMind`` instance with a built index.
        output_path: Where to write the CSV file.
        controls: If True, export compliance-control-to-code mappings.
        nodes: If True, export the full node list with metadata.

    Returns:
        Dict with ``path``, ``rows``, and ``export_type``.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    embedder = getattr(mind, "embedder", None)
    nodes_list = getattr(embedder, "nodes", None) or []
    synapses = getattr(mind, "synapses", None)

    if controls:
        return _export_controls_csv(mind, output_path, nodes_list, synapses)
    if nodes:
        return _export_nodes_csv(mind, output_path, nodes_list)
    # Default: full graph + synapse weights
    return _export_graph_csv(mind, output_path, nodes_list, synapses)


def _export_controls_csv(mind, output_path, nodes_list, synapses) -> dict:
    """Export compliance-control-to-code mapping CSV."""
    rows = []
    seen: set[tuple[str, str]] = set()

    # Scan all nodes for compliance annotations (from graphgen rationale nodes)
    for node in nodes_list:
        compliance_matches = node.get("compliance_matches") or []
        for cm in compliance_matches:
            ctrl_id = cm.get("control_id", "")
            framework = cm.get("framework", "")
            label_cm = cm.get("label", "")
            key = (ctrl_id, node.get("id", ""))
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "control_id": ctrl_id,
                    "framework": framework,
                    "label": label_cm,
                    "code_node_id": node.get("id", ""),
                    "code_label": node.get("label", ""),
                    "source_file": node.get("source_file", ""),
                    "node_type": node.get("file_type", ""),
                }
            )

    # Also scan the synapse store for compliance edges
    if synapses is not None:
        try:
            all_edges = synapses.edges(min_weight=0.0, limit=10000)
            for edge in all_edges:
                src, tgt = edge.get("source", ""), edge.get("target", "")
                weight = edge.get("weight", 0.0)
                for sid in (src, tgt):
                    if str(sid).startswith("compliance:"):
                        parts = str(sid).split(":", 2)
                        if len(parts) == 3:
                            framework_syn, ctrl_id = parts[1], parts[2]
                            code_side = tgt if sid == src else src
                            # Find the code node's source file
                            source_file = ""
                            for n in nodes_list:
                                if n.get("id", "") == code_side:
                                    source_file = n.get("source_file", "")
                                    break
                            key = (ctrl_id, code_side)
                            if key not in seen:
                                seen.add(key)
                                rows.append(
                                    {
                                        "control_id": ctrl_id,
                                        "framework": framework_syn,
                                        "label": "",
                                        "code_node_id": code_side,
                                        "code_label": "",
                                        "source_file": source_file,
                                        "node_type": "synapse",
                                        "synapse_weight": round(weight, 4),
                                    }
                                )
        except Exception:
            pass

    if not rows:
        rows.append(
            {
                "control_id": "",
                "framework": "",
                "label": "",
                "code_node_id": "",
                "code_label": "",
                "source_file": "",
                "node_type": "",
                "note": "No compliance-to-code mappings found",
            }
        )

    fieldnames = [
        "control_id",
        "framework",
        "label",
        "code_node_id",
        "code_label",
        "source_file",
        "node_type",
    ]
    if any("synapse_weight" in r for r in rows):
        fieldnames.append("synapse_weight")

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    count = len(rows)
    print(f"Exported {count} compliance-to-code mappings to {output_path}")

    return {
        "path": str(output_path),
        "rows": count,
        "export_type": "controls",
    }


def _export_nodes_csv(mind, output_path, nodes_list) -> dict:
    """Export all nodes with metadata as CSV."""
    rows = []
    for node in nodes_list:
        rows.append(
            {
                "node_id": node.get("id", ""),
                "label": node.get("label", ""),
                "file_type": node.get("file_type", ""),
                "source_file": node.get("source_file", ""),
                "source_location": node.get("source_location", ""),
                "community": node.get("community", -1),
            }
        )

    if not rows:
        rows.append({"node_id": "", "label": "", "note": "No nodes in graph"})

    fieldnames = [
        "node_id",
        "label",
        "file_type",
        "source_file",
        "source_location",
        "community",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} nodes to {output_path}")

    return {
        "path": str(output_path),
        "rows": len(rows),
        "export_type": "nodes",
    }


def _export_graph_csv(mind, output_path, nodes_list, synapses) -> dict:
    """Export full graph with synapse weights as CSV."""
    rows = []
    for node in nodes_list:
        rows.append(
            {
                "node_id": node.get("id", ""),
                "label": node.get("label", ""),
                "file_type": node.get("file_type", ""),
                "source_file": node.get("source_file", ""),
                "source_location": node.get("source_location", ""),
                "community": node.get("community", -1),
                "compliance_matches": json.dumps(node.get("compliance_matches", [])),
            }
        )

    fieldnames = [
        "node_id",
        "label",
        "file_type",
        "source_file",
        "source_location",
        "community",
        "compliance_matches",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} graph nodes to {output_path}")

    return {
        "path": str(output_path),
        "rows": len(rows),
        "export_type": "graph",
    }


# --------------------------------------------------------------------------- #
# PDF Export
# --------------------------------------------------------------------------- #


def _find_weasyprint() -> bool:
    """Check if weasyprint is available (optional dependency)."""
    try:
        import weasyprint  # noqa: F401

        return True
    except ImportError:
        return False


def _html_escape(text: str) -> str:
    """Basic HTML escaping for embedding in reports."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _render_ssp_report(mind, embedder, nodes_list, synapses) -> str:
    """Render an SSP (System Security Plan) section as HTML."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    project = mind.project_path.name

    # Group nodes by compliance control
    control_map: dict[str, list[dict]] = {}
    for node in nodes_list:
        cm = node.get("compliance_matches") or []
        for m in cm:
            ctrl = m.get("control_id", "")
            control_map.setdefault(ctrl, []).append(node)

    # Also gather from synapse store
    if synapses is not None:
        try:
            all_edges = synapses.edges(min_weight=0.0, limit=5000)
            for edge in all_edges:
                src, tgt = edge.get("source", ""), edge.get("target", "")
                for sid in (src, tgt):
                    if str(sid).startswith("compliance:"):
                        parts = str(sid).split(":", 2)
                        if len(parts) == 3:
                            ctrl_id = parts[2]
                            code_side = tgt if sid == src else src
                            # Find matching node
                            for node in nodes_list:
                                if node.get("id", "") == code_side:
                                    if ctrl_id not in control_map:
                                        control_map[ctrl_id] = []
                                    if node not in control_map[ctrl_id]:
                                        control_map[ctrl_id].append(node)
                                    break
        except Exception:
            pass

    # Build HTML
    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head><meta charset='utf-8'>",
        f"<title>NeuralMind SSP Report — {_html_escape(project)}</title>",
        "<style>",
        "  body { font-family: 'Helvetica', 'Arial', sans-serif; margin: 40px; }",
        "  h1 { color: #1a56db; border-bottom: 2px solid #1a56db; padding-bottom: 8px; }",
        "  h2 { color: #374151; margin-top: 30px; }",
        "  h3 { color: #4b5563; }",
        "  table { width: 100%; border-collapse: collapse; margin: 16px 0; }",
        "  th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid #e5e7eb; }",
        "  th { background-color: #f3f4f6; font-weight: 600; }",
        "  .meta { color: #6b7280; font-size: 0.9em; margin-bottom: 24px; }",
        "  .empty { color: #9ca3af; font-style: italic; }",
        "  .summary-box { border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 20px 0; }",
        "</style></head><body>",
    ]

    html_parts.append(f"<h1>System Security Plan — {_html_escape(project)}</h1>")
    html_parts.append(f'<p class="meta">Generated: {now} | NeuralMind v2.0</p>')

    # Summary
    html_parts.append('<div class="summary-box">')
    html_parts.append(f"<p><strong>Total Nodes:</strong> {len(nodes_list)}</p>")
    html_parts.append(f"<p><strong>Controls Mapped:</strong> {len(control_map)}</p>")
    html_parts.append(
        f"<p><strong>Synapse Store:</strong> {'Enabled' if synapses is not None else 'Disabled'}</p>"
    )
    html_parts.append("</div>")

    if not control_map:
        html_parts.append(
            '<p class="empty">No compliance-to-code mappings found. '
            "Ingest a compliance framework and annotate code with "
            "compliance markers first.</p>"
        )
    else:
        for ctrl_id in sorted(control_map.keys()):
            nodes = control_map[ctrl_id]
            html_parts.append(f"<h2>Control: {_html_escape(ctrl_id)}</h2>")
            html_parts.append(f"<p>{len(nodes)} code node(s) mapped</p>")
            html_parts.append("<table><tr>")
            html_parts.append("<th>Node ID</th><th>Label</th><th>File</th><th>Type</th>")
            html_parts.append("</tr>")
            for n in nodes:
                html_parts.append("<tr>")
                html_parts.append(f"<td>{_html_escape(n.get('id', ''))}</td>")
                html_parts.append(f"<td>{_html_escape(n.get('label', ''))}</td>")
                html_parts.append(f"<td>{_html_escape(n.get('source_file', ''))}</td>")
                html_parts.append(f"<td>{_html_escape(n.get('file_type', ''))}</td>")
                html_parts.append("</tr>")
            html_parts.append("</table>")

    html_parts.append(
        "<hr><p class='meta'>Generated by NeuralMind Audit Export. "
        "This is an automated evidence report and should be reviewed "
        "by a qualified assessor.</p>"
    )
    html_parts.append("</body></html>")

    return "\n".join(html_parts)


def export_pdf(
    mind,
    output_path: str | Path,
    *,
    report: str = "ssp",
) -> dict:
    """Export NeuralMind state to PDF.

    Args:
        mind: A ``NeuralMind`` instance with a built index.
        output_path: Where to write the PDF file.
        report: Report type (``ssp`` for System Security Plan).

    Returns:
        Dict with ``path``, ``pages``, and ``report_type``.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not _find_weasyprint():
        return {
            "error": ("PDF export requires weasyprint. Install: pip install weasyprint"),
        }

    import weasyprint

    embedder = getattr(mind, "embedder", None)
    nodes_list = getattr(embedder, "nodes", None) or []
    synapses = getattr(mind, "synapses", None)

    if report == "ssp":
        html = _render_ssp_report(mind, embedder, nodes_list, synapses)
    else:
        html = _render_ssp_report(mind, embedder, nodes_list, synapses)

    try:
        doc = weasyprint.HTML(string=html).render()
        doc.write_pdf(str(output_path))
    except Exception as exc:
        return {"error": f"PDF generation failed: {exc}"}

    pages = len(doc.pages) if hasattr(doc, "pages") else 0
    print(f"Exported {report.upper()} report ({pages} pages) to {output_path}")

    return {
        "path": str(output_path),
        "pages": pages,
        "report_type": report,
    }


# --------------------------------------------------------------------------- #
# CLI integration helper
# --------------------------------------------------------------------------- #


def run_export(args, mind=None):
    """Run export from CLI args. Returns export result dict."""
    fmt = getattr(args, "format", "csv")
    output_path = getattr(args, "output", f"neuralmind_export.{'csv' if fmt == 'csv' else 'pdf'}")
    controls = getattr(args, "controls", False)
    nodes = getattr(args, "nodes", False)
    report_type = getattr(args, "report", "ssp")

    if mind is None:
        from neuralmind.core import create_mind

        project_path = getattr(args, "project_path", ".")
        mind = create_mind(str(project_path), auto_build=True)

    if fmt == "csv":
        return export_csv(
            mind,
            output_path,
            controls=controls,
            nodes=nodes,
        )

    if fmt == "pdf":
        return export_pdf(
            mind,
            output_path,
            report=report_type,
        )

    return {"error": f"Unsupported format: {fmt}"}
