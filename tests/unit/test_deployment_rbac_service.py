"""
Unit tests for DeploymentRBACService.

Tests cover:
- Role assignment and revocation
- Permission checking
- Environment scoping
- Permission matrix
- Access logging
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock
import pytest

from src.services.deployment_rbac_service import (
    AccessCheckResult,
    DeploymentPermission,
    DeploymentRBACService,
    DeploymentRole,
    RBACPolicy,
    RoleAssignment,
    ROLE_PERMISSIONS,
    get_deployment_rbac_service,
)


@pytest.fixture
def service():
    """Create a fresh DeploymentRBACService instance for testing."""
    svc = DeploymentRBACService()
    svc.reset()
    return svc


@pytest.fixture
def sample_assignment(service):
    """Create a sample role assignment."""
    return service.assign_role(
        user_id="user-001",
        role=DeploymentRole.DEPLOYER,
        environments=["staging", "production"],
        assigned_by="admin",
    )


class TestRolePermissions:
    """Tests for predefined role permissions."""

    def test_viewer_permissions(self):
        """Test viewer role has limited permissions."""
        perms = ROLE_PERMISSIONS[DeploymentRole.VIEWER]
        assert DeploymentPermission.VIEW_DEPLOYMENTS in perms
        assert DeploymentPermission.VIEW_ENVIRONMENTS in perms
        assert DeploymentPermission.VIEW_HEALTH in perms
        assert DeploymentPermission.TRIGGER_DEPLOYMENT not in perms
        assert DeploymentPermission.MANAGE_ROLES not in perms

    def test_deployer_permissions(self):
        """Test deployer role has deploy permissions."""
        perms = ROLE_PERMISSIONS[DeploymentRole.DEPLOYER]
        assert DeploymentPermission.VIEW_DEPLOYMENTS in perms
        assert DeploymentPermission.TRIGGER_DEPLOYMENT in perms
        assert DeploymentPermission.ROLLBACK_DEPLOYMENT in perms
        assert DeploymentPermission.CANCEL_DEPLOYMENT in perms
        assert DeploymentPermission.MANAGE_ROLES not in perms

    def test_admin_permissions(self):
        """Test admin role has all permissions."""
        perms = ROLE_PERMISSIONS[DeploymentRole.ADMIN]
        assert len(perms) == len(DeploymentPermission)
        for perm in DeploymentPermission:
            assert perm in perms


class TestRoleAssignment:
    """Tests for role assignment."""

    def test_assign_role_success(self, service):
        """Test basic role assignment."""
        assignment = service.assign_role(
            user_id="user-001",
            role=DeploymentRole.DEPLOYER,
            environments=["staging"],
            assigned_by="admin",
        )

        assert isinstance(assignment, RoleAssignment)
        assert assignment.user_id == "user-001"
        assert assignment.role == DeploymentRole.DEPLOYER
        assert assignment.environments == ["staging"]
        assert assignment.assigned_by == "admin"

    def test_assign_role_all_environments(self, service):
        """Test role assignment for all environments."""
        assignment = service.assign_role(
            user_id="user-001",
            role=DeploymentRole.ADMIN,
            assigned_by="admin",
        )

        assert assignment.environments == []  # Empty means all

    def test_assign_role_with_expiration(self, service):
        """Test role assignment with expiration."""
        expires = datetime.utcnow() + timedelta(days=30)
        assignment = service.assign_role(
            user_id="user-001",
            role=DeploymentRole.DEPLOYER,
            assigned_by="admin",
            expires_at=expires,
        )

        assert assignment.expires_at == expires

    def test_assign_role_with_custom_permissions(self, service):
        """Test role assignment with custom permissions."""
        custom_perms = {DeploymentPermission.VIEW_AUDIT_TRAIL}
        assignment = service.assign_role(
            user_id="user-001",
            role=DeploymentRole.VIEWER,
            assigned_by="admin",
            custom_permissions=custom_perms,
        )

        assert assignment.custom_permissions == custom_perms

    def test_assign_role_with_revoked_permissions(self, service):
        """Test role assignment with revoked permissions."""
        revoked = {DeploymentPermission.ROLLBACK_DEPLOYMENT}
        assignment = service.assign_role(
            user_id="user-001",
            role=DeploymentRole.DEPLOYER,
            assigned_by="admin",
            revoked_permissions=revoked,
        )

        assert assignment.revoked_permissions == revoked

    def test_assign_too_many_environments_fails(self, service):
        """Test assigning too many environments fails."""
        policy = RBACPolicy(max_environments_per_user=2)
        service.configure_policy(policy)

        with pytest.raises(ValueError, match="Cannot assign more than"):
            service.assign_role(
                user_id="user-001",
                role=DeploymentRole.DEPLOYER,
                environments=["env1", "env2", "env3"],
                assigned_by="admin",
            )


class TestRoleRevocation:
    """Tests for role revocation."""

    def test_revoke_assignment(self, service, sample_assignment):
        """Test revoking a role assignment."""
        result = service.revoke_assignment(sample_assignment.assignment_id)
        assert result is True

        assignments = service.get_user_assignments("user-001")
        assert len(assignments) == 0

    def test_revoke_assignment_not_found(self, service):
        """Test revoking non-existent assignment."""
        result = service.revoke_assignment("nonexistent")
        assert result is False

    def test_revoke_all_user_assignments(self, service):
        """Test revoking all assignments for a user."""
        service.assign_role("user-001", DeploymentRole.VIEWER, assigned_by="admin")
        service.assign_role("user-001", DeploymentRole.DEPLOYER, environments=["staging"], assigned_by="admin")

        count = service.revoke_all_user_assignments("user-001")
        assert count == 2

        assignments = service.get_user_assignments("user-001")
        assert len(assignments) == 0


class TestPermissionChecking:
    """Tests for permission checking."""

    def test_check_permission_allowed(self, service, sample_assignment):
        """Test permission check that is allowed."""
        result = service.check_permission(
            user_id="user-001",
            permission=DeploymentPermission.TRIGGER_DEPLOYMENT,
            environment="staging",
        )

        assert result.allowed is True
        assert result.user_id == "user-001"
        assert result.permission == DeploymentPermission.TRIGGER_DEPLOYMENT

    def test_check_permission_denied_no_role(self, service):
        """Test permission check denied when no role."""
        result = service.check_permission(
            user_id="user-001",
            permission=DeploymentPermission.TRIGGER_DEPLOYMENT,
        )

        assert result.allowed is False
        assert "No role assigned" in result.reason

    def test_check_permission_denied_wrong_environment(self, service, sample_assignment):
        """Test permission denied for wrong environment."""
        result = service.check_permission(
            user_id="user-001",
            permission=DeploymentPermission.TRIGGER_DEPLOYMENT,
            environment="development",  # Not in assigned environments
        )

        assert result.allowed is False

    def test_check_permission_denied_insufficient_role(self, service):
        """Test permission denied when role lacks permission."""
        service.assign_role(
            user_id="user-001",
            role=DeploymentRole.VIEWER,
            assigned_by="admin",
        )

        result = service.check_permission(
            user_id="user-001",
            permission=DeploymentPermission.TRIGGER_DEPLOYMENT,
        )

        assert result.allowed is False
        assert "not in role viewer" in result.reason

    def test_check_permission_with_custom_permissions(self, service):
        """Test permission check with custom permissions."""
        service.assign_role(
            user_id="user-001",
            role=DeploymentRole.VIEWER,
            custom_permissions={DeploymentPermission.VIEW_AUDIT_TRAIL},
            assigned_by="admin",
        )

        result = service.check_permission(
            user_id="user-001",
            permission=DeploymentPermission.VIEW_AUDIT_TRAIL,
        )

        assert result.allowed is True

    def test_check_permission_with_revoked_permissions(self, service):
        """Test permission check with revoked permissions."""
        service.assign_role(
            user_id="user-001",
            role=DeploymentRole.DEPLOYER,
            revoked_permissions={DeploymentPermission.ROLLBACK_DEPLOYMENT},
            assigned_by="admin",
        )

        result = service.check_permission(
            user_id="user-001",
            permission=DeploymentPermission.ROLLBACK_DEPLOYMENT,
        )

        assert result.allowed is False

    def test_check_expired_assignment(self, service):
        """Test permission check with expired assignment."""
        expired = datetime.utcnow() - timedelta(hours=1)
        service.assign_role(
            user_id="user-001",
            role=DeploymentRole.DEPLOYER,
            assigned_by="admin",
            expires_at=expired,
        )

        result = service.check_permission(
            user_id="user-001",
            permission=DeploymentPermission.TRIGGER_DEPLOYMENT,
        )

        assert result.allowed is False


class TestMultiplePermissionCheck:
    """Tests for checking multiple permissions."""

    def test_check_permissions_all_required(self, service):
        """Test checking multiple permissions - all required."""
        service.assign_role(
            user_id="user-001",
            role=DeploymentRole.DEPLOYER,
            assigned_by="admin",
        )

        result = service.check_permissions(
            user_id="user-001",
            permissions=[
                DeploymentPermission.VIEW_DEPLOYMENTS,
                DeploymentPermission.TRIGGER_DEPLOYMENT,
            ],
            require_all=True,
        )

        assert result.allowed is True

    def test_check_permissions_any_required(self, service):
        """Test checking multiple permissions - any required."""
        service.assign_role(
            user_id="user-001",
            role=DeploymentRole.VIEWER,
            assigned_by="admin",
        )

        result = service.check_permissions(
            user_id="user-001",
            permissions=[
                DeploymentPermission.VIEW_DEPLOYMENTS,
                DeploymentPermission.TRIGGER_DEPLOYMENT,  # Viewer doesn't have this
            ],
            require_all=False,
        )

        assert result.allowed is True  # Has at least VIEW_DEPLOYMENTS


class TestConvenienceMethods:
    """Tests for convenience permission check methods."""

    def test_can_deploy(self, service, sample_assignment):
        """Test can_deploy convenience method."""
        assert service.can_deploy("user-001", "staging") is True
        assert service.can_deploy("user-001", "development") is False  # Not assigned

    def test_can_rollback(self, service, sample_assignment):
        """Test can_rollback convenience method."""
        assert service.can_rollback("user-001", "staging") is True

    def test_can_approve(self, service, sample_assignment):
        """Test can_approve convenience method."""
        # Deployer doesn't have approve permission
        assert service.can_approve("user-001", "staging") is False

        # Admin does
        service.assign_role("user-002", DeploymentRole.ADMIN, assigned_by="admin")
        assert service.can_approve("user-002", "staging") is True

    def test_can_manage(self, service):
        """Test can_manage convenience method."""
        service.assign_role("user-001", DeploymentRole.DEPLOYER, assigned_by="admin")
        assert service.can_manage("user-001") is False

        service.assign_role("user-002", DeploymentRole.ADMIN, assigned_by="admin")
        assert service.can_manage("user-002") is True


class TestEnvironmentAccess:
    """Tests for environment access."""

    def test_get_accessible_environments(self, service, sample_assignment):
        """Test getting accessible environments."""
        envs = service.get_accessible_environments("user-001")
        assert "staging" in envs
        assert "production" in envs

    def test_get_accessible_environments_all(self, service):
        """Test getting all environments for admin."""
        service.assign_role("user-001", DeploymentRole.ADMIN, assigned_by="admin")
        envs = service.get_accessible_environments("user-001")
        assert envs == []  # Empty means all environments


class TestUserQueries:
    """Tests for user queries."""

    def test_get_user_assignments(self, service, sample_assignment):
        """Test getting user assignments."""
        assignments = service.get_user_assignments("user-001")
        assert len(assignments) == 1
        assert assignments[0] == sample_assignment

    def test_get_user_permissions(self, service, sample_assignment):
        """Test getting user permissions."""
        perms = service.get_user_permissions("user-001", "staging")
        assert DeploymentPermission.TRIGGER_DEPLOYMENT in perms
        assert DeploymentPermission.VIEW_DEPLOYMENTS in perms

    def test_get_user_role(self, service, sample_assignment):
        """Test getting user role."""
        role = service.get_user_role("user-001", "staging")
        assert role == DeploymentRole.DEPLOYER

    def test_get_user_role_highest(self, service):
        """Test getting highest role when multiple assigned."""
        service.assign_role("user-001", DeploymentRole.VIEWER, assigned_by="admin")
        service.assign_role("user-001", DeploymentRole.ADMIN, assigned_by="admin")

        role = service.get_user_role("user-001")
        assert role == DeploymentRole.ADMIN

    def test_get_users_with_permission(self, service):
        """Test getting users with permission."""
        service.assign_role("user-001", DeploymentRole.DEPLOYER, assigned_by="admin")
        service.assign_role("user-002", DeploymentRole.VIEWER, assigned_by="admin")

        users = service.get_users_with_permission(DeploymentPermission.TRIGGER_DEPLOYMENT)
        assert "user-001" in users
        assert "user-002" not in users

    def test_get_users_by_role(self, service):
        """Test getting users by role."""
        service.assign_role("user-001", DeploymentRole.DEPLOYER, assigned_by="admin")
        service.assign_role("user-002", DeploymentRole.DEPLOYER, assigned_by="admin")
        service.assign_role("user-003", DeploymentRole.VIEWER, assigned_by="admin")

        deployers = service.get_users_by_role(DeploymentRole.DEPLOYER)
        assert "user-001" in deployers
        assert "user-002" in deployers
        assert "user-003" not in deployers


class TestPermissionMatrix:
    """Tests for permission matrix."""

    def test_get_permission_matrix(self, service):
        """Test getting permission matrix."""
        service.assign_role(
            "user-001",
            DeploymentRole.DEPLOYER,
            environments=["staging"],
            assigned_by="admin"
        )
        service.assign_role(
            "user-002",
            DeploymentRole.ADMIN,
            assigned_by="admin"
        )

        matrix = service.get_permission_matrix(["staging", "production"])

        assert "user-001" in matrix
        assert "user-002" in matrix

        # User-001 can deploy to staging but not production
        assert matrix["user-001"]["staging"]["trigger_deployment"] is True
        assert matrix["user-001"]["production"]["trigger_deployment"] is False

        # User-002 (admin) can deploy to both
        assert matrix["user-002"]["staging"]["trigger_deployment"] is True
        assert matrix["user-002"]["production"]["trigger_deployment"] is True


class TestAccessLog:
    """Tests for access logging."""

    def test_access_log_created(self, service, sample_assignment):
        """Test that access checks are logged."""
        service.check_permission("user-001", DeploymentPermission.VIEW_DEPLOYMENTS)

        log = service.get_access_log()
        assert len(log) == 1
        assert log[0].user_id == "user-001"

    def test_access_log_filter_by_user(self, service):
        """Test filtering access log by user."""
        service.assign_role("user-001", DeploymentRole.DEPLOYER, assigned_by="admin")
        service.assign_role("user-002", DeploymentRole.VIEWER, assigned_by="admin")

        service.check_permission("user-001", DeploymentPermission.VIEW_DEPLOYMENTS)
        service.check_permission("user-002", DeploymentPermission.VIEW_DEPLOYMENTS)

        log = service.get_access_log(user_id="user-001")
        assert len(log) == 1
        assert log[0].user_id == "user-001"

    def test_access_log_filter_by_allowed(self, service):
        """Test filtering access log by result."""
        service.assign_role("user-001", DeploymentRole.VIEWER, assigned_by="admin")

        service.check_permission("user-001", DeploymentPermission.VIEW_DEPLOYMENTS)  # Allowed
        service.check_permission("user-001", DeploymentPermission.TRIGGER_DEPLOYMENT)  # Denied

        denied_log = service.get_access_log(allowed=False)
        assert len(denied_log) == 1
        assert denied_log[0].permission == DeploymentPermission.TRIGGER_DEPLOYMENT


class TestPolicy:
    """Tests for RBAC policy."""

    def test_configure_policy(self, service):
        """Test configuring RBAC policy."""
        policy = RBACPolicy(
            enforce_environment_scope=True,
            audit_all_checks=False,
        )
        service.configure_policy(policy)

        assert service.get_policy().enforce_environment_scope is True
        assert service.get_policy().audit_all_checks is False


class TestCustomRoles:
    """Tests for custom role definitions."""

    def test_define_custom_role(self, service):
        """Test defining a custom role."""
        service.define_custom_role(
            "release_manager",
            {
                DeploymentPermission.VIEW_DEPLOYMENTS,
                DeploymentPermission.TRIGGER_DEPLOYMENT,
                DeploymentPermission.APPROVE_DEPLOYMENT,
            }
        )

        assert "release_manager" in service._custom_roles


class TestStatistics:
    """Tests for RBAC statistics."""

    def test_get_statistics_empty(self, service):
        """Test statistics with no data."""
        stats = service.get_statistics()
        assert stats["total_assignments"] == 0
        assert stats["users_with_roles"] == 0

    def test_get_statistics_with_data(self, service):
        """Test statistics with data."""
        service.assign_role("user-001", DeploymentRole.DEPLOYER, assigned_by="admin")
        service.assign_role("user-002", DeploymentRole.VIEWER, assigned_by="admin")

        service.check_permission("user-001", DeploymentPermission.VIEW_DEPLOYMENTS)  # Allowed
        service.check_permission("user-001", DeploymentPermission.MANAGE_ROLES)  # Denied

        stats = service.get_statistics()
        assert stats["total_assignments"] == 2
        assert stats["users_with_roles"] == 2
        assert stats["by_role"]["deployer"] == 1
        assert stats["by_role"]["viewer"] == 1
        assert stats["access_checks"] == 2
        assert stats["denied_checks"] == 1


class TestSingletonPattern:
    """Tests for singleton pattern."""

    def test_singleton_instance(self):
        """Test that service is a singleton."""
        service1 = DeploymentRBACService()
        service2 = DeploymentRBACService()
        assert service1 is service2

    def test_get_service_function(self):
        """Test get_deployment_rbac_service function."""
        service = get_deployment_rbac_service()
        assert isinstance(service, DeploymentRBACService)


class TestReset:
    """Tests for service reset."""

    def test_reset_clears_state(self, service, sample_assignment):
        """Test reset clears all state."""
        service.check_permission("user-001", DeploymentPermission.VIEW_DEPLOYMENTS)

        service.reset()

        assert len(service._assignments) == 0
        assert len(service._user_assignments) == 0
        assert len(service._access_log) == 0
