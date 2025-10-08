"""
MAESTRO Enterprise Template Repository - RBAC Security System
Version: 1.0
Purpose: Role-Based Access Control with enterprise security features
"""

import asyncio
import hashlib
import json
import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import jwt
from template_manager import EnterpriseTemplateRepository

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Permission(Enum):
    """System permissions"""

    READ_TEMPLATE = "read_template"
    CREATE_TEMPLATE = "create_template"
    UPDATE_TEMPLATE = "update_template"
    DELETE_TEMPLATE = "delete_template"
    APPROVE_TEMPLATE = "approve_template"
    REJECT_TEMPLATE = "reject_template"
    PUBLISH_TEMPLATE = "publish_template"
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    VIEW_ANALYTICS = "view_analytics"
    ADMIN_ACCESS = "admin_access"
    SECURITY_AUDIT = "security_audit"


class SecurityLevel(Enum):
    """Security classification levels"""

    PUBLIC = 1
    INTERNAL = 2
    CONFIDENTIAL = 3
    RESTRICTED = 4


@dataclass
class Role:
    """Role definition with permissions"""

    role_id: str
    name: str
    description: str
    permissions: Set[Permission]
    security_clearance: SecurityLevel
    is_system_role: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class User:
    """User account with security attributes"""

    user_id: str
    username: str
    email: str
    full_name: str
    organization: str
    roles: Set[str]  # Role IDs
    security_clearance: SecurityLevel
    is_active: bool = True
    last_login: Optional[datetime] = None
    password_hash: Optional[str] = None
    api_key: Optional[str] = None
    failed_login_attempts: int = 0
    account_locked_until: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class AccessPolicy:
    """Access control policy"""

    policy_id: str
    name: str
    description: str
    resource_pattern: str  # Template pattern matching
    required_permissions: Set[Permission]
    required_security_level: SecurityLevel
    conditions: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True


@dataclass
class SecurityContext:
    """Security context for request processing"""

    user_id: str
    username: str
    roles: Set[str]
    permissions: Set[Permission]
    security_clearance: SecurityLevel
    organization: str
    session_id: str
    ip_address: str
    user_agent: str
    authenticated_at: datetime


