"""
Role-Based Access Control (RBAC) Service for Deployments.

This service manages role-based access control for deployment operations,
supporting fine-grained permissions per environment.

Implements MD-1813: RBAC for Deployment Access
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

try:
    from prometheus_client import Counter
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)


class DeploymentRole(Enum):
    """Predefined deployment roles."""
    VIEWER = "viewer"
    DEPLOYER = "deployer"
    ADMIN = "admin"


class DeploymentPermission(Enum):
    """Granular deployment permissions."""
    # View permissions
    VIEW_DEPLOYMENTS = "view_deployments"
    VIEW_ENVIRONMENTS = "view_environments"
    VIEW_LOGS = "view_logs"
    VIEW_HEALTH = "view_health"
    VIEW_AUDIT_TRAIL = "view_audit_trail"

    # Deployment actions
    TRIGGER_DEPLOYMENT = "trigger_deployment"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    CANCEL_DEPLOYMENT = "cancel_deployment"
    APPROVE_DEPLOYMENT = "approve_deployment"

    # Configuration
    MANAGE_ENVIRONMENTS = "manage_environments"
    MANAGE_THRESHOLDS = "manage_thresholds"
    MANAGE_APPROVALS = "manage_approvals"

    # Administration
    MANAGE_ROLES = "manage_roles"
    MANAGE_USERS = "manage_users"
    VIEW_ALL_TEAMS = "view_all_teams"


# Default permission sets for each role
ROLE_PERMISSIONS: Dict[DeploymentRole, Set[DeploymentPermission]] = {
    DeploymentRole.VIEWER: {
        DeploymentPermission.VIEW_DEPLOYMENTS,
        DeploymentPermission.VIEW_ENVIRONMENTS,
        DeploymentPermission.VIEW_HEALTH,
    },
    DeploymentRole.DEPLOYER: {
        DeploymentPermission.VIEW_DEPLOYMENTS,
        DeploymentPermission.VIEW_ENVIRONMENTS,
        DeploymentPermission.VIEW_LOGS,
        DeploymentPermission.VIEW_HEALTH,
        DeploymentPermission.VIEW_AUDIT_TRAIL,
        DeploymentPermission.TRIGGER_DEPLOYMENT,
        DeploymentPermission.ROLLBACK_DEPLOYMENT,
        DeploymentPermission.CANCEL_DEPLOYMENT,
    },
    DeploymentRole.ADMIN: {
        permission for permission in DeploymentPermission
    },
}


@dataclass
class RoleAssignment:
    """Assignment of a role to a user for specific environments."""
    assignment_id: str
    user_id: str
    role: DeploymentRole
    environments: List[str]  # Empty list means all environments
    assigned_by: str
    assigned_at: datetime
    expires_at: Optional[datetime] = None
    custom_permissions: Set[DeploymentPermission] = field(default_factory=set)
    revoked_permissions: Set[DeploymentPermission] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessCheckResult:
    """Result of an access check."""
    allowed: bool
    user_id: str
    permission: DeploymentPermission
    environment: Optional[str]
    role: Optional[DeploymentRole]
    reason: str
    checked_at: datetime


@dataclass
class RBACPolicy:
    """RBAC policy configuration."""
    enforce_environment_scope: bool = True
    default_role: Optional[DeploymentRole] = None
    allow_role_escalation: bool = False
    require_environment_for_deploy: bool = True
    max_environments_per_user: int = 10
    audit_all_checks: bool = True


class DeploymentRBACService:
    """
    Service for role-based access control on deployments.

    Features:
    - Define roles: viewer, deployer, admin
    - Permission matrix per environment
    - Role assignment and management
    - Permission enforcement in API
    """

    _instance: Optional["DeploymentRBACService"] = None

    def __new__(cls) -> "DeploymentRBACService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._assignments: Dict[str, RoleAssignment] = {}
        self._user_assignments: Dict[str, List[str]] = {}  # user_id -> assignment_ids
        self._access_log: List[AccessCheckResult] = []
        self._policy = RBACPolicy()
        self._custom_roles: Dict[str, Set[DeploymentPermission]] = {}

        # Prometheus metrics
        if PROMETHEUS_AVAILABLE:
            self._access_granted_counter = Counter(
                "rbac_access_granted_total",
                "Total number of access grants",
                ["permission", "environment", "role"]
            )
            self._access_denied_counter = Counter(
                "rbac_access_denied_total",
                "Total number of access denials",
                ["permission", "environment", "reason"]
            )

        self._initialized = True
        logger.info("DeploymentRBACService initialized")

    def configure_policy(self, policy: RBACPolicy) -> None:
        """
        Configure the RBAC policy.

        Args:
            policy: Policy configuration
        """
        self._policy = policy
        logger.info(f"RBAC policy configured: enforce_environment_scope={policy.enforce_environment_scope}")

    def get_policy(self) -> RBACPolicy:
        """Get the current RBAC policy."""
        return self._policy

    def define_custom_role(
        self,
        role_name: str,
        permissions: Set[DeploymentPermission],
    ) -> None:
        """
        Define a custom role with specific permissions.

        Args:
            role_name: Name of the custom role
            permissions: Set of permissions for this role
        """
        self._custom_roles[role_name] = permissions
        logger.info(f"Custom role '{role_name}' defined with {len(permissions)} permissions")

    def assign_role(
        self,
        user_id: str,
        role: DeploymentRole,
        environments: Optional[List[str]] = None,
        assigned_by: str = "system",
        expires_at: Optional[datetime] = None,
        custom_permissions: Optional[Set[DeploymentPermission]] = None,
        revoked_permissions: Optional[Set[DeploymentPermission]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RoleAssignment:
        """
        Assign a role to a user.

        Args:
            user_id: User to assign role to
            role: Role to assign
            environments: Specific environments (None means all)
            assigned_by: Who is making the assignment
            expires_at: Optional expiration time
            custom_permissions: Additional permissions beyond role defaults
            revoked_permissions: Permissions to remove from role defaults
            metadata: Additional metadata

        Returns:
            Created RoleAssignment
        """
        # Check max environments policy
        if environments and len(environments) > self._policy.max_environments_per_user:
            raise ValueError(
                f"Cannot assign more than {self._policy.max_environments_per_user} environments"
            )

        assignment = RoleAssignment(
            assignment_id=str(uuid4()),
            user_id=user_id,
            role=role,
            environments=environments or [],
            assigned_by=assigned_by,
            assigned_at=datetime.utcnow(),
            expires_at=expires_at,
            custom_permissions=custom_permissions or set(),
            revoked_permissions=revoked_permissions or set(),
            metadata=metadata or {},
        )

        self._assignments[assignment.assignment_id] = assignment

        if user_id not in self._user_assignments:
            self._user_assignments[user_id] = []
        self._user_assignments[user_id].append(assignment.assignment_id)

        logger.info(
            f"Role {role.value} assigned to {user_id} for environments: "
            f"{environments or 'all'}"
        )

        return assignment

    def revoke_assignment(self, assignment_id: str) -> bool:
        """
        Revoke a role assignment.

        Args:
            assignment_id: ID of the assignment to revoke

        Returns:
            True if revoked, False if not found
        """
        if assignment_id not in self._assignments:
            return False

        assignment = self._assignments[assignment_id]
        user_id = assignment.user_id

        del self._assignments[assignment_id]
        if user_id in self._user_assignments:
            self._user_assignments[user_id].remove(assignment_id)

        logger.info(f"Assignment {assignment_id} revoked for user {user_id}")
        return True

    def revoke_all_user_assignments(self, user_id: str) -> int:
        """
        Revoke all role assignments for a user.

        Args:
            user_id: User to revoke assignments for

        Returns:
            Number of assignments revoked
        """
        if user_id not in self._user_assignments:
            return 0

        assignment_ids = list(self._user_assignments[user_id])
        count = 0
        for assignment_id in assignment_ids:
            if self.revoke_assignment(assignment_id):
                count += 1

        return count

    def get_user_assignments(self, user_id: str) -> List[RoleAssignment]:
        """
        Get all role assignments for a user.

        Args:
            user_id: User to get assignments for

        Returns:
            List of role assignments
        """
        if user_id not in self._user_assignments:
            return []

        now = datetime.utcnow()
        assignments = []
        for assignment_id in self._user_assignments[user_id]:
            assignment = self._assignments.get(assignment_id)
            if assignment:
                # Check expiration
                if assignment.expires_at and assignment.expires_at < now:
                    continue
                assignments.append(assignment)

        return assignments

    def get_user_permissions(
        self,
        user_id: str,
        environment: Optional[str] = None,
    ) -> Set[DeploymentPermission]:
        """
        Get all permissions for a user, optionally scoped to an environment.

        Args:
            user_id: User to get permissions for
            environment: Optional environment to scope permissions

        Returns:
            Set of permissions
        """
        assignments = self.get_user_assignments(user_id)
        permissions: Set[DeploymentPermission] = set()

        for assignment in assignments:
            # Check environment scope
            if environment and assignment.environments:
                if environment not in assignment.environments:
                    continue

            # Get base role permissions
            role_perms = ROLE_PERMISSIONS.get(assignment.role, set())
            permissions.update(role_perms)

            # Add custom permissions
            permissions.update(assignment.custom_permissions)

            # Remove revoked permissions
            permissions -= assignment.revoked_permissions

        return permissions

    def get_user_role(
        self,
        user_id: str,
        environment: Optional[str] = None,
    ) -> Optional[DeploymentRole]:
        """
        Get the highest role for a user in an environment.

        Args:
            user_id: User to check
            environment: Optional environment to scope

        Returns:
            Highest role or None
        """
        assignments = self.get_user_assignments(user_id)
        highest_role = None
        role_hierarchy = [DeploymentRole.VIEWER, DeploymentRole.DEPLOYER, DeploymentRole.ADMIN]

        for assignment in assignments:
            # Check environment scope
            if environment and assignment.environments:
                if environment not in assignment.environments:
                    continue

            if highest_role is None:
                highest_role = assignment.role
            elif role_hierarchy.index(assignment.role) > role_hierarchy.index(highest_role):
                highest_role = assignment.role

        return highest_role

    def check_permission(
        self,
        user_id: str,
        permission: DeploymentPermission,
        environment: Optional[str] = None,
    ) -> AccessCheckResult:
        """
        Check if a user has a specific permission.

        Args:
            user_id: User to check
            permission: Permission to check
            environment: Optional environment to scope

        Returns:
            AccessCheckResult
        """
        now = datetime.utcnow()

        # Get user permissions for environment
        user_permissions = self.get_user_permissions(user_id, environment)
        user_role = self.get_user_role(user_id, environment)

        allowed = permission in user_permissions

        if allowed:
            reason = f"Permission granted via role {user_role.value if user_role else 'custom'}"
            if PROMETHEUS_AVAILABLE:
                self._access_granted_counter.labels(
                    permission=permission.value,
                    environment=environment or "all",
                    role=user_role.value if user_role else "custom"
                ).inc()
        else:
            if not user_role:
                reason = "No role assigned"
            elif environment:
                reason = f"No access to environment {environment}"
            else:
                reason = f"Permission not in role {user_role.value}"

            if PROMETHEUS_AVAILABLE:
                self._access_denied_counter.labels(
                    permission=permission.value,
                    environment=environment or "all",
                    reason=reason[:50]
                ).inc()

        result = AccessCheckResult(
            allowed=allowed,
            user_id=user_id,
            permission=permission,
            environment=environment,
            role=user_role,
            reason=reason,
            checked_at=now,
        )

        # Log access check
        if self._policy.audit_all_checks:
            self._access_log.append(result)

        logger.debug(
            f"Access check: user={user_id}, permission={permission.value}, "
            f"env={environment}, allowed={allowed}"
        )

        return result

    def check_permissions(
        self,
        user_id: str,
        permissions: List[DeploymentPermission],
        environment: Optional[str] = None,
        require_all: bool = True,
    ) -> AccessCheckResult:
        """
        Check multiple permissions at once.

        Args:
            user_id: User to check
            permissions: Permissions to check
            environment: Optional environment to scope
            require_all: If True, all permissions required; if False, any permission

        Returns:
            AccessCheckResult
        """
        results = [
            self.check_permission(user_id, perm, environment)
            for perm in permissions
        ]

        if require_all:
            allowed = all(r.allowed for r in results)
        else:
            allowed = any(r.allowed for r in results)

        denied_perms = [r.permission.value for r in results if not r.allowed]

        return AccessCheckResult(
            allowed=allowed,
            user_id=user_id,
            permission=permissions[0],  # Primary permission
            environment=environment,
            role=self.get_user_role(user_id, environment),
            reason=f"Denied: {', '.join(denied_perms)}" if denied_perms else "All granted",
            checked_at=datetime.utcnow(),
        )

    def can_deploy(self, user_id: str, environment: str) -> bool:
        """
        Check if user can trigger deployment to an environment.

        Args:
            user_id: User to check
            environment: Target environment

        Returns:
            True if user can deploy
        """
        result = self.check_permission(
            user_id,
            DeploymentPermission.TRIGGER_DEPLOYMENT,
            environment
        )
        return result.allowed

    def can_rollback(self, user_id: str, environment: str) -> bool:
        """
        Check if user can rollback deployment in an environment.

        Args:
            user_id: User to check
            environment: Target environment

        Returns:
            True if user can rollback
        """
        result = self.check_permission(
            user_id,
            DeploymentPermission.ROLLBACK_DEPLOYMENT,
            environment
        )
        return result.allowed

    def can_approve(self, user_id: str, environment: str) -> bool:
        """
        Check if user can approve deployments for an environment.

        Args:
            user_id: User to check
            environment: Target environment

        Returns:
            True if user can approve
        """
        result = self.check_permission(
            user_id,
            DeploymentPermission.APPROVE_DEPLOYMENT,
            environment
        )
        return result.allowed

    def can_manage(self, user_id: str, environment: Optional[str] = None) -> bool:
        """
        Check if user has management permissions.

        Args:
            user_id: User to check
            environment: Optional environment

        Returns:
            True if user can manage
        """
        result = self.check_permissions(
            user_id,
            [
                DeploymentPermission.MANAGE_ENVIRONMENTS,
                DeploymentPermission.MANAGE_ROLES,
            ],
            environment,
            require_all=False,
        )
        return result.allowed

    def get_accessible_environments(self, user_id: str) -> List[str]:
        """
        Get list of environments a user can access.

        Args:
            user_id: User to check

        Returns:
            List of accessible environments (empty means all)
        """
        assignments = self.get_user_assignments(user_id)
        environments: Set[str] = set()
        has_global_access = False

        for assignment in assignments:
            if not assignment.environments:
                has_global_access = True
                break
            environments.update(assignment.environments)

        if has_global_access:
            return []  # Empty means all environments

        return sorted(environments)

    def get_users_with_permission(
        self,
        permission: DeploymentPermission,
        environment: Optional[str] = None,
    ) -> List[str]:
        """
        Get all users with a specific permission.

        Args:
            permission: Permission to check
            environment: Optional environment to scope

        Returns:
            List of user IDs
        """
        users = []
        for user_id in self._user_assignments.keys():
            if permission in self.get_user_permissions(user_id, environment):
                users.append(user_id)
        return users

    def get_users_by_role(
        self,
        role: DeploymentRole,
        environment: Optional[str] = None,
    ) -> List[str]:
        """
        Get all users with a specific role.

        Args:
            role: Role to filter by
            environment: Optional environment to scope

        Returns:
            List of user IDs
        """
        users = []
        for user_id, assignment_ids in self._user_assignments.items():
            for assignment_id in assignment_ids:
                assignment = self._assignments.get(assignment_id)
                if assignment and assignment.role == role:
                    if not environment or not assignment.environments:
                        users.append(user_id)
                        break
                    elif environment in assignment.environments:
                        users.append(user_id)
                        break
        return users

    def get_permission_matrix(
        self,
        environments: List[str],
    ) -> Dict[str, Dict[str, Dict[str, bool]]]:
        """
        Get permission matrix for all users across environments.

        Args:
            environments: List of environments to include

        Returns:
            Nested dict: {user_id: {environment: {permission: bool}}}
        """
        matrix: Dict[str, Dict[str, Dict[str, bool]]] = {}

        for user_id in self._user_assignments.keys():
            matrix[user_id] = {}
            for env in environments:
                perms = self.get_user_permissions(user_id, env)
                matrix[user_id][env] = {
                    perm.value: perm in perms
                    for perm in [
                        DeploymentPermission.VIEW_DEPLOYMENTS,
                        DeploymentPermission.TRIGGER_DEPLOYMENT,
                        DeploymentPermission.ROLLBACK_DEPLOYMENT,
                        DeploymentPermission.APPROVE_DEPLOYMENT,
                        DeploymentPermission.MANAGE_ENVIRONMENTS,
                    ]
                }

        return matrix

    def get_access_log(
        self,
        user_id: Optional[str] = None,
        permission: Optional[DeploymentPermission] = None,
        allowed: Optional[bool] = None,
        limit: int = 100,
    ) -> List[AccessCheckResult]:
        """
        Get access check log with optional filters.

        Args:
            user_id: Filter by user
            permission: Filter by permission
            allowed: Filter by result
            limit: Maximum entries

        Returns:
            List of access check results
        """
        log = self._access_log

        if user_id:
            log = [e for e in log if e.user_id == user_id]

        if permission:
            log = [e for e in log if e.permission == permission]

        if allowed is not None:
            log = [e for e in log if e.allowed == allowed]

        return sorted(log, key=lambda e: e.checked_at, reverse=True)[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """Get RBAC statistics."""
        total_assignments = len(self._assignments)
        users_with_roles = len(self._user_assignments)

        by_role: Dict[str, int] = {}
        for assignment in self._assignments.values():
            role_key = assignment.role.value
            by_role[role_key] = by_role.get(role_key, 0) + 1

        access_checks = len(self._access_log)
        denied = sum(1 for e in self._access_log if not e.allowed)

        return {
            "total_assignments": total_assignments,
            "users_with_roles": users_with_roles,
            "by_role": by_role,
            "access_checks": access_checks,
            "denied_checks": denied,
            "denial_rate": denied / access_checks if access_checks > 0 else 0.0,
            "custom_roles_defined": len(self._custom_roles),
        }

    def reset(self) -> None:
        """Reset the service state (for testing)."""
        self._assignments.clear()
        self._user_assignments.clear()
        self._access_log.clear()
        self._policy = RBACPolicy()
        self._custom_roles.clear()
        logger.info("DeploymentRBACService reset")


# Singleton instance
_deployment_rbac_service: Optional[DeploymentRBACService] = None


def get_deployment_rbac_service() -> DeploymentRBACService:
    """Get the singleton DeploymentRBACService instance."""
    global _deployment_rbac_service
    if _deployment_rbac_service is None:
        _deployment_rbac_service = DeploymentRBACService()
    return _deployment_rbac_service
