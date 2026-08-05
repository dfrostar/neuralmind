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

    @classmethod
    def from_decision(cls, decision: dict) -> ContentNode:
        """Create a ContentNode from a decision record.

        Expects ``decision`` dict with keys: ``title``, ``date``,
        ``participants``, ``summary``, ``decisions``, ``action_items``,
        ``tags``, ``status``, ``impact``, ``alternatives``.

        Used for: architecture decisions, strategic choices, product
        direction decisions, policy decisions.
        """
        title = decision.get("title", "Untitled Decision")
        date = decision.get("date", "")
        participants = decision.get("participants", [])
        summary = decision.get("summary", "")
        decisions_list = decision.get("decisions", [])
        action_items = decision.get("action_items", [])
        tags = decision.get("tags", [])
        status = decision.get("status", "")
        impact = decision.get("impact", "")
        alternatives = decision.get("alternatives", [])
        source = decision.get("source", "")

        # Build rich text for embedding
        text_parts = [f"Decision: {title}"]
        if date:
            text_parts.append(f"Date: {date}")
        if status:
            text_parts.append(f"Status: {status}")
        if impact:
            text_parts.append(f"Impact: {impact}")
        if participants:
            text_parts.append(f"Participants: {', '.join(participants)}")
        if summary:
            text_parts.append(f"Summary: {summary}")
        if decisions_list:
            text_parts.append("Decisions:")
            for d in decisions_list:
                text_parts.append(f"  - {d}")
        if alternatives:
            text_parts.append("Alternatives Considered:")
            for a in alternatives:
                text_parts.append(f"  - {a}")
        if action_items:
            text_parts.append("Action Items:")
            for ai in action_items:
                owner = ai.get("owner", "") if isinstance(ai, dict) else ""
                task = ai.get("task", ai) if isinstance(ai, dict) else ai
                due = ai.get("due", "") if isinstance(ai, dict) else ""
                line = f"  - {task}"
                if owner:
                    line += f" (owner: {owner})"
                if due:
                    line += f" [due: {due}]"
                text_parts.append(line)
        if tags:
            text_parts.append(f"Tags: {', '.join(tags)}")

        # Node ID from title hash + date for uniqueness
        slug = title.lower().replace(" ", "_")[:40]
        date_str = date.replace("-", "") if date else "nodate"
        node_id = f"decision:{slug}.{date_str}"

        return cls(
            node_id=node_id,
            label=title,
            content_type="decision",
            text="\n".join(text_parts),
            metadata={
                "title": title,
                "date": date,
                "participants": participants,
                "decisions": decisions_list,
                "action_items": action_items,
                "tags": tags,
                "status": status,
                "impact": impact,
                "alternatives": alternatives,
                "source": source,
                "content_category": "business_context",
            },
        )

    @classmethod
    def from_meeting_note(cls, note: dict) -> ContentNode:
        """Create a ContentNode from meeting notes.

        Expects ``note`` dict with keys: ``title``, ``date``,
        ``attendees``, ``agenda``, ``notes``, ``decisions``,
        ``action_items``, ``tags``.
        """
        title = note.get("title", "Meeting")
        date = note.get("date", "")
        attendees = note.get("attendees", [])
        agenda = note.get("agenda", [])
        notes_text = note.get("notes", "")
        decisions_list = note.get("decisions", [])
        action_items = note.get("action_items", [])
        tags = note.get("tags", [])
        meeting_type = note.get("type", "")
        source = note.get("source", "")

        text_parts = [f"Meeting: {title}"]
        if date:
            text_parts.append(f"Date: {date}")
        if meeting_type:
            text_parts.append(f"Type: {meeting_type}")
        if attendees:
            text_parts.append(f"Attendees: {', '.join(attendees)}")
        if agenda:
            text_parts.append("Agenda:")
            for item in agenda:
                text_parts.append(f"  - {item}")
        if notes_text:
            text_parts.append(f"Notes:\n{notes_text}")
        if decisions_list:
            text_parts.append("Decisions Made:")
            for d in decisions_list:
                text_parts.append(f"  - {d}")
        if action_items:
            text_parts.append("Action Items:")
            for ai in action_items:
                owner = ai.get("owner", "") if isinstance(ai, dict) else ""
                task = ai.get("task", ai) if isinstance(ai, dict) else ai
                due = ai.get("due", "") if isinstance(ai, dict) else ""
                line = f"  - {task}"
                if owner:
                    line += f" (owner: {owner})"
                if due:
                    line += f" [due: {due}]"
                text_parts.append(line)
        if tags:
            text_parts.append(f"Tags: {', '.join(tags)}")

        slug = title.lower().replace(" ", "_")[:40]
        date_str = date.replace("-", "") if date else "nodate"
        node_id = f"meeting:{slug}.{date_str}"

        return cls(
            node_id=node_id,
            label=title,
            content_type="meeting_note",
            text="\n".join(text_parts),
            metadata={
                "title": title,
                "date": date,
                "attendees": attendees,
                "agenda": agenda,
                "decisions": decisions_list,
                "action_items": action_items,
                "tags": tags,
                "type": meeting_type,
                "source": source,
                "content_category": "business_context",
            },
        )

    @classmethod
    def from_sop(cls, sop: dict) -> ContentNode:
        """Create a ContentNode from a Standard Operating Procedure.

        Expects ``sop`` dict with keys: ``title``, ``version``,
        ``purpose``, ``scope``, ``steps``, ``responsibilities``,
        ``references``, ``tags``.
        """
        title = sop.get("title", "SOP")
        version = sop.get("version", "")
        purpose = sop.get("purpose", "")
        scope = sop.get("scope", "")
        steps = sop.get("steps", [])
        responsibilities = sop.get("responsibilities", {})
        references = sop.get("references", [])
        tags = sop.get("tags", [])
        owner = sop.get("owner", "")
        review_date = sop.get("review_date", "")
        source = sop.get("source", "")

        text_parts = [f"SOP: {title}"]
        if version:
            text_parts.append(f"Version: {version}")
        if owner:
            text_parts.append(f"Owner: {owner}")
        if review_date:
            text_parts.append(f"Review Date: {review_date}")
        if purpose:
            text_parts.append(f"Purpose: {purpose}")
        if scope:
            text_parts.append(f"Scope: {scope}")
        if steps:
            text_parts.append("Procedure Steps:")
            for i, step in enumerate(steps, 1):
                text_parts.append(f"  {i}. {step}")
        if responsibilities:
            text_parts.append("Responsibilities:")
            for role, duties in responsibilities.items():
                text_parts.append(f"  - {role}: {duties}")
        if references:
            text_parts.append("References:")
            for ref in references:
                text_parts.append(f"  - {ref}")
        if tags:
            text_parts.append(f"Tags: {', '.join(tags)}")

        slug = title.lower().replace(" ", "_")[:40]
        ver = version.replace(".", "_") if version else "v0"
        node_id = f"sop:{slug}.{ver}"

        return cls(
            node_id=node_id,
            label=title,
            content_type="sop",
            text="\n".join(text_parts),
            metadata={
                "title": title,
                "version": version,
                "purpose": purpose,
                "scope": scope,
                "steps": steps,
                "responsibilities": responsibilities,
                "references": references,
                "tags": tags,
                "owner": owner,
                "review_date": review_date,
                "source": source,
                "content_category": "business_context",
            },
        )

    @classmethod
    def from_policy(cls, policy: dict) -> ContentNode:
        """Create a ContentNode from a business policy.

        Expects ``policy`` dict with keys: ``title``, ``effective_date``,
        ``policy_type``, ``statement``, ``rationale``, ``requirements``,
        ``exceptions``, ``tags``.
        """
        title = policy.get("title", "Policy")
        effective_date = policy.get("effective_date", "")
        policy_type = policy.get("policy_type", "")
        statement = policy.get("statement", "")
        rationale = policy.get("rationale", "")
        requirements = policy.get("requirements", [])
        exceptions = policy.get("exceptions", [])
        tags = policy.get("tags", [])
        owner = policy.get("owner", "")
        source = policy.get("source", "")

        text_parts = [f"Policy: {title}"]
        if effective_date:
            text_parts.append(f"Effective: {effective_date}")
        if policy_type:
            text_parts.append(f"Type: {policy_type}")
        if owner:
            text_parts.append(f"Owner: {owner}")
        if statement:
            text_parts.append(f"Policy Statement: {statement}")
        if rationale:
            text_parts.append(f"Rationale: {rationale}")
        if requirements:
            text_parts.append("Requirements:")
            for r in requirements:
                text_parts.append(f"  - {r}")
        if exceptions:
            text_parts.append("Exceptions:")
            for e in exceptions:
                text_parts.append(f"  - {e}")
        if tags:
            text_parts.append(f"Tags: {', '.join(tags)}")

        slug = title.lower().replace(" ", "_")[:40]
        date_str = effective_date.replace("-", "") if effective_date else "nodate"
        node_id = f"policy:{slug}.{date_str}"

        return cls(
            node_id=node_id,
            label=title,
            content_type="policy",
            text="\n".join(text_parts),
            metadata={
                "title": title,
                "effective_date": effective_date,
                "policy_type": policy_type,
                "statement": statement,
                "rationale": rationale,
                "requirements": requirements,
                "exceptions": exceptions,
                "tags": tags,
                "owner": owner,
                "source": source,
                "content_category": "business_context",
            },
        )
