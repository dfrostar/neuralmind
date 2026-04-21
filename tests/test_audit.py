"""Tests for NeuralMind audit trail (NIST AI RMF compliance)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from neuralmind.audit import (
    AuditLogEntry,
    CodeStateSnapshot,
    EvidenceItem,
    ModelMetadata,
    audit_log_dir,
    audit_log_file,
    count_audit_entries,
    export_nist_rmf_report,
    generate_nist_rmf_report,
    get_git_branch,
    get_git_commit,
    log_audit_entry,
    read_audit_entries,
)


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory."""
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    (project_path / ".neuralmind").mkdir()
    return project_path


@pytest.fixture
def sample_evidence_item():
    """Create a sample evidence item."""
    return EvidenceItem(
        entity_id="authenticate_user",
        entity_type="function",
        entity_name="authenticate_user",
        file_path="auth/handlers.py",
        community_id=5,
        relevance_score=0.92,
        evidence_type="EXTRACTED",
        line_number=42,
        snippet="def authenticate_user(username, password):",
    )


@pytest.fixture
def sample_model_metadata():
    """Create sample model metadata."""
    return ModelMetadata(
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        embedding_backend="chromadb",
        embedding_dimensions=384,
        model_version="v1",
        created_at="2026-04-21T00:00:00Z",
    )


@pytest.fixture
def sample_code_state():
    """Create sample code state snapshot."""
    return CodeStateSnapshot(
        git_commit="a1b2c3d4e5f6",
        git_branch="main",
        code_hash="sha256_hash_here",
    )


@pytest.fixture
def sample_audit_entry(sample_evidence_item, sample_model_metadata, sample_code_state):
    """Create a sample audit log entry."""
    return AuditLogEntry(
        audit_id="550e8400-e29b-41d4-a716-446655440000",
        query_text="How does authentication work?",
        timestamp="2026-04-21T14:30:00Z",
        project_path="/home/user/myproject",
        user_id="alice@company.com",
        evidence=[sample_evidence_item],
        evidence_count=1,
        evidence_type_breakdown={"EXTRACTED": 1},
        tokens_used=847,
        tokens_baseline=50000,
        reduction_ratio=59.0,
        layer_breakdown={"L0": 150, "L1": 600, "L2": 97},
        model_metadata=sample_model_metadata,
        decision_deterministic=True,
        confidence_metrics={
            "overall": 0.95,
            "evidence_quality": 0.95,
            "deterministic": 1.0,
        },
        code_state=sample_code_state,
        reproducibility_score=0.95,
    )


# ============================================================================
# Test Audit Directory Management
# ============================================================================


def test_audit_log_dir(temp_project):
    """Test audit log directory path generation."""
    audit_dir = audit_log_dir(temp_project)
    assert audit_dir == temp_project / ".neuralmind" / "audit"


def test_audit_log_file(temp_project):
    """Test audit log file path generation."""
    log_file = audit_log_file(temp_project)
    assert log_file == temp_project / ".neuralmind" / "audit" / "queries.jsonl"


# ============================================================================
# Test Git State Capture
# ============================================================================


@patch("neuralmind.audit.subprocess.run")
def test_get_git_commit_success(mock_run):
    """Test successful git commit retrieval."""
    mock_run.return_value = MagicMock(
        returncode=0, stdout="a1b2c3d4e5f6\n", stderr=""
    )

    commit = get_git_commit(".")
    assert commit == "a1b2c3d4e5f6"
    mock_run.assert_called_once()


@patch("neuralmind.audit.subprocess.run")
def test_get_git_commit_failure(mock_run):
    """Test git commit retrieval when not in git repo."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fatal")

    commit = get_git_commit(".")
    assert commit is None


@patch("neuralmind.audit.subprocess.run")
def test_get_git_branch_success(mock_run):
    """Test successful git branch retrieval."""
    mock_run.return_value = MagicMock(returncode=0, stdout="main\n", stderr="")

    branch = get_git_branch(".")
    assert branch == "main"


@patch("neuralmind.audit.subprocess.run")
def test_get_git_branch_failure(mock_run):
    """Test git branch retrieval when not in git repo."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fatal")

    branch = get_git_branch(".")
    assert branch is None


# ============================================================================
# Test Audit Entry Serialization
# ============================================================================


