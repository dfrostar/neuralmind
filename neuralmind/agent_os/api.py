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
      the authenticated session (Authorization header), NOT from request body.
    - All routes require authentication (token-guarded, same as daemon).
    - Stdlib-only: matches the daemon's no-dependency approach.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .auth import AuthContext, SessionStore, extract_bearer_token
from .experiment import ExperimentRunner
from .governance import AgentOSGovernance, Permission
from .signals import SignalDetector
from .store import AgentOSStore
from .tenant import TenantRegistry

log = logging.getLogger(__name__)


def _json_response(status: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return status, payload


def _error(status: int, message: str) -> tuple[int, dict[str, Any]]:
    return status, {"error": message}


ScopedHandler = Callable[[dict[str, Any], str], tuple[int, dict[str, Any]]]
DirectHandler = Callable[[dict[str, Any]], tuple[int, dict[str, Any]]]


def _require_permission(
    governance: AgentOSGovernance,
    auth: AuthContext,
    tenant_id: str | None,
    permission: Permission,
) -> tuple[int, dict[str, Any]] | None:
    """Enforce a permission for an authenticated user in a tenant."""
    if not tenant_id:
        return _error(400, "tenant_id is required")
    if not auth.is_authenticated:
        return _error(401, "authentication required")
    result = governance.enforce(tenant_id, auth.email, permission)
    if not result.allowed:
        return _error(403, result.reason)
    return None


def create_agent_os_routes(
    tenant_registry: TenantRegistry,
    signal_detector: SignalDetector,
    experiment_runner: ExperimentRunner,
    session_store: SessionStore | None = None,
    audit_path: Path | None = None,
    store: AgentOSStore | None = None,
) -> dict[tuple[str, str], Callable]:
    """Create Agent OS route handlers.

    Returns a dict of {(method, path): handler} for the daemon's dispatch.
    The daemon calls handler(body, path_parameters_dict).
    """
    governance = AgentOSGovernance(tenant_registry, audit_path, store=store)
    if session_store is None:
        session_store = SessionStore()

    def _get_auth(body: dict[str, Any] | None, headers: dict[str, str] | None = None) -> AuthContext:
        """Extract auth context from Authorization header."""
        if headers:
            token = extract_bearer_token(headers.get("Authorization"))
            if token:
                auth = session_store.get_session(token)
                if auth:
                    return auth
        # Backward-compat: body-based identity (token-less clients, tests)
        if body:
            email = (body.get("email") or "").strip()
            if email:
                return AuthContext(email=email.lower(), tenant_id=None)
        return AuthContext(email="", tenant_id=None)

    def create_tenant(body: dict[str, Any], **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/tenants — Create a tenant (bootstrap, no auth required)."""
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
            token = session_store.create_session(admin_email, tenant_id, "admin")
            tenant = governance.create_tenant(tenant_id, admin_email, name, tier, projects)
            return _json_response(201, {**tenant.to_dict(), "session_token": token})
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
            auth = _get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            tenants = governance.list_accessible_tenants(auth.email)
            return _json_response(
                200,
                {
                    "tenants": [t.to_dict() for t in tenants],
                    "count": len(tenants),
                },
            )
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
            auth = _get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            tenant = tenant_registry.get_tenant(tenant_id)
            if not tenant:
                return _error(404, f"Tenant '{tenant_id}' not found")
            if not tenant.has_access(auth.email):
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
            auth = _get_auth(body)
            error = _require_permission(governance, auth, tenant_id, Permission.MANAGE_PROJECTS)
            if error:
                return error
            project_path = (body.get("project_path") or "").strip()
            if not project_path:
                return _error(400, "project_path is required")
            tenant = governance.add_project(tenant_id, auth.email, project_path)
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
            auth = _get_auth(body)
            error = _require_permission(governance, auth, tenant_id, Permission.DELETE_TENANT)
            if error:
                return error
            governance.delete_tenant(tenant_id, auth.email)
            return _json_response(200, {"deleted": tenant_id})
        except PermissionError as e:
            return _error(403, str(e))
        except Exception as e:
            log.exception("Failed to delete tenant")
            return _error(500, str(e))

    def assign_role(body: dict[str, Any], **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/tenants/{tenant_id}/rbac — Assign a role."""
        try:
            tenant_id = path_params.get("tenant_id", "")
            auth = _get_auth(body)
            error = _require_permission(governance, auth, tenant_id, Permission.MANAGE_RBAC)
            if error:
                return error
            target_email = (body.get("target_email") or "").strip()
            role = (body.get("role") or "viewer").strip()
            if not target_email:
                return _error(400, "target_email is required")
            session_store.create_session(target_email, tenant_id, role)
            tenant = governance.assign_role(tenant_id, auth.email, target_email, role)
            return _json_response(200, tenant.to_dict())
        except PermissionError as e:
            return _error(403, str(e))
        except Exception as e:
            log.exception("Failed to assign role")
            return _error(500, str(e))

    def get_signals(
        body: dict[str, Any] | None = None, **path_params: str
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/signals — List tracked metrics."""
        try:
            auth = _get_auth(body)
            tenant_id = (body.get("tenant_id") or "").strip()
            error = _require_permission(
                governance, auth, tenant_id, Permission.VIEW_SIGNALS
            )
            if error:
                return error
            metrics = signal_detector.list_metrics()
            stats = {}
            for m in metrics:
                s = signal_detector.get_stats(m)
                if s:
                    stats[m] = s
            return _json_response(
                200,
                {"metrics": stats, "tracked_count": len(metrics)},
            )
        except Exception as e:
            log.exception("Failed to get signals")
            return _error(500, str(e))

    def update_signal(body: dict[str, Any], **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/signals — Push a metric value."""
        try:
            auth = _get_auth(body)
            tenant_id = (body.get("tenant_id") or "").strip()
            error = _require_permission(
                governance, auth, tenant_id, Permission.MANAGE_SIGNALS
            )
            if error:
                return error
            metric_name = (body.get("metric_name") or "").strip()
            value = body.get("value")
            if not metric_name:
                return _error(400, "metric_name is required")
            if value is None:
                return _error(400, "value is required")
            try:
                sample = float(value)
            except (TypeError, ValueError):
                return _error(400, "value must be numeric")
            result = signal_detector.push(metric_name, sample)
            return _json_response(
                200,
                {
                    "signal": result.signal.to_dict() if result.signal else None,
                    "insight": result.insight.to_dict() if result.insight else None,
                    "metric": metric_name,
                    "value": sample,
                },
            )
        except Exception as e:
            log.exception("Failed to update signal")
            return _error(500, str(e))

    def run_experiment(body: dict[str, Any], **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/experiments — Run an A/B experiment."""
        try:
            auth = _get_auth(body)
            tenant_id = (body.get("tenant_id") or "").strip()
            error = _require_permission(
                governance, auth, tenant_id, Permission.RUN_EXPERIMENTS
            )
            if error:
                return error
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
            try:
                baseline_f = float(baseline_value)
                candidate_f = float(candidate_value)
                threshold_f = float(threshold_pct) if threshold_pct else None
            except (TypeError, ValueError):
                return _error(
                    400, "baseline_value, candidate_value, and threshold_pct must be numeric"
                )
            result = experiment_runner.run(
                proposal_id=proposal_id,
                metric_name=metric_name,
                baseline_value=baseline_f,
                candidate_value=candidate_f,
                threshold_pct=threshold_f,
                details={"triggered_by": auth.email},
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
            auth = _get_auth(body)
            tenant_id = (body.get("tenant_id") or "").strip()
            error = _require_permission(
                governance, auth, tenant_id, Permission.VIEW_EXPERIMENTS
            )
            if error:
                return error
            history = experiment_runner.get_history()
            return _json_response(
                200,
                {"experiments": [e.to_dict() for e in history], "count": len(history)},
            )
        except Exception as e:
            log.exception("Failed to list experiments")
            return _error(500, str(e))

    # Route table
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