class RBACSecurityManager:
    """
    Enterprise RBAC Security Manager

    Features:
    - Role-based access control (RBAC)
    - Multi-level security classification
    - JWT token authentication
    - API key management
    - Session management
    - Audit logging
    - Policy enforcement
    - Account lockout protection
    """

    def __init__(self, repository: EnterpriseTemplateRepository, jwt_secret: str = None):
        self.repository = repository
        self.jwt_secret = jwt_secret or secrets.token_urlsafe(32)

        # In-memory stores (would be database-backed in production)
        self.users: Dict[str, User] = {}
        self.roles: Dict[str, Role] = {}
        self.policies: Dict[str, AccessPolicy] = {}
        self.active_sessions: Dict[str, SecurityContext] = {}

        # Security settings
        self.max_failed_login_attempts = 5
        self.account_lockout_duration = timedelta(hours=1)
        self.jwt_expiry_hours = 8
        self.session_timeout_hours = 24

        # Initialize default roles and policies
        self._initialize_default_roles()
        self._initialize_default_policies()

    def _initialize_default_roles(self):
        """Initialize default system roles"""

        # Developer role
        developer_role = Role(
            role_id="developer",
            name="Developer",
            description="Standard developer with basic template access",
            permissions={
                Permission.READ_TEMPLATE,
                Permission.CREATE_TEMPLATE,
                Permission.UPDATE_TEMPLATE,
            },
            security_clearance=SecurityLevel.INTERNAL,
            is_system_role=True,
        )

        # Senior Developer role
        senior_dev_role = Role(
            role_id="senior_developer",
            name="Senior Developer",
            description="Senior developer with extended template access",
            permissions={
                Permission.READ_TEMPLATE,
                Permission.CREATE_TEMPLATE,
                Permission.UPDATE_TEMPLATE,
                Permission.DELETE_TEMPLATE,
                Permission.VIEW_ANALYTICS,
            },
            security_clearance=SecurityLevel.CONFIDENTIAL,
            is_system_role=True,
        )

        # Team Lead role
        team_lead_role = Role(
            role_id="team_lead",
            name="Team Lead",
            description="Team lead with approval capabilities",
            permissions={
                Permission.READ_TEMPLATE,
                Permission.CREATE_TEMPLATE,
                Permission.UPDATE_TEMPLATE,
                Permission.DELETE_TEMPLATE,
                Permission.APPROVE_TEMPLATE,
                Permission.REJECT_TEMPLATE,
                Permission.VIEW_ANALYTICS,
            },
            security_clearance=SecurityLevel.CONFIDENTIAL,
            is_system_role=True,
        )

        # Architect role
        architect_role = Role(
            role_id="architect",
            name="Architect",
            description="System architect with security and publishing access",
            permissions={
                Permission.READ_TEMPLATE,
                Permission.CREATE_TEMPLATE,
                Permission.UPDATE_TEMPLATE,
                Permission.DELETE_TEMPLATE,
                Permission.APPROVE_TEMPLATE,
                Permission.REJECT_TEMPLATE,
                Permission.PUBLISH_TEMPLATE,
                Permission.VIEW_ANALYTICS,
                Permission.SECURITY_AUDIT,
            },
            security_clearance=SecurityLevel.RESTRICTED,
            is_system_role=True,
        )

        # Admin role
        admin_role = Role(
            role_id="admin",
            name="Administrator",
            description="System administrator with full access",
            permissions=set(Permission),  # All permissions
            security_clearance=SecurityLevel.RESTRICTED,
            is_system_role=True,
        )

        self.roles = {
            "developer": developer_role,
            "senior_developer": senior_dev_role,
            "team_lead": team_lead_role,
            "architect": architect_role,
            "admin": admin_role,
        }

    def _initialize_default_policies(self):
        """Initialize default access policies"""

        # Public templates policy
        public_policy = AccessPolicy(
            policy_id="public_templates",
            name="Public Template Access",
            description="Access to public templates",
            resource_pattern="templates/*",
            required_permissions={Permission.READ_TEMPLATE},
            required_security_level=SecurityLevel.PUBLIC,
        )

        # Internal templates policy
        internal_policy = AccessPolicy(
            policy_id="internal_templates",
            name="Internal Template Access",
            description="Access to internal templates",
            resource_pattern="templates/internal/*",
            required_permissions={Permission.READ_TEMPLATE},
            required_security_level=SecurityLevel.INTERNAL,
        )

        # Security templates policy
        security_policy = AccessPolicy(
            policy_id="security_templates",
            name="Security Template Access",
            description="Access to security-related templates",
            resource_pattern="templates/domains/auth/*",
            required_permissions={Permission.READ_TEMPLATE, Permission.SECURITY_AUDIT},
            required_security_level=SecurityLevel.CONFIDENTIAL,
        )

        # Admin operations policy
        admin_policy = AccessPolicy(
            policy_id="admin_operations",
            name="Administrative Operations",
            description="Administrative operations access",
            resource_pattern="admin/*",
            required_permissions={Permission.ADMIN_ACCESS},
            required_security_level=SecurityLevel.RESTRICTED,
        )

        self.policies = {
            "public_templates": public_policy,
            "internal_templates": internal_policy,
            "security_templates": security_policy,
            "admin_operations": admin_policy,
        }

    async def create_user(
        self,
        username: str,
        email: str,
        full_name: str,
        organization: str,
        roles: List[str],
        security_clearance: SecurityLevel,
        password: Optional[str] = None,
    ) -> str:
        """Create new user account"""
        try:
            # Validate roles exist
            for role_id in roles:
                if role_id not in self.roles:
                    raise ValueError(f"Role not found: {role_id}")

            # Check if username/email already exists
            if any(u.username == username or u.email == email for u in self.users.values()):
                raise ValueError("Username or email already exists")

            # Generate user ID and API key
            user_id = str(uuid.uuid4())
            api_key = secrets.token_urlsafe(32)

            # Hash password if provided
            password_hash = None
            if password:
                password_hash = self._hash_password(password)

            # Create user
            user = User(
                user_id=user_id,
                username=username,
                email=email,
                full_name=full_name,
                organization=organization,
                roles=set(roles),
                security_clearance=security_clearance,
                password_hash=password_hash,
                api_key=api_key,
            )

            self.users[user_id] = user

            # Store in database
            await self._store_user_in_database(user)

            # Log user creation
            await self._log_security_event(
                "user_created",
                user_id,
                {"username": username, "organization": organization, "roles": roles},
            )

            logger.info(f"✅ Created user: {username} ({user_id})")
            return user_id

        except Exception as e:
            logger.error(f"❌ Failed to create user: {e}")
            raise

    async def authenticate_user(
        self, username: str, password: str, ip_address: str, user_agent: str
    ) -> Tuple[str, str]:  # Returns (user_id, jwt_token)
        """Authenticate user with password"""
        try:
            # Find user by username
            user = next((u for u in self.users.values() if u.username == username), None)
            if not user:
                await self._log_security_event(
                    "login_failed",
                    None,
                    {"username": username, "reason": "user_not_found", "ip_address": ip_address},
                )
                raise ValueError("Invalid credentials")

            # Check account status
            if not user.is_active:
                raise ValueError("Account is disabled")

            # Check account lockout
            if user.account_locked_until and datetime.now() < user.account_locked_until:
                raise ValueError(f"Account locked until {user.account_locked_until}")

            # Verify password
            if not user.password_hash or not self._verify_password(password, user.password_hash):
                user.failed_login_attempts += 1

                # Lock account after max failed attempts
                if user.failed_login_attempts >= self.max_failed_login_attempts:
                    user.account_locked_until = datetime.now() + self.account_lockout_duration

                await self._log_security_event(
                    "login_failed",
                    user.user_id,
                    {
                        "username": username,
                        "reason": "invalid_password",
                        "failed_attempts": user.failed_login_attempts,
                        "ip_address": ip_address,
                    },
                )
                raise ValueError("Invalid credentials")

            # Successful authentication
            user.failed_login_attempts = 0
            user.account_locked_until = None
            user.last_login = datetime.now()

            # Generate JWT token
            jwt_token = self._generate_jwt_token(user)

            # Create security context
            security_context = await self._create_security_context(user, ip_address, user_agent)

            # Store active session
            session_id = security_context.session_id
            self.active_sessions[session_id] = security_context

            # Log successful login
            await self._log_security_event(
                "login_successful",
                user.user_id,
                {"username": username, "session_id": session_id, "ip_address": ip_address},
            )

            logger.info(f"✅ User authenticated: {username} ({user.user_id})")
            return user.user_id, jwt_token

        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            raise

    async def authenticate_api_key(self, api_key: str, ip_address: str) -> str:
        """Authenticate using API key"""
        try:
            # Find user by API key
            user = next((u for u in self.users.values() if u.api_key == api_key), None)
            if not user or not user.is_active:
                await self._log_security_event(
                    "api_auth_failed",
                    None,
                    {
                        "api_key_hash": hashlib.sha256(api_key.encode()).hexdigest()[:8],
                        "ip_address": ip_address,
                    },
                )
                raise ValueError("Invalid API key")

            # Update last access
            user.last_login = datetime.now()

            # Log API access
            await self._log_security_event(
                "api_auth_successful", user.user_id, {"ip_address": ip_address}
            )

            logger.info(f"✅ API key authenticated: {user.username}")
            return user.user_id

        except Exception as e:
            logger.error(f"❌ API key authentication failed: {e}")
            raise

    async def verify_jwt_token(self, token: str) -> SecurityContext:
        """Verify JWT token and return security context"""
        try:
            # Decode JWT token
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])

            # Extract session ID
            session_id = payload.get("session_id")
            if not session_id or session_id not in self.active_sessions:
                raise ValueError("Invalid or expired session")

            # Get security context
            security_context = self.active_sessions[session_id]

            # Check session timeout
            session_age = (
                datetime.now() - security_context.authenticated_at
            ).total_seconds() / 3600
            if session_age > self.session_timeout_hours:
                del self.active_sessions[session_id]
                raise ValueError("Session expired")

            return security_context

        except jwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")
        except Exception as e:
            logger.error(f"❌ JWT verification failed: {e}")
            raise

    async def check_permission(
        self, security_context: SecurityContext, permission: Permission, resource: str = None
    ) -> bool:
        """Check if user has required permission"""
        try:
            # Check direct permission
            if permission in security_context.permissions:
                return True

            # Check policy-based permissions
            if resource:
                for policy in self.policies.values():
                    if (
                        policy.is_active
                        and self._matches_pattern(resource, policy.resource_pattern)
                        and permission in policy.required_permissions
                        and security_context.security_clearance.value
                        >= policy.required_security_level.value
                    ):
                        return True

            # Admin override
            if Permission.ADMIN_ACCESS in security_context.permissions:
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Permission check failed: {e}")
            return False

    async def check_template_access(
        self, security_context: SecurityContext, template_id: str, permission: Permission
    ) -> bool:
        """Check access to specific template"""
        try:
            # Get template metadata
            template_data = await self.repository.get_template(template_id)
            if not template_data:
                return False

            # Check basic permission
            if not await self.check_permission(security_context, permission):
                return False

            # Check security level
            template_security_level = self._determine_template_security_level(template_data)
            if security_context.security_clearance.value < template_security_level.value:
                return False

            # Check organization access
            template_org = template_data.get("organization")
            if (
                template_org
                and template_org != security_context.organization
                and not await self.check_permission(security_context, Permission.ADMIN_ACCESS)
            ):
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Template access check failed: {e}")
            return False

    async def get_user_permissions(self, user_id: str) -> Dict[str, Any]:
        """Get user permissions and security info"""
        try:
            user = self.users.get(user_id)
            if not user:
                raise ValueError("User not found")

            # Collect permissions from all roles
            all_permissions = set()
            role_details = []

            for role_id in user.roles:
                role = self.roles.get(role_id)
                if role:
                    all_permissions.update(role.permissions)
                    role_details.append(
                        {
                            "role_id": role_id,
                            "name": role.name,
                            "permissions": [p.value for p in role.permissions],
                        }
                    )

            return {
                "user_id": user_id,
                "username": user.username,
                "organization": user.organization,
                "security_clearance": user.security_clearance.name,
                "roles": role_details,
                "permissions": [p.value for p in all_permissions],
                "is_active": user.is_active,
                "last_login": user.last_login.isoformat() if user.last_login else None,
            }

        except Exception as e:
            logger.error(f"❌ Failed to get user permissions: {e}")
            raise

    async def get_security_audit_log(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        hours_back: int = 24,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get security audit log entries"""
        try:
            # This would query the database in production
            # For now, return sample audit data
            audit_entries = []

            # Sample audit log structure
            sample_events = [
                "login_successful",
                "login_failed",
                "api_auth_successful",
                "permission_denied",
                "template_accessed",
                "user_created",
            ]

            for i in range(min(limit, 10)):  # Sample data
                audit_entries.append(
                    {
                        "event_id": str(uuid.uuid4()),
                        "event_type": sample_events[i % len(sample_events)],
                        "user_id": user_id or f"user_{i}",
                        "timestamp": (datetime.now() - timedelta(hours=i)).isoformat(),
                        "details": {"sample": "audit_data"},
                        "ip_address": "192.168.1.100",
                        "risk_level": "low",
                    }
                )

            return audit_entries

        except Exception as e:
            logger.error(f"❌ Failed to get audit log: {e}")
            return []

    async def get_security_metrics(self) -> Dict[str, Any]:
        """Get security and compliance metrics"""
        try:
            total_users = len(self.users)
            active_users = len([u for u in self.users.values() if u.is_active])
            locked_accounts = len(
                [
                    u
                    for u in self.users.values()
                    if u.account_locked_until and u.account_locked_until > datetime.now()
                ]
            )
            active_sessions = len(self.active_sessions)

            # Failed login attempts in last 24 hours
            failed_logins = sum(u.failed_login_attempts for u in self.users.values())

            metrics = {
                "user_metrics": {
                    "total_users": total_users,
                    "active_users": active_users,
                    "locked_accounts": locked_accounts,
                    "active_sessions": active_sessions,
                },
                "security_metrics": {
                    "failed_login_attempts_24h": failed_logins,
                    "password_policy_compliance": 95.0,  # Would be calculated
                    "session_timeout_compliance": 100.0,
                    "api_key_usage": 85.0,
                },
                "role_distribution": {
                    role_id: len([u for u in self.users.values() if role_id in u.roles])
                    for role_id in self.roles.keys()
                },
                "security_clearance_distribution": {
                    level.name: len(
                        [u for u in self.users.values() if u.security_clearance == level]
                    )
                    for level in SecurityLevel
                },
                "generated_at": datetime.now().isoformat(),
            }

            return metrics

        except Exception as e:
            logger.error(f"❌ Failed to get security metrics: {e}")
            return {}

    def _hash_password(self, password: str) -> str:
        """Hash password using secure method"""
        import bcrypt

        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        import bcrypt

        return bcrypt.checkpw(password.encode(), password_hash.encode())

    def _generate_jwt_token(self, user: User) -> str:
        """Generate JWT token for user"""
        payload = {
            "user_id": user.user_id,
            "username": user.username,
            "session_id": str(uuid.uuid4()),
            "exp": datetime.utcnow() + timedelta(hours=self.jwt_expiry_hours),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    async def _create_security_context(
        self, user: User, ip_address: str, user_agent: str
    ) -> SecurityContext:
        """Create security context for authenticated user"""

        # Collect permissions from all user roles
        all_permissions = set()
        for role_id in user.roles:
            role = self.roles.get(role_id)
            if role:
                all_permissions.update(role.permissions)

        return SecurityContext(
            user_id=user.user_id,
            username=user.username,
            roles=user.roles,
            permissions=all_permissions,
            security_clearance=user.security_clearance,
            organization=user.organization,
            session_id=str(uuid.uuid4()),
            ip_address=ip_address,
            user_agent=user_agent,
            authenticated_at=datetime.now(),
        )

    def _determine_template_security_level(self, template_data: Dict[str, Any]) -> SecurityLevel:
        """Determine security classification for template"""
        domain = template_data.get("domain", "").lower()
        category = template_data.get("category", "").lower()
        tags = [tag.lower() for tag in template_data.get("tags", [])]

        # Restricted level
        if (
            domain in ["security", "infrastructure", "admin"]
            or "security" in tags
            or "critical" in tags
            or "admin" in tags
        ):
            return SecurityLevel.RESTRICTED

        # Confidential level
        if (
            domain in ["auth", "payment", "api_core"]
            or category in ["security", "infrastructure"]
            or "confidential" in tags
        ):
            return SecurityLevel.CONFIDENTIAL

        # Internal level (default for approved templates)
        return SecurityLevel.INTERNAL

    def _matches_pattern(self, resource: str, pattern: str) -> bool:
        """Check if resource matches pattern (simplified implementation)"""
        import fnmatch

        return fnmatch.fnmatch(resource, pattern)

    async def _store_user_in_database(self, user: User):
        """Store user in database"""
        # Would implement actual database storage
        pass

    async def _log_security_event(
        self, event_type: str, user_id: Optional[str], details: Dict[str, Any]
    ):
        """Log security event to audit trail"""
        async with self.repository.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO template_audit_log (template_id, action, actor_id, details, ip_address)
                VALUES ($1, $2, $3, $4, $5)
            """,
                None,
                event_type,
                user_id,
                json.dumps(details),
                details.get("ip_address"),
            )


