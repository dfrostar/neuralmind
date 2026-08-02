"""
turbo_vec_doc_evolver.py — TurboVec-accelerated DocEvolver.

The stock DocEvolver's bottleneck is ``_evaluate_candidate``: it patches a
JSDoc variant into the source, then runs a full ``neuralmind build``
subprocess (120s timeout) to reindex before each query. With 5 spots ×
5 generations × 5 population = 125 evaluations, that's 4+ hours.

This subclass replaces that with TurboVec incremental reindex:

1.  Patch JSDoc into source file
2.  Extract just the method text (regex-based, no full graphify)
3.  Re-embed that single node via ``TurboVecEmbedder.embed_content()``
4.  Query in-process
5.  Restore original content + original embedding

Result: ~30s per spot instead of ~30min.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from neuralmind.core import NeuralMind
from neuralmind.doc_evolver import (
    BlindSpot,
    DocEvolver,
    JSDocVariant,
    _camel_to_words,
)

log = logging.getLogger(__name__)


class TurboVecDocEvolver(DocEvolver):
    """DocEvolver accelerated with TurboVec incremental reindex.

    Instead of running ``neuralmind build`` subprocess per candidate,
    re-embeds only the patched method node in-process.
    """

    def __init__(
        self,
        project_path: str | Path,
        blind_spots: list[BlindSpot],
        population_size: int | None = None,
        generations: int | None = None,
        hysteresis: float | None = None,
        mind: NeuralMind | None = None,
    ):
        super().__init__(
            project_path=project_path,
            blind_spots=blind_spots,
            population_size=population_size,
            generations=generations,
            hysteresis=hysteresis,
            query_fn=None,
        )
        if mind is None:
            mind = NeuralMind(str(self.project_path), backend_type="turbovec")
            mind.build()
        self.mind = mind
        self.embedder = mind.embedder

    def _evaluate_candidate(self, spot: BlindSpot, variant: JSDocVariant) -> float:
        """Score a variant using TurboVec incremental reindex.

        Patches JSDoc into source, re-embeds just that method's node,
        queries in-process, then restores.
        """
        file_path = self.project_path / spot.file_path
        if not file_path.exists():
            log.warning("source file not found: %s", file_path)
            return 0.0

        original_content = file_path.read_text(encoding="utf-8")
        lines = original_content.splitlines()

        # Find the method line
        insert_line = self._find_method_line(lines, spot)
        if insert_line is None:
            log.warning("could not locate method %s in %s", spot.name, spot.file_path)
            return 0.0

        # Patch in the JSDoc
        jsdoc_lines = variant.text.splitlines()
        patched_lines = lines[:insert_line] + jsdoc_lines + lines[insert_line:]
        patched_content = "\n".join(patched_lines) + "\n"

        # Backup + patch
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        shutil.copy2(file_path, backup_path)
        try:
            file_path.write_text(patched_content, encoding="utf-8")

            # Build query from method name
            query = _camel_to_words(spot.name)

            # Extract method text for re-embedding
            method_text = self._extract_method_text(
                patched_lines, insert_line, len(jsdoc_lines), spot
            )
            if not method_text:
                return 0.0

            # Save original node state
            node_id = self._method_node_id(spot)
            original_node = self._get_node_by_id(node_id)
            original_meta = original_node.copy() if original_node else None

            # Create ContentNode with JSDoc-enhanced text
            from neuralmind.content_node import ContentNode

            cn = ContentNode(
                node_id=node_id,
                label=spot.name,
                content_type="code",
                text=method_text,
                metadata={
                    "source_file": spot.file_path,
                    "source_location": str(spot.line),
                    "file_type": "code",
                },
            )

            # Upsert into TurboVec index
            self.embedder.embed_content([cn.to_graph_node()])

            # Query in-process
            results = self.mind.search(query, n=5)
            ranked_files = [
                r.get("metadata", {}).get("source_file", "")
                for r in results
                if r.get("metadata", {}).get("source_file")
            ]

            # Score by rank of correct file
            target_file = spot.file_path.replace("\\", "/")
            for rank, filepath in enumerate(ranked_files, start=1):
                if filepath.replace("\\", "/") == target_file:
                    return 1.0 / rank

            return 0.0

        except Exception as exc:
            log.warning("evaluation failed for %s: %s", spot.name, exc)
            return 0.0

        finally:
            # Restore original content
            backup_path.replace(file_path)
            # Restore original embedding
            if original_meta:
                self.embedder.embed_content([original_meta])

    def _extract_method_text(
        self, lines: list[str], insert_line: int, jsdoc_lines_count: int, spot: BlindSpot
    ) -> str:
        """Extract the method's full text (JSDoc + signature + body start)."""
        start = insert_line
        # Find the end of the method (balance braces)
        end = start + jsdoc_lines_count
        brace_count = 0
        found_brace = False
        for i in range(start + jsdoc_lines_count, min(len(lines), start + jsdoc_lines_count + 50)):
            line = lines[i]
            brace_count += line.count("{") - line.count("}")
            if "{" in line and not found_brace:
                found_brace = True
            if found_brace and brace_count <= 0:
                end = i + 1
                break
            end = i + 1

        return "\n".join(lines[start:end])

    def _method_node_id(self, spot: BlindSpot) -> str:
        """Find the node id for this method by matching source file + label."""
        # Target label
        target_label = spot.name.lower().strip()

        # File stem for matching
        fp = spot.file_path.replace("/", "_").replace(".", "_").lower()

        # First pass: match on file path AND exact label
        for n in getattr(self.embedder, "nodes", []) or []:
            sf = n.get("source_file", "").lower().replace("/", "_").replace(".", "_")
            label = n.get("label", "").lower()

            if fp.endswith(sf.replace("/", "_").replace(".", "_")) and label == target_label:
                return str(n.get("id"))

        # Second pass: match on file path AND partial label
        for n in getattr(self.embedder, "nodes", []) or []:
            sf = n.get("source_file", "").lower()
            label = n.get("label", "").lower()

            if sf.endswith(spot.file_path.lower().replace("/", "")) and (
                target_label in label or label in target_label
            ):
                return str(n.get("id"))

        return None

    def _get_node_by_id(self, node_id: str) -> dict | None:
        """Look up an existing node by id from the embedder."""
        for n in getattr(self.embedder, "nodes", []) or []:
            if str(n.get("id")) == node_id:
                return n
        return None

    def _run_query(self, query: str) -> list[str]:
        """In-process query using TurboVec."""
        results = self.mind.search(query, n=5)
        return [
            r.get("metadata", {}).get("source_file", "")
            for r in results
            if r.get("metadata", {}).get("source_file")
        ]

    def patch_winners(self, results: list) -> list[str]:
        """Patch winning JSDoc variants into source files.

        Only patches variants that were promoted (improved over baseline).
        Handles multiple patches in the same file by tracking line offsets.
        """
        # Group by file
        by_file: dict[str, list[tuple[int, Any]]] = {}
        for r in results:
            if r.best_variant is None or not r.promoted:
                continue
            by_file.setdefault(r.file_path, []).append((r.line, r))

        modified: list[str] = []
        for file_path, entries in by_file.items():
            fp = self.project_path / file_path
            if not fp.exists():
                continue

            # Sort by line number (descending) so patching doesn't shift later lines
            entries.sort(key=lambda x: x[0], reverse=True)

            content = fp.read_text(encoding="utf-8")
            lines = content.splitlines()

            for line_num, result in entries:
                insert_idx = self._find_method_line_by_number(lines, line_num)
                if insert_idx is None:
                    continue
                if insert_idx > 0 and lines[insert_idx - 1].strip().endswith("*/"):
                    continue  # Already has JSDoc

                jsdoc_lines = result.best_variant.text.splitlines()
                lines = lines[:insert_idx] + jsdoc_lines + lines[insert_idx:]

            new_content = "\n".join(lines) + "\n"
            fp.write_text(new_content, encoding="utf-8")
            modified.append(file_path)

        return modified
