# Copyright (c) 2026 Cheval-Volant LLC (d/b/a NeuralMind).
# Source-available under the NeuralMind Commercial Modules License
# (neuralmind/agent_os/LICENSE) — NOT MIT. Free 1-seat use included; see LICENSING.md.
"""NeuralMind Agent OS — Multi-tenant, self-improving product operations.

The Agent OS is the orchestration layer that runs NeuralMind as a
multi-business product:

1. **Tenants** are businesses (Level2Logic, CyberSentinel, DermEngine).
   Each tenant owns multiple projects with isolated data, governance,
   and RBAC.
2. **Signal detection** watches metrics streams for anomalies
   (Page-Hinkley test, no fixed thresholds) and writes signal records.
3. **Governance** enforces RBAC per-tenant: admin/operator/viewer roles,
   publishing scope, weight thresholds, audit trails.
4. **The daemon** exposes tenant-scoped HTTP endpoints for operations.

All modules are fail-open: any error degrades to pre-existing behavior
rather than blocking the core product.

Pattern follows the self-improving product operations loop (see
ai-product-ops skill): signal → diagnose → experiment → promote/rollback.

Version:
    1.14.0
"""

from __future__ import annotations

__version__ = "1.15.0"

from .api import create_agent_os_routes
from .correlator import CauseType, Insight, RootCauseCorrelator
from .experiment import ExperimentResult, ExperimentRunner, ExperimentStatus
from .governance import AgentOSGovernance, Permission, Role, require_permission
from .promotion import PromotionEngine, PromotionRecord, PromotionStatus
from .signals import SeverityLevel, Signal, SignalDetector
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
    "create_agent_os_routes",
]