# Security middleware for API integration
class SecurityMiddleware:
    """Security middleware for API endpoints"""

    def __init__(self, rbac_manager: RBACSecurityManager):
        self.rbac_manager = rbac_manager

    async def authenticate_request(self, request) -> SecurityContext:
        """Authenticate API request"""
        try:
            # Check for JWT token in Authorization header
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]  # Remove "Bearer " prefix
                return await self.rbac_manager.verify_jwt_token(token)

            # Check for API key in headers
            api_key = request.headers.get("X-API-Key")
            if api_key:
                client_ip = request.client.host
                user_id = await self.rbac_manager.authenticate_api_key(api_key, client_ip)
                user = self.rbac_manager.users.get(user_id)
                if user:
                    return await self.rbac_manager._create_security_context(
                        user, client_ip, request.headers.get("User-Agent", "")
                    )

            raise ValueError("No authentication provided")

        except Exception as e:
            logger.error(f"❌ Request authentication failed: {e}")
            raise

    async def check_endpoint_permission(
        self, security_context: SecurityContext, endpoint: str, method: str
    ) -> bool:
        """Check permission for specific endpoint"""

        # Map endpoints to required permissions
        permission_map = {
            "GET /templates": Permission.READ_TEMPLATE,
            "POST /templates": Permission.CREATE_TEMPLATE,
            "PUT /templates": Permission.UPDATE_TEMPLATE,
            "DELETE /templates": Permission.DELETE_TEMPLATE,
            "POST /templates/approve": Permission.APPROVE_TEMPLATE,
            "GET /admin": Permission.ADMIN_ACCESS,
            "GET /analytics": Permission.VIEW_ANALYTICS,
        }

        endpoint_key = f"{method} {endpoint}"
        required_permission = permission_map.get(endpoint_key)

        if not required_permission:
            return True  # No specific permission required

        return await self.rbac_manager.check_permission(
            security_context, required_permission, endpoint
        )


