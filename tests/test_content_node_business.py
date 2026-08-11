"""Tests for business context ContentNode factory methods."""

from neuralmind.content_node import ContentNode


def test_from_decision():
    decision = {
        "title": "Use PostgreSQL for CMMC audit logs",
        "date": "2026-08-01",
        "participants": ["Darren", "Rye"],
        "summary": "Selected PostgreSQL with pgaudit for immutable audit trail.",
        "decisions": [
            "Use PostgreSQL 16+ with pgaudit extension",
            "Append-only audit table with hash chain",
        ],
        "action_items": [
            {"task": "Provision RDS instance", "owner": "Darren", "due": "2026-08-15"},
            {"task": "Configure pgaudit", "owner": "Darren", "due": "2026-08-20"},
        ],
        "tags": ["database", "audit", "cmmc"],
        "status": "approved",
        "impact": "high",
        "alternatives": ["SQLite WAL", "CockroachDB"],
    }
    node = ContentNode.from_decision(decision)
    assert node.content_type == "decision"
    assert node.node_id.startswith("decision:")
    assert node.metadata["content_category"] == "business_context"
    assert "PostgreSQL" in node.text
    assert "Darren" in node.text
    assert "SQLite WAL" in node.text
    graph = node.to_graph_node()
    assert graph["id"] == node.node_id
    assert graph["content_text"] == node.text


def test_from_meeting_note():
    note = {
        "title": "Weekly standup",
        "date": "2026-08-05",
        "attendees": ["Darren", "Claude"],
        "type": "standup",
        "agenda": ["CMMC progress", "NeuralMind ingest"],
        "notes": "Second brain scope decided.",
        "decisions": ["Second brain expands to business context"],
        "action_items": [
            {"task": "Build content types", "owner": "Claude"},
        ],
        "tags": ["standup"],
    }
    node = ContentNode.from_meeting_note(note)
    assert node.content_type == "meeting_note"
    assert node.node_id.startswith("meeting:")
    assert "Weekly standup" in node.text
    assert "Claude" in node.text
    assert node.metadata["content_category"] == "business_context"


def test_from_sop():
    sop = {
        "title": "Incident Response",
        "version": "1.0",
        "purpose": "Define IR procedure",
        "scope": "All production incidents",
        "steps": ["Detect", "Contain", "Eradicate", "Recover", "Lessons learned"],
        "responsibilities": {"IR Lead": "Coordinate response", "Engineer": "Technical triage"},
        "references": ["NIST SP 800-61"],
        "tags": ["security", "ir"],
        "owner": "Darren",
    }
    node = ContentNode.from_sop(sop)
    assert node.content_type == "sop"
    assert node.node_id.startswith("sop:")
    assert "Incident Response" in node.text
    assert "Detect" in node.text
    assert node.metadata["content_category"] == "business_context"


def test_from_policy():
    policy = {
        "title": "Data Retention",
        "effective_date": "2026-09-01",
        "policy_type": "compliance",
        "statement": "Audit logs retained for 7 years.",
        "rationale": "CMMC requirement",
        "requirements": ["Immutable storage", "Yearly verification"],
        "exceptions": [],
        "tags": ["retention", "cmmc"],
        "owner": "Darren",
    }
    node = ContentNode.from_policy(policy)
    assert node.content_type == "policy"
    assert node.node_id.startswith("policy:")
    assert "Data Retention" in node.text
    assert "7 years" in node.text
    assert node.metadata["content_category"] == "business_context"


def test_decision_minimal():
    """Minimal decision with only title."""
    node = ContentNode.from_decision({"title": "Go with option A"})
    assert node.content_type == "decision"
    assert node.label == "Go with option A"
    assert "Decision: Go with option A" in node.text


def test_meeting_note_minimal():
    node = ContentNode.from_meeting_note({"title": "Sync"})
    assert node.content_type == "meeting_note"
    assert node.label == "Sync"


def test_sop_minimal():
    node = ContentNode.from_sop({"title": "Deploy process"})
    assert node.content_type == "sop"


def test_policy_minimal():
    node = ContentNode.from_policy({"title": "Access policy"})
    assert node.content_type == "policy"


def test_all_factories_have_content_category():
    """All business context types must have content_category metadata."""
    factories = [
        ContentNode.from_decision({"title": "T"}),
        ContentNode.from_meeting_note({"title": "T"}),
        ContentNode.from_sop({"title": "T"}),
        ContentNode.from_policy({"title": "T"}),
    ]
    for node in factories:
        assert node.metadata["content_category"] == "business_context"
