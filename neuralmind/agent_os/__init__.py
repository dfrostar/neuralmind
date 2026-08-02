"""NeuralMind Agent OS — Multi-tenant, self-improving product operations."""
from __future__ import annotations

__version__ = "1.16.0"

from .adversarial import (
    generate_adversarial_query,
    get_adversarial_queries,
)
from .api import create_agent_os_routes
from .auth import AuthContext, SessionStore, extract_bearer_token
from .auto_trigger import AutoTriggerLoop
from .correlator import CauseType, Insight, RootCauseCorrelator
from .experiment import ExperimentResult, ExperimentRunner, ExperimentStatus
from .governance import AgentOSGovernance, Permission, Role, require_permission
from .promotion import (
    MIN_SIGNALS_BEFORE_AUTO_PROMOTE,
    PromotionEngine,
    PromotionRecord,
    PromotionStatus,
    Proposal,
    ShipCallable,
    TunerIncumbent,
)
from .proposal_store import (
    create_proposal,
    increment_signal_count,
    list_proposals,
    update_proposal,
)
from .proposal_store import (
    get_proposal as get_proposal_by_id,
)
from .proposal_store import (
    history as proposal_history,
)
from .signals import SeverityLevel, Signal, SignalDetector
from .signals_log import (
    get_insights,
    get_signals,
    log_insight,
    log_signal,
)
from .store import AgentOSStore, get_store, reset_store
from .tenant import (
    Tenant,
    TenantConflictError,
    TenantNotFoundError,
    TenantRegistry,
    resolve_tenant,
    validate_tenant_id,
)

__all__ = [
    "Tenant",
    "TenantRegistry",
    "TenantConflictError",
    "TenantNotFoundError",
    "resolve_tenant",
    "validate_tenant_id",
    "AgentOSGovernance",
    "Role",
    "Permission",
    "require_permission",
    "SignalDetector",
    "Signal",
    "SeverityLevel",
    "ExperimentRunner",
    "ExperimentResult",
    "ExperimentStatus",
    "RootCauseCorrelator",
    "CauseType",
    "Insight",
    "PromotionEngine",
    "PromotionRecord",
    "PromotionStatus",
    "Proposal",
    "TunerIncumbent",
    "ShipCallable",
    "MIN_SIGNALS_BEFORE_AUTO_PROMOTE",
    "create_agent_os_routes",
    "log_signal",
    "log_insight",
    "get_signals",
    "get_insights",
    "AutoTriggerLoop",
    "AgentOSStore",
    "get_store",
    "reset_store",
    "create_proposal",
    "list_proposals",
    "get_proposal_by_id",
    "update_proposal",
    "increment_signal_count",
    "proposal_history",
    "AuthContext",
    "SessionStore",
    "extract_bearer_token",
]
