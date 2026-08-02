"""governance.py — RBAC enforcement for the Agent OS.

Wraps the Tier2 governance model with Agent OS tenant roles:
- admin: full control (manage RBAC, delete tenant, manage projects)
- operator: manage projects, view signals, trigger experiments
- viewer: read-only access to dashboard and signals

Permission enforcement is decorator-based:
    @require_permission(Permission.MANAGE_RBAC)
    def add_role(...): ...

Design:
    - Permissions are granular, not role-names. Roles map to permission sets.
    - Unknown roles get viewer-only permissions (fail-closed).
    - The audit log records every permission check failure.
    - Stdlib-only: no external dependencies.
"""

from __future__ import annotations

import enum
import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar, cast

from .tenant import Tenant, TenantRegistry

log = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class Role(enum.Enum):
    """Agent OS tenant roles."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Permission(enum.Enum):
    """Agent OS permissions."""

    # Project management
    MANAGE_PROJECTS = "manage_projects"
    VIEW_PROJECTS = "view_projects"

    # RBAC management
    MANAGE_RBAC = "manage_rbac"
    VIEW_RBAC = "view_rbac"

    # Signal/operations
    VIEW_SIGNALS = "view_signals"
    MANAGE_SIGNALS = "manage_signals"

    # Experiments
    RUN_EXPERIMENTS = "run_experiments"
    VIEW_EXPERIMENTS = "view_experiments"

    # Tenant management (admin only)
    DELETE_TENANT = "delete_tenant"
    MANAGE_GOVERNANCE = "manage_governance"


# Role → permission mapping. Fail-closed: missing role = no permissions.
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: {
        Permission.MANAGE_PROJECTS,
        Permission.VIEW_PROJECTS,
        Permission.MANAGE_RBAC,
        Permission.VIEW_RBAC,
        Permission.VIEW_SIGNALS,
        Permission.MANAGE_SIGNALS,
        Permission.RUN_EXPERIMENTS,
        Permission.VIEW_EXPERIMENTS,
        Permission.DELETE_TENANT,
        Permission.MANAGE_GOVERNANCE,
    },
    Role.OPERATOR: {
        Permission.MANAGE_PROJECTS,
        Permission.VIEW_PROJECTS,
        Permission.VIEW_RBAC,
        Permission.VIEW_SIGNALS,
        Permission.MANAGE_SIGNALS,
        Permission.RUN_EXPERIMENTS,
        Permission.VIEW_EXPERIMENTS,
    },
    Role.VIEWER: {
        Permission.VIEW_PROJECTS,
        Permission.VIEW_RBAC,
        Permission.VIEW_SIGNALS,
        Permission.VIEW_EXPERIMENTS,
    },
}


class InsufficientPermissionError(PermissionError):
    """Raised when a user lacks the required permission."""


def _resolve_role_value(role_str: str) -> Role:
    """Resolve a role string to a Role enum. Fail-closed to VIEWER."""
    try:
        return Role(role_str.lower())
    except ValueError:
        log.warning(f"Unknown role '{role_str}', defaulting to viewer")
        return Role.VIEWER


def role_has_permission(role_str: str, permission: Permission) -> bool:
    """Check if a role string grants a specific permission."""
    role = _resolve_role_value(role_str)
    return permission in ROLE_PERMISSIONS.get(role, set())


def get_user_role(tenant: Tenant, email: str) -> str:
    """Get the role string for an email in a tenant. Defaults to viewer."""
    for assignment in tenant.rbac:
        if assignment.email.lower() == email.lower():
            return assignment.role
    return Role.VIEWER.value


def check_permission(tenant: Tenant, email: str, permission: Permission) -> bool:
    """Check if email has a specific permission in a tenant."""
    role_str = get_user_role(tenant, email)
    return role_has_permission(role_str, permission)


def require_permission(permission: Permission) -> Callable[[F], F]:
    """Decorator that enforces a permission on a method.

    The decorated method's first positional argument after `self`
    must be the tenant_id (str), and the second must be the email (str).

    Usage:
        @require_permission(Permission.MANAGE_RBAC)
        def add_role(self, tenant_id, email, target_email, role):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract tenant_id and email from positional args
            # Assumes: (self, tenant_id, email, ...)
            if len(args) < 3:
                raise InsufficientPermissionError(
                    f"Cannot enforce permission {permission.value}: "
                    "need at least (self, tenant_id, email)"
                )
            tenant_id = args[1]
            email = args[2]
            # Tenant must be resolved by the caller/registry
            # For now, we accept a TenantRegistry instance in self._tenant_registry
            self_obj = args[0]
            registry = getattr(self_obj, "_tenant_registry", None)
            if registry is None:
                raise InsufficientPermissionError(
                    "Cannot resolve tenant: no _tenant_registry on self"
                )
            tenant = registry.get_tenant(str(tenant_id))
            if tenant is None:
                raise InsufficientPermissionError(f"Tenant not found: {tenant_id}")
            if not check_permission(tenant, str(email), permission):
                log.warning(
                    f"Permission denied: {email} lacks {permission.value} "
                    f"in tenant {tenant_id}"
                )
                raise InsufficientPermissionError(
                    f"Insufficient permission: {permission.value} required. "
                    f"Email '{email}' has role '{get_user_role(tenant, email)}'."
                )
            return func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


