# Copyright (c) 2026 Cheval-Volant LLC (d/b/a NeuralMind).
# Source-available under the NeuralMind Commercial Modules License
# (neuralmind/agent_os/LICENSE) — NOT MIT. Free 1-seat use included; see LICENSING.md.
"""tenant.py — Tenant and multi-tenant registry for the Agent OS.

A Tenant is a business that owns multiple NeuralMind projects.
TenantRegistry maps tenant_id → Tenant and provides the
resolution layer for multi-tenant request routing.

Tenants live in ~/.config/neuralmind/tenants/ as JSON files.
Each tenant file contains:
    - tenant_id: unique slug (e.g. "level2logic")
    - name: display name
    - tier: "free" | "team" | "enterprise"
    - projects: list of project paths
    - rbac: role assignments (admin/operator/viewer per email)
    - created_at, updated_at

Design notes:
    - TenantRegistry is a process-local cache. It reloads from disk
      on each access within the daemon's warm registry lifecycle.
    - Tenant IDs are URL-safe slugs (lowercase, hyphens, digits).
    - A project path can only belong to ONE tenant (hard invariant).
      Attempting to assign a project to a second tenant raises
      TenantConflictError.
    - Stdlib-only: no external dependencies, safe for hook/daemon import.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TENANTS_DIR = Path(
    os.environ.get("NEURALMIND_TENANTS_DIR", Path.home() / ".config" / "neuralmind" / "tenants")
)

_TENANT_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class TenantError(Exception):
    """Base exception for tenant operations."""


class TenantConflictError(TenantError):
    """Raised when a project is already assigned to another tenant."""


class TenantNotFoundError(TenantError):
    """Raised when a tenant_id doesn't exist."""


class InvalidTenantIdError(TenantError):
    """Raised when a tenant_id fails slug validation."""


@dataclass
class RoleAssignment:
    """Maps an email to a role within a tenant.

    Roles: "admin" (full control), "operator" (manage projects, view signals),
           "viewer" (read-only access to dashboard and signals).
    """

    email: str
    role: str  # "admin" | "operator" | "viewer"

    def to_dict(self) -> dict[str, Any]:
        return {"email": self.email, "role": self.role}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoleAssignment:
        return cls(email=data["email"].strip().lower(), role=data.get("role", "viewer"))