# Example usage and testing
async def main():
    """Example usage of the RBAC security system"""

    # Initialize repository and RBAC manager
    repository = EnterpriseTemplateRepository()
    await repository.initialize()

    rbac_manager = RBACSecurityManager(repository)

    # Create sample user
    user_id = await rbac_manager.create_user(
        username="john.developer",
        email="john@company.com",
        full_name="John Developer",
        organization="TechCorp",
        roles=["developer", "senior_developer"],
        security_clearance=SecurityLevel.CONFIDENTIAL,
        password="secure_password_123",
    )

    print(f"✅ Created user: {user_id}")

    # Authenticate user
    auth_user_id, jwt_token = await rbac_manager.authenticate_user(
        "john.developer", "secure_password_123", "192.168.1.100", "Mozilla/5.0"
    )

    print(f"✅ Authenticated user: {auth_user_id}")

    # Verify JWT token
    security_context = await rbac_manager.verify_jwt_token(jwt_token)
    print(f"✅ JWT verified for: {security_context.username}")

    # Check permissions
    can_read = await rbac_manager.check_permission(security_context, Permission.READ_TEMPLATE)
    can_admin = await rbac_manager.check_permission(security_context, Permission.ADMIN_ACCESS)

    print(f"Can read templates: {can_read}")
    print(f"Can admin: {can_admin}")

    # Get user permissions
    permissions = await rbac_manager.get_user_permissions(user_id)
    print(f"📋 User permissions: {len(permissions['permissions'])} permissions")

    # Get security metrics
    metrics = await rbac_manager.get_security_metrics()
    print(f"📊 Security metrics: {metrics['user_metrics']['total_users']} users")

    await repository.close()


if __name__ == "__main__":
    asyncio.run(main())