def test_audit_entry_to_dict(sample_audit_entry):
    """Test audit entry conversion to dictionary."""
    entry_dict = sample_audit_entry.to_dict()

    assert entry_dict["audit_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert entry_dict["query_text"] == "How does authentication work?"
    assert entry_dict["tokens_used"] == 847
    assert entry_dict["reduction_ratio"] == 59.0
    assert entry_dict["reproducibility_score"] == 0.95


def test_audit_entry_dict_structure(sample_audit_entry):
    """Test that audit entry dict has all required fields."""
    entry_dict = sample_audit_entry.to_dict()

    required_fields = [
        "audit_id",
        "query_text",
        "timestamp",
        "project_path",
        "evidence",
        "tokens_used",
        "reduction_ratio",
        "model_metadata",
        "code_state",
        "reproducibility_score",
    ]

    for field in required_fields:
        assert field in entry_dict


# ============================================================================
# Test Audit Logging
# ============================================================================


def test_log_audit_entry(temp_project, sample_audit_entry):
    """Test logging an audit entry to file."""
    success = log_audit_entry(temp_project, sample_audit_entry)

    assert success is True
    log_file = audit_log_file(temp_project)
    assert log_file.exists()


def test_log_audit_entry_creates_directory(tmp_path):
    """Test that logging creates audit directory if missing."""
    project_path = tmp_path / "project"
    project_path.mkdir()

    entry = AuditLogEntry(
        audit_id="test-id",
        query_text="test",
        timestamp="2026-04-21T00:00:00Z",
        project_path=str(project_path),
    )

    success = log_audit_entry(project_path, entry)

    assert success is True
    assert (project_path / ".neuralmind" / "audit").exists()


def test_log_audit_entry_appends(temp_project, sample_audit_entry):
    """Test that multiple entries are appended (JSONL format)."""
    entry1 = sample_audit_entry
    entry2 = AuditLogEntry(
        audit_id="test-id-2",
        query_text="Another question?",
        timestamp="2026-04-21T14:31:00Z",
        project_path=str(temp_project),
    )

    log_audit_entry(temp_project, entry1)
    log_audit_entry(temp_project, entry2)

    log_file = audit_log_file(temp_project)
    lines = log_file.read_text().strip().split("\n")

    assert len(lines) == 2
    data1 = json.loads(lines[0])
    data2 = json.loads(lines[1])
    assert data1["audit_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert data2["audit_id"] == "test-id-2"


# ============================================================================
# Test Audit Entry Reading
# ============================================================================


def test_read_audit_entries_empty(temp_project):
    """Test reading audit entries from non-existent file."""
    entries = read_audit_entries(temp_project)
    assert entries == []


def test_read_audit_entries(temp_project, sample_audit_entry):
    """Test reading audit entries from file."""
    log_audit_entry(temp_project, sample_audit_entry)

    entries = read_audit_entries(temp_project)
    assert len(entries) == 1
    assert entries[0].audit_id == sample_audit_entry.audit_id
    assert entries[0].query_text == sample_audit_entry.query_text


def test_read_audit_entries_multiple(temp_project):
    """Test reading multiple audit entries."""
    entries_to_log = []
    for i in range(5):
        entry = AuditLogEntry(
            audit_id=f"id-{i}",
            query_text=f"Question {i}?",
            timestamp="2026-04-21T14:30:00Z",
            project_path=str(temp_project),
        )
        entries_to_log.append(entry)
        log_audit_entry(temp_project, entry)

    entries = read_audit_entries(temp_project)
    assert len(entries) == 5


def test_count_audit_entries(temp_project):
    """Test counting audit entries."""
    assert count_audit_entries(temp_project) == 0

    for i in range(3):
        entry = AuditLogEntry(
            audit_id=f"id-{i}",
            query_text=f"Q{i}?",
            timestamp="2026-04-21T14:30:00Z",
            project_path=str(temp_project),
        )
        log_audit_entry(temp_project, entry)

    assert count_audit_entries(temp_project) == 3


# ============================================================================
# Test NIST AI RMF Report Generation
# ============================================================================


def test_generate_nist_rmf_report_no_data(temp_project):
    """Test NIST RMF report generation with no audit data."""
    report = generate_nist_rmf_report(temp_project)

    assert report["status"] == "no_data"
    assert "message" in report
    assert "generated_at" in report


def test_generate_nist_rmf_report_basic(temp_project, sample_audit_entry):
    """Test basic NIST RMF report generation."""
    log_audit_entry(temp_project, sample_audit_entry)

    report = generate_nist_rmf_report(temp_project)

    assert "nist_rmf_phases" in report
    assert "GOVERN" in report["nist_rmf_phases"]
    assert "MAP" in report["nist_rmf_phases"]
    assert "MEASURE" in report["nist_rmf_phases"]
    assert "MANAGE" in report["nist_rmf_phases"]


def test_generate_nist_rmf_report_govern_phase(temp_project, sample_audit_entry):
    """Test GOVERN phase in NIST RMF report."""
    log_audit_entry(temp_project, sample_audit_entry)
    report = generate_nist_rmf_report(temp_project)

    govern = report["nist_rmf_phases"]["GOVERN"]
    assert govern["findings"]["audit_trail_enabled"] is True
    assert govern["findings"]["audit_entries_logged"] == 1


def test_generate_nist_rmf_report_map_phase(temp_project, sample_audit_entry):
    """Test MAP phase in NIST RMF report."""
    log_audit_entry(temp_project, sample_audit_entry)
    report = generate_nist_rmf_report(temp_project)

    map_phase = report["nist_rmf_phases"]["MAP"]
    assert map_phase["findings"]["evidence_extraction_enabled"] is True
    assert "avg_evidence_items_per_query" in map_phase["findings"]


def test_generate_nist_rmf_report_measure_phase(temp_project, sample_audit_entry):
    """Test MEASURE phase in NIST RMF report."""
    log_audit_entry(temp_project, sample_audit_entry)
    report = generate_nist_rmf_report(temp_project)

    measure = report["nist_rmf_phases"]["MEASURE"]
    assert measure["findings"]["token_reduction_enabled"] is True
    assert measure["findings"]["total_tokens_saved"] > 0


def test_generate_nist_rmf_report_manage_phase(temp_project, sample_audit_entry):
    """Test MANAGE phase in NIST RMF report."""
    log_audit_entry(temp_project, sample_audit_entry)
    report = generate_nist_rmf_report(temp_project)

    manage = report["nist_rmf_phases"]["MANAGE"]
    assert manage["findings"]["reproducibility_tracking"] is True
    assert manage["findings"]["immutable_audit_log"] is True


def test_generate_nist_rmf_report_compliance_summary(temp_project, sample_audit_entry):
    """Test compliance summary in NIST RMF report."""
    log_audit_entry(temp_project, sample_audit_entry)
    report = generate_nist_rmf_report(temp_project)

    compliance = report["compliance_summary"]
    assert compliance["nist_ai_rmf_aligned"] is True
    assert compliance["gdpr_compatible"] is True
    assert compliance["hipaa_compatible"] is True
    assert compliance["soc2_ready"] is True
    assert compliance["audit_trail_immutable"] is True


def test_generate_nist_rmf_report_aggregates_metrics(temp_project):
    """Test that report aggregates metrics from multiple entries."""
    for i in range(3):
        entry = AuditLogEntry(
            audit_id=f"id-{i}",
            query_text=f"Question {i}?",
            timestamp="2026-04-21T14:30:00Z",
            project_path=str(temp_project),
            tokens_used=1000,
            tokens_baseline=50000,
            reduction_ratio=50.0,
        )
        log_audit_entry(temp_project, entry)

    report = generate_nist_rmf_report(temp_project)

    govern = report["nist_rmf_phases"]["GOVERN"]
    assert govern["findings"]["audit_entries_logged"] == 3


# ============================================================================
# Test Report Export
# ============================================================================


def test_export_nist_rmf_report_json(temp_project, sample_audit_entry):
    """Test exporting NIST RMF report as JSON."""
    log_audit_entry(temp_project, sample_audit_entry)

    report_path = export_nist_rmf_report(temp_project, output_format="json")

    assert report_path is not None
    assert report_path.endswith(".json")
    assert Path(report_path).exists()

    # Verify JSON is valid
    with open(report_path) as f:
        data = json.load(f)
    assert "nist_rmf_phases" in data


def test_export_nist_rmf_report_markdown(temp_project, sample_audit_entry):
    """Test exporting NIST RMF report as Markdown."""
    log_audit_entry(temp_project, sample_audit_entry)

    report_path = export_nist_rmf_report(temp_project, output_format="markdown")

    assert report_path is not None
    assert report_path.endswith(".md")
    assert Path(report_path).exists()

    content = Path(report_path).read_text()
    assert "NIST" in content or "nist" in content.lower()


def test_export_nist_rmf_report_creates_directory(temp_project, sample_audit_entry):
    """Test that export creates reports directory if missing."""
    log_audit_entry(temp_project, sample_audit_entry)

    report_path = export_nist_rmf_report(temp_project, output_format="json")

    reports_dir = temp_project / ".neuralmind" / "audit" / "reports"
    assert reports_dir.exists()


# ============================================================================
# Test Edge Cases
# ============================================================================


def test_audit_entry_with_empty_evidence():
    """Test audit entry with no evidence items."""
    entry = AuditLogEntry(
        audit_id="test",
        query_text="Q?",
        timestamp="2026-04-21T00:00:00Z",
        project_path="/test",
        evidence=[],
    )

    entry_dict = entry.to_dict()
    assert entry_dict["evidence"] == []
    assert entry_dict["evidence_count"] == 0


def test_audit_entry_with_zero_tokens():
    """Test audit entry with zero token usage."""
    entry = AuditLogEntry(
        audit_id="test",
        query_text="Q?",
        timestamp="2026-04-21T00:00:00Z",
        project_path="/test",
        tokens_used=0,
        tokens_baseline=0,
        reduction_ratio=0.0,
    )

    entry_dict = entry.to_dict()
    assert entry_dict["tokens_used"] == 0
    assert entry_dict["reduction_ratio"] == 0.0


def test_model_metadata_json_serializable(sample_model_metadata):
    """Test that model metadata is JSON serializable."""
    import json

    entry = AuditLogEntry(
        audit_id="test",
        query_text="Q?",
        timestamp="2026-04-21T00:00:00Z",
        project_path="/test",
        model_metadata=sample_model_metadata,
    )

    entry_dict = entry.to_dict()
    json_str = json.dumps(entry_dict)
    assert "embedding_model" in json_str