@dataclass
class GovernanceResult:
    """Result of a governance check."""

    allowed: bool
    reason: str = ""
    role: str = ""
    permission: str = ""


class AgentOSGovernance:
    """Enforces RBAC and governance rules for the Agent OS.

    Wraps TenantRegistry with permission enforcement methods.
    Audit log is JSONL in ~/.config/neuralmind/agent-os-audit.jsonl.
    """

    def __init__(
        self,
        tenant_registry: TenantRegistry,
        audit_path: Path | None = None,
    ) -> None:
        self._tenant_registry = tenant_registry
        self._tenants_dir = tenant_registry.tenants_dir
        audit_dir = Path(self._tenants_dir).parent
        self._audit_path = audit_path or (audit_dir / "agent-os-audit.jsonl")
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)

    def _audit(self, actor: str, action: str, target: str, details: dict) -> None:
        """Append an entry to the audit log."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "action": action,
            "target": target,
            **details,
        }
        try:
            with self._audit_path.open("a", encoding="utf-8") as f:
                import json

                f.write(json.dumps(entry, ensure_ascii=True) + "\n")
        except OSError:
            pass  # fail-open: audit logging must never block operations

    def enforce(
        self,
        tenant_id: str,
        email: str,
        permission: Permission,
    ) -> GovernanceResult:
        """Enforce a permission check with audit logging.

        Returns a GovernanceResult with allowed=True only if the email
        has the permission in the specified tenant.
        """
        tenant = self._tenant_registry.get_tenant(tenant_id)
        if tenant is None:
            return GovernanceResult(
                allowed=False,
                reason=f"Tenant '{tenant_id}' not found",
            )
        role_str = get_user_role(tenant, email)
        if role_has_permission(role_str, permission):
            self._audit(email, "permission_granted", tenant_id, {"permission": permission.value})
            return GovernanceResult(
                allowed=True,
                reason=f"Permission {permission.value} granted",
                role=role_str,
                permission=permission.value,
            )
        self._audit(
            email,
            "permission_denied",
            tenant_id,
            {"permission": permission.value, "role": role_str},
        )
        return GovernanceResult(
            allowed=False,
            reason=(
                f"Permission '{permission.value}' denied for '{email}' "
                f"(role: {role_str}) in tenant '{tenant_id}'"
            ),
            role=role_str,
            permission=permission.value,
        )

    @require_permission(Permission.MANAGE_PROJECTS)
    def create_tenant(
        self,
        tenant_id: str,
        email: str,  # the creating user (must be admin in system context)
        name: str,
        tier: str = "free",
        projects: list[str] | None = None,
    ) -> Tenant:
        """Create a tenant with the creator as admin."""
        return self._tenant_registry.create_tenant(
            tenant_id=tenant_id,
            name=name,
            tier=tier,
            admin_email=email,
            projects=projects,
        )

    @require_permission(Permission.MANAGE_RBAC)
    def assign_role(
        self,
        tenant_id: str,
        admin_email: str,
        target_email: str,
        role: str,
    ) -> Tenant:
        """Assign a role to a user. Admin-only."""
        tenant = self._tenant_registry.add_role(tenant_id, target_email, role, admin_email)
        self._audit(admin_email, "role_assigned", tenant_id, {
            "target": target_email,
            "role": role,
        })
        return tenant

    @require_permission(Permission.MANAGE_PROJECTS)
    def add_project(
        self,
        tenant_id: str,
        email: str,
        project_path: str,
    ) -> Tenant:
        """Add a project to a tenant. Operator+."""
        tenant = self._tenant_registry.add_project(tenant_id, project_path, email)
        self._audit(email, "project_added", tenant_id, {"project": project_path})
        return tenant

    @require_permission(Permission.DELETE_TENANT)
    def delete_tenant(
        self,
        tenant_id: str,
        admin_email: str,
    ) -> None:
        """Delete a tenant. Admin-only."""
        self._tenant_registry.delete_tenant(tenant_id, admin_email)
        self._audit(admin_email, "tenant_deleted", tenant_id, {})

    def list_accessible_tenants(self, email: str) -> list[Tenant]:
        """List all tenants where the email has any role."""
        result = []
        for tenant in self._tenant_registry.list_tenants():
            if tenant.has_access(email):
                result.append(tenant)
        return result

    def can_access_project(self, email: str, project_path: str) -> bool:
        """Check if email has any access to the tenant owning a project."""
        tenant = self._tenant_registry.get_tenant_by_project(project_path)
        if tenant is None:
            return False
        return tenant.has_access(email)