@dataclass
class Tenant:
    """A business unit in the Agent OS.

    Attributes:
        tenant_id: URL-safe unique slug.
        name: Display name.
        tier: License tier.
        projects: List of absolute project paths owned by this tenant.
        rbac: List of role assignments.
        governance: Per-tenant governance overrides.
        created_at: ISO timestamp.
        updated_at: ISO timestamp.
    """

    tenant_id: str
    name: str
    tier: str = "free"
    projects: list[str] = field(default_factory=list)
    rbac: list[RoleAssignment] = field(default_factory=list)
    governance: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at
        if isinstance(self.rbac, list) and self.rbac and isinstance(self.rbac[0], dict):
            self.rbac = [RoleAssignment.from_dict(r) for r in self.rbac]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "tier": self.tier,
            "projects": self.projects,
            "rbac": [r.to_dict() for r in self.rbac],
            "governance": self.governance,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Tenant:
        return cls(
            tenant_id=data["tenant_id"],
            name=data.get("name", data["tenant_id"]),
            tier=data.get("tier", "free"),
            projects=list(data.get("projects", [])),
            rbac=[RoleAssignment.from_dict(r) for r in data.get("rbac", [])],
            governance=dict(data.get("governance", {})),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def is_admin(self, email: str) -> bool:
        """True if email has admin role."""
        if not email:
            return False
        return any(r.email.lower() == email.lower() and r.role == "admin" for r in self.rbac)

    def is_operator(self, email: str) -> bool:
        """True if email has operator or admin role."""
        if not email:
            return False
        return any(
            r.email.lower() == email.lower() and r.role in ("admin", "operator") for r in self.rbac
        )

    def has_access(self, email: str) -> bool:
        """True if email has any role in this tenant."""
        if not email:
            return False
        return any(r.email.lower() == email.lower() for r in self.rbac)


def validate_tenant_id(tenant_id: str) -> str:
    """Validate a tenant_id is a URL-safe slug.

    Args:
        tenant_id: The tenant ID to validate.

    Returns:
        The validated tenant_id.

    Raises:
        InvalidTenantIdError: If the ID fails validation.
    """
    if not tenant_id or not isinstance(tenant_id, str):
        raise InvalidTenantIdError("tenant_id is required")
    if not _TENANT_ID_RE.match(tenant_id):
        raise InvalidTenantIdError(
            f"Invalid tenant_id '{tenant_id}'. Must match: lowercase, "
            "start with a letter, alphanumeric + hyphens, 1-64 chars."
        )
    return tenant_id


class TenantRegistry:
    """Multi-tenant registry backed by per-tenant JSON files.

    Thread-safe. Atomic writes via tempfile+rename.
    """

    def __init__(self, tenants_dir: Path | None = None) -> None:
        self.tenants_dir = Path(tenants_dir) if tenants_dir else DEFAULT_TENANTS_DIR
        self._lock = threading.Lock()
        self._cache: dict[str, Tenant] = {}
        self._project_index: dict[str, str] = {}  # project_path → tenant_id

    def _load_all(self) -> None:
        """Reload all tenant files from disk into the cache."""
        self._cache = {}
        self._project_index = {}
        if not self.tenants_dir.exists():
            return
        for path in self.tenants_dir.glob("*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                tenant = Tenant.from_dict(raw)
                self._cache[tenant.tenant_id] = tenant
                for proj in tenant.projects:
                    self._project_index[str(Path(proj).resolve())] = tenant.tenant_id
            except (OSError, ValueError, KeyError):
                continue

    def _save(self, tenant: Tenant) -> Path:
        """Atomic write of a tenant file."""
        self.tenants_dir.mkdir(parents=True, exist_ok=True)
        path = self.tenants_dir / f"{tenant.tenant_id}.json"
        data = json.dumps(tenant.to_dict(), indent=2, sort_keys=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=self.tenants_dir, prefix=f".{tenant.tenant_id}-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
            Path(tmp_path).replace(path)
        except OSError:
            Path(tmp_path).unlink(missing_ok=True)
            raise
        return path

    def create_tenant(
        self,
        tenant_id: str,
        name: str,
        tier: str = "free",
        admin_email: str | None = None,
        projects: list[str] | None = None,
    ) -> Tenant:
        """Create a new tenant.

        Args:
            tenant_id: URL-safe unique slug.
            name: Display name.
            tier: License tier.
            admin_email: Optional admin email for initial setup.
            projects: Optional list of project paths.

        Returns:
            The created Tenant.

        Raises:
            InvalidTenantIdError: If tenant_id fails validation.
            TenantConflictError: If the ID exists or a project is already assigned.
        """
        validate_tenant_id(tenant_id)
        with self._lock:
            self._load_all()
            if tenant_id in self._cache:
                raise TenantConflictError(f"Tenant '{tenant_id}' already exists")
            # Check project conflicts
            for proj in projects or []:
                resolved = str(Path(proj).resolve())
                if resolved in self._project_index:
                    other = self._project_index[resolved]
                    raise TenantConflictError(
                        f"Project '{proj}' already assigned to tenant '{other}'"
                    )
            rbac = []
            if admin_email:
                rbac.append(RoleAssignment(email=admin_email.strip().lower(), role="admin"))
            tenant = Tenant(
                tenant_id=tenant_id,
                name=name,
                tier=tier,
                projects=[str(Path(p).resolve()) for p in (projects or [])],
                rbac=rbac,
            )
            try:
                self._save(tenant)
            except Exception:
                self._load_all()
                raise
            self._cache[tenant_id] = tenant
            for proj in tenant.projects:
                self._project_index[proj] = tenant_id
            return tenant

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        """Get a tenant by ID. Returns None if not found."""
        with self._lock:
            self._load_all()
            return self._cache.get(tenant_id)

    def get_tenant_by_project(self, project_path: str) -> Tenant | None:
        """Get the tenant that owns a project path. Returns None if unassigned."""
        with self._lock:
            self._load_all()
            resolved = str(Path(project_path).resolve())
            tenant_id = self._project_index.get(resolved)
            return self._cache.get(tenant_id) if tenant_id else None

    def list_tenants(self) -> list[Tenant]:
        """List all tenants alphabetically by name."""
        with self._lock:
            self._load_all()
            return sorted(self._cache.values(), key=lambda t: t.name.lower())

    def add_project(self, tenant_id: str, project_path: str, admin_email: str) -> Tenant:
        """Add a project to a tenant. Admin-only."""
        with self._lock:
            self._load_all()
            tenant = self._cache.get(tenant_id)
            if not tenant:
                raise TenantNotFoundError(f"Tenant '{tenant_id}' not found")
            if not tenant.is_admin(admin_email):
                raise PermissionError(f"Not a tenant admin: {admin_email}")
            resolved = str(Path(project_path).resolve())
            if resolved in self._project_index:
                other = self._project_index[resolved]
                if other != tenant_id:
                    raise TenantConflictError(f"Project already assigned to tenant '{other}'")
            if resolved not in tenant.projects:
                tenant.projects.append(resolved)
                tenant.updated_at = datetime.now(timezone.utc).isoformat()
                try:
                    self._save(tenant)
                except Exception:
                    # Roll back cache mutation on save failure to keep
                    # in-memory state consistent with disk.
                    self._load_all()
                    raise
                self._project_index[resolved] = tenant_id
            return tenant

    def remove_project(self, tenant_id: str, project_path: str, admin_email: str) -> Tenant:
        """Remove a project from a tenant. Admin-only."""
        with self._lock:
            self._load_all()
            tenant = self._cache.get(tenant_id)
            if not tenant:
                raise TenantNotFoundError(f"Tenant '{tenant_id}' not found")
            if not tenant.is_admin(admin_email):
                raise PermissionError(f"Not a tenant admin: {admin_email}")
            resolved = str(Path(project_path).resolve())
            if resolved in tenant.projects:
                tenant.projects.remove(resolved)
                tenant.updated_at = datetime.now(timezone.utc).isoformat()
                try:
                    self._save(tenant)
                except Exception:
                    self._load_all()
                    raise
                self._project_index.pop(resolved, None)
            return tenant

    def add_role(self, tenant_id: str, email: str, role: str, admin_email: str) -> Tenant:
        """Add or update a role assignment. Admin-only."""
        with self._lock:
            self._load_all()
            tenant = self._cache.get(tenant_id)
            if not tenant:
                raise TenantNotFoundError(f"Tenant '{tenant_id}' not found")
            if not tenant.is_admin(admin_email):
                raise PermissionError(f"Not a tenant admin: {admin_email}")
            normalized = email.strip().lower()
            # Remove existing assignment for this email
            tenant.rbac = [r for r in tenant.rbac if r.email != normalized]
            tenant.rbac.append(RoleAssignment(email=normalized, role=role))
            tenant.updated_at = datetime.now(timezone.utc).isoformat()
            try:
                self._save(tenant)
            except Exception:
                self._load_all()
                raise
            return tenant

    def remove_role(self, tenant_id: str, email: str, admin_email: str) -> Tenant:
        """Remove a role assignment. Admin-only."""
        with self._lock:
            self._load_all()
            tenant = self._cache.get(tenant_id)
            if not tenant:
                raise TenantNotFoundError(f"Tenant '{tenant_id}' not found")
            if not tenant.is_admin(admin_email):
                raise PermissionError(f"Not a tenant admin: {admin_email}")
            normalized = email.strip().lower()
            tenant.rbac = [r for r in tenant.rbac if r.email != normalized]
            tenant.updated_at = datetime.now(timezone.utc).isoformat()
            self._save(tenant)
            return tenant

    def delete_tenant(self, tenant_id: str, admin_email: str) -> None:
        """Delete a tenant entirely. Admin-only. Irreversible."""
        with self._lock:
            self._load_all()
            tenant = self._cache.get(tenant_id)
            if not tenant:
                raise TenantNotFoundError(f"Tenant '{tenant_id}' not found")
            if not tenant.is_admin(admin_email):
                raise PermissionError(f"Not a tenant admin: {admin_email}")
            # Defense in depth: reject non-slug tenant_ids even if cache is poisoned
            validate_tenant_id(tenant_id)
            path = self.tenants_dir / f"{tenant_id}.json"
            try:
                path.unlink()
            except OSError:
                pass
            self._cache.pop(tenant_id, None)
            for proj in tenant.projects:
                self._project_index.pop(proj, None)


def resolve_tenant(
    project_path: str,
    tenants_dir: Path | None = None,
) -> Tenant | None:
    """Resolve the tenant for a project path.

    Convenience wrapper for daemon/MCP routing:
    resolve_tenant(mind.project_path) → owning Tenant or None.
    """
    registry = TenantRegistry(tenants_dir)
    return registry.get_tenant_by_project(project_path)
