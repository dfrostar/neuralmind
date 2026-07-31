"""
content_node.py — Non-code content nodes for NeuralMind.

Extends the NeuralMind code graph to include first-class nodes for
documents, compliance frameworks, API specs, and other structured
content alongside code symbols.

Each ContentNode is converted to the same text representation the
embedder uses for code nodes, making all content searchable via
semantic and BM25 retrieval.

Usage:
    from neuralmind.content_node import ContentNode

    practice = ContentNode(
        node_id="cmc:AC.L2-3.1.1",
        label="Authorized Access Control",
        content_type="cmmc_practice",
        text="AC.L2-3.1.1: Authorized Access Control - Limit system access...",
        metadata={"domain": "AC", "framework": "CMMC"},
    )

    # Get graph-compatible node dict for the embedder
    node_dict = practice.to_graph_node()
"""

from __future__ import annotations

from typing import Any


class ContentNode:
    """A non-code content node that lives alongside code nodes in the graph.

    Attributes:
        node_id: Unique identifier (e.g. ``cmc:AC.L2-3.1.1``)
        label: Human-readable title
        content_type: Type discriminator (e.g. ``cmmc_practice``,
                     ``document``, ``api_spec``)
        text: Full text content for embedding and search
        metadata: Additional fields for filtering (framework, domain, url, etc.)
    """

    def __init__(
        self,
        node_id: str,
        label: str,
        content_type: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.node_id = node_id
        self.label = label
        self.content_type = content_type
        self.text = text
        self.metadata = metadata or {}

    def to_graph_node(self) -> dict[str, Any]:
        """Convert to a graph-compatible node dict for the embedder.

        Returns a dict with the same shape as graphgen.py node entries,
        so the embedder's ``_node_to_text()`` and ``embed_nodes()``
        can process it alongside code nodes.
        """
        return {
            "id": self.node_id,
            "label": self.label,
            "file_type": self.content_type,
            "source_file": self.metadata.get("source", ""),
            "source_location": "",
            "community": -1,
            "norm_label": self.label.lower(),
            "content_text": self.text,
            "metadata": self.metadata,
        }

    @classmethod
    def from_cmmc_practice(cls, practice: dict) -> ContentNode:
        """Create a ContentNode from a CMMC practice registry entry.

        Expects ``practice`` dict with keys: ``id``, ``title``,
        ``description``, ``guide``, ``domain``.
        """
        practice_id = practice.get("id", "UNKNOWN")
        title = practice.get("title", "")
        description = practice.get("description", "")
        guide = practice.get("guide", "")
        domain = practice.get("domain", "")

        text_parts = [
            f"CMMC Practice: {practice_id}",
            f"Title: {title}",
            f"Domain: {domain}",
            f"Description: {description}",
            f"Guide: {guide}",
        ]

        return cls(
            node_id=f"cmc:{practice_id}",
            label=f"{practice_id}: {title}",
            content_type="cmmc_practice",
            text="\n".join(text_parts),
            metadata={
                "practice_id": practice_id,
                "title": title,
                "domain": domain,
                "framework": "CMMC",
                "source": "CMMC Practice Registry",
            },
        )

    @classmethod
    def from_compliance_registry_entry(
        cls,
        entry: dict,
        framework: str = "CMMC",
        id_field: str = "id",
        title_field: str = "title",
        description_field: str = "description",
        guide_field: str = "guide",
        domain_field: str = "domain",
        prefix: str = "cmc",
    ) -> ContentNode:
        """Create a ContentNode from a generic compliance registry entry.

        Allows plugging any compliance framework (SOX, NIST, HIPAA)
        that follows a similar id/title/description/guide structure.
        """
        entry_id = entry.get(id_field, "UNKNOWN")
        title = entry.get(title_field, "")
        description = entry.get(description_field, "")
        guide = entry.get(guide_field, "")
        domain = entry.get(domain_field, "")

        text_parts = [
            f"{framework} Practice: {entry_id}",
            f"Title: {title}",
            f"Domain: {domain}",
            f"Description: {description}",
            f"Guide: {guide}",
        ]

        return cls(
            node_id=f"{prefix}:{entry_id}",
            label=f"{entry_id}: {title}",
            content_type=f"{framework.lower().replace(' ', '_')}_practice",
            text="\n".join(text_parts),
            metadata={
                "practice_id": entry_id,
                "title": title,
                "domain": domain,
                "framework": framework,
            },
        )
