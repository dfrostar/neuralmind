"""api.py — Agent OS HTTP route handlers for the daemon.

Tenant-scoped endpoints:
    POST /api/agent-os/tenants — create tenant
    GET  /api/agent-os/tenants — list accessible tenants
    GET  /api/agent-os/tenants/{id} — get tenant details
    POST /api/agent-os/tenants/{id}/projects — add project
    DELETE /api/agent-os/tenants/{id} — delete tenant
    POST /api/agent-os/tenants/{id}/rbac — assign role
    GET  /api/agent-os/signals — list tracked metrics
    POST /api/agent-os/signals — push metric value
    POST /api/agent-os/experiments — run A/B experiment
    GET  /api/agent-os/experiments — list experiment history

Design:
    - All routes are tenant-scoped. The tenant is resolved from
      the request body (project_path or explicit tenant_id).
    - All routes require authentication (token-guarded, same as daemon).
    - Stdlib-only: matches the daemon's no-dependency approach.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .experiment import ExperimentRunner
from .governance import AgentOSGovernance
from .signals import SignalDetector
from .tenant import TenantRegistry

log = logging.getLogger(__name__)


def _json_response(status: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return status, payload


def _error(status: int, message: str) -> tuple[int, dict[str, Any]]:
    return status, {"error": message}


# Type alias: (body, path_remainder) → (status, payload)
ScopedHandler = Callable[[dict[str, Any], str], tuple[int, dict[str, Any]]]
DirectHandler = Callable[[dict[str, Any]], tuple[int, dict[str, Any]]]


def create_agent_os_routes(
    tenant_registry: TenantRegistry,
    signal_detector: SignalDetector,
    experiment_runner: ExperimentRunner,
    audit_path: Path | None = None,
) -> dict[tuple[str, str], Callable]:
    """Create Agent OS route handlers.

    Returns a dict of {(method, path): handler} for the daemon's dispatch.
    The daemon calls handler(body, path_parameters_dict).

    For routes with path parameters (e.g., /tenants/{id}), the daemon
    provides them in path_parameters.

    Args:
        tenant_registry: The tenant registry to use.
        signal_detector: The signal detector to use.
        experiment_runner: The experiment runner to use.
        audit_path: Optional audit log path.

    Returns:
        A dict of route handlers keyed by (HTTP method, path).
        Path parameters use {name} syntax (e.g., "/tenants/{tenant_id}").
    """
    governance = AgentOSGovernance(tenant_registry, audit_path)

    # ---- Tenant CRUD ----

    def create_tenant(
        body: dict[str, Any], **path_params: str
    ) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/tenants — Create a tenant."""
        try:
            tenant_id = (body.get("tenant_id") or "").strip()
            name = body.get("name", tenant_id)
            tier = body.get("tier", "free")
            admin_email = (body.get("admin_email") or "").strip()
            projects = body.get("projects", [])
            if not admin_email:
                return _error(400, "admin_email is required")
            if not tenant_id:
                return _error(400, "tenant_id is required")
            tenant = governance.create_tenant(tenant_id, admin_email, name, tier, projects)
            return _json_response(201, tenant.to_dict())
        except PermissionError as e:
            return _error(403, str(e))
        except Exception as e:
            log.exception("Failed to create tenant")
            return _error(500, str(e))

    def list_tenants(
        body: dict[str, Any] | None = None, **path_params: str
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/tenants — List accessible tenants."""
        try:
            if body is None:
                body = {}
            email = (body.get("email") or "").strip()
            if not email:
                return _error(400, "email is required")
            tenants = governance.list_accessible_tenants(email)
            return _json_response(200, {
                "tenants": [t.to_dict() for t in tenants],
                "count": len(tenants),
            })
        except Exception as e:
            log.exception("Failed to list tenants")
            return _error(500, str(e))

    def get_tenant(
        body: dict[str, Any] | None = None, **path_params: str
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/tenants/{tenant_id} — Get tenant details."""
        try:
            tenant_id = path_params.get("tenant_id", "")
            if not tenant_id:
                return _error(400, "tenant_id is required in path")
            if body is None:
                body = {}
            email = (body.get("email") or "").strip()
            if not email:
                return _error(400, "email is required")
            tenant = tenant_registry.get_tenant(tenant_id)
            if not tenant:
                return _error(404, f"Tenant '{tenant_id}' not found")
            if not tenant.has_access(email):
                return _error(403, "Access denied")
            return _json_response(200, tenant.to_dict())
        except Exception as e:
            log.exception("Failed to get tenant")
            return _error(500, str(e))

    def add_project_to_tenant(
        body: dict[str, Any], **path_params: str
    ) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/tenants/{tenant_id}/projects — Add a project."""
        try:
            tenant_id = path_params.get("tenant_id", "")
            email = (body.get("email") or "").strip()
            project_path = (body.get("project_path") or "").strip()
            if not email:
                return _error(400, "email is required")
            if not project_path:
                return _error(400, "project_path is required")
            tenant = governance.add_project(tenant_id, email, project_path)
            return _json_response(200, tenant.to_dict())
        except PermissionError as e:
            return _error(403, str(e))
        except Exception as e:
            log.exception("Failed to add project")
            return _error(500, str(e))

    def delete_tenant_endpoint(
        body: dict[str, Any] | None = None, **path_params: str
    ) -> tuple[int, dict[str, Any]]:
        """DELETE /api/agent-os/tenants/{tenant_id} — Delete a tenant."""
        try:
            tenant_id = path_params.get("tenant_id", "")
            if body is None:
                body = {}
            email = (body.get("email") or "").strip()
            if not email:
                return _error(400, "email is required")
            governance.delete_tenant(tenant_id, email)
            return _json_response(200, {"deleted": tenant_id})
        except PermissionError as e:
            return _error(403, str(e))
        except Exception as e:
            log.exception("Failed to delete tenant")
            return _error(500, str(e))

    def assign_role(
        body: dict[str, Any], **path_params: str
    ) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/tenants/{tenant_id}/rbac — Assign a role."""
        try:
            tenant_id = path_params.get("tenant_id", "")
            email = (body.get("email") or "").strip()
            target_email = (body.get("target_email") or "").strip()
            role = (body.get("role") or "viewer").strip()
            if not email:
                return _error(400, "email is required")
            if not target_email:
                return _error(400, "target_email is required")
            tenant = governance.assign_role(tenant_id, email, target_email, role)
            return _json_response(200, tenant.to_dict())
        except PermissionError as e:
            return _error(403, str(e))
        except Exception as e:
            log.exception("Failed to assign role")
            return _error(500, str(e))

    # ---- Signal routes ----

    def get_signals(
        body: dict[str, Any] | None = None, **path_params: str
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/signals — List tracked metrics."""
        try:
            metrics = signal_detector.list_metrics()
            stats = {}
            for m in metrics:
                s = signal_detector.get_stats(m)
                if s:
                    stats[m] = s
            return _json_response(200, {
                "metrics": stats,
                "tracked_count": len(metrics),
            })
        except Exception as e:
            log.exception("Failed to get signals")
            return _error(500, str(e))

    def update_signal(
        body: dict[str, Any], **path_params: str
    ) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/signals — Push a metric value."""
        try:
            metric_name = (body.get("metric_name") or "").strip()
            value = body.get("value")
            if not metric_name:
                return _error(400, "metric_name is required")
            if value is None:
                return _error(400, "value is required")
            signal = signal_detector.update(metric_name, float(value))
            return _json_response(200, {
                "signal": signal.to_dict() if signal else None,
                "metric": metric_name,
                "value": float(value),
            })
        except Exception as e:
            log.exception("Failed to update signal")
            return _error(500, str(e))

    # ---- Experiment routes ----

    def run_experiment(
        body: dict[str, Any], **path_params: str
    ) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/experiments — Run an A/B experiment."""
        try:
            email = (body.get("email") or "").strip()
            if not email:
                return _error(400, "email is required")
            proposal_id = (body.get("proposal_id") or "").strip()
            metric_name = (body.get("metric_name") or "").strip()
            baseline_value = body.get("baseline_value")
            candidate_value = body.get("candidate_value")
            threshold_pct = body.get("threshold_pct")
            if not proposal_id:
                return _error(400, "proposal_id is required")
            if not metric_name:
                return _error(400, "metric_name is required")
            if baseline_value is None or candidate_value is None:
                return _error(400, "baseline_value and candidate_value are required")
            result = experiment_runner.run(
                proposal_id=proposal_id,
                metric_name=metric_name,
                baseline_value=float(baseline_value),
                candidate_value=float(candidate_value),
                threshold_pct=float(threshold_pct) if threshold_pct else None,
                details={"triggered_by": email},
            )
            return _json_response(200, result.to_dict())
        except PermissionError as e:
            return _error(403, str(e))
        except Exception as e:
            log.exception("Failed to run experiment")
            return _error(500, str(e))

    def list_experiments(
        body: dict[str, Any] | None = None, **path_params: str
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/experiments — List experiment history."""
        try:
            history = experiment_runner.get_history()
            return _json_response(200, {
                "experiments": [e.to_dict() for e in history],
                "count": len(history),
            })
        except Exception as e:
            log.exception("Failed to list experiments")
            return _error(500, str(e))

    # ---- Route table ----
    # Format: (method, path) → handler
    # Path uses {param} syntax for daemon path extraction
    routes: dict[tuple[str, str], Callable] = {
        ("POST", "/api/agent-os/tenants"): create_tenant,
        ("GET", "/api/agent-os/tenants"): list_tenants,
        ("GET", "/api/agent-os/tenants/{tenant_id}"): get_tenant,
        ("POST", "/api/agent-os/tenants/{tenant_id}/projects"): add_project_to_tenant,
        ("DELETE", "/api/agent-os/tenants/{tenant_id}"): delete_tenant_endpoint,
        ("POST", "/api/agent-os/tenants/{tenant_id}/rbac"): assign_role,
        ("GET", "/api/agent-os/signals"): get_signals,
        ("POST", "/api/agent-os/signals"): update_signal,
        ("POST", "/api/agent-os/experiments"): run_experiment,
        ("GET", "/api/agent-os/experiments"): list_experiments,
    }

    return routes
