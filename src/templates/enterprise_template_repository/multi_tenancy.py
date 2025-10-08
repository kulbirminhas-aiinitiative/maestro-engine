"""
MAESTRO Enterprise Template Repository - Multi-Tenancy Support
============================================================

Comprehensive multi-tenancy system for the enterprise template repository,
providing isolated environments for different organizations while maintaining
security, performance, and compliance requirements.

Features:
- Organization-based tenant isolation
- Custom tenant configurations and branding
- Resource quotas and usage monitoring
- Cross-tenant template sharing with permissions
- Tenant-specific analytics and reporting
- Hierarchical tenant management (parent-child relationships)
- Tenant lifecycle management (provisioning, migration, archival)
- Compliance and audit trail per tenant

Author: MAESTRO Enterprise Architecture Team
Version: 1.0
"""

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import asyncpg

logger = logging.getLogger(__name__)


class TenantStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"
    PENDING_SETUP = "pending_setup"


class TenantPlan(Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class ResourceType(Enum):
    TEMPLATES = "templates"
    STORAGE_GB = "storage_gb"
    USERS = "users"
    API_REQUESTS = "api_requests"
    SEARCHES_PER_DAY = "searches_per_day"


@dataclass
class TenantConfiguration:
    """Tenant-specific configuration"""

    tenant_id: str
    organization_name: str
    display_name: str
    status: TenantStatus
    plan: TenantPlan
    custom_domain: Optional[str] = None
    branding: Dict[str, Any] = None
    features: List[str] = None
    quotas: Dict[str, int] = None
    settings: Dict[str, Any] = None
    parent_tenant_id: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None


@dataclass
class ResourceQuota:
    """Resource quota definition"""

    tenant_id: str
    resource_type: ResourceType
    quota_limit: int
    current_usage: int
    warning_threshold: float  # percentage (0.0-1.0)
    hard_limit_reached: bool
    last_updated: datetime


@dataclass
class TenantUsageMetrics:
    """Tenant usage metrics"""

    tenant_id: str
    period_start: datetime
    period_end: datetime
    templates_created: int
    templates_accessed: int
    api_requests: int
    unique_users: int
    storage_used_gb: float
    search_queries: int
    collaboration_sessions: int


class MultiTenancyManager:
    """Multi-tenancy management system"""

    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.db_pool = None
        self.default_quotas = self._load_default_quotas()
        self.plan_features = self._load_plan_features()

    async def initialize(self):
        """Initialize multi-tenancy system"""
        try:
            self.db_pool = await asyncpg.create_pool(**self.db_config, max_size=20)
            await self._create_tenancy_tables()
            await self._create_default_tenant()
            logger.info("Multi-tenancy system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize multi-tenancy: {e}")
            raise

    async def _create_tenancy_tables(self):
        """Create multi-tenancy database tables"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                -- Tenants table
                CREATE TABLE IF NOT EXISTS tenants (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id VARCHAR(100) UNIQUE NOT NULL,
                    organization_name VARCHAR(200) NOT NULL,
                    display_name VARCHAR(200) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    plan VARCHAR(20) NOT NULL DEFAULT 'starter',
                    custom_domain VARCHAR(200),
                    branding JSONB DEFAULT '{}',
                    features JSONB DEFAULT '[]',
                    quotas JSONB DEFAULT '{}',
                    settings JSONB DEFAULT '{}',
                    parent_tenant_id VARCHAR(100) REFERENCES tenants(tenant_id),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    created_by VARCHAR(100),
                    CONSTRAINT valid_status CHECK (status IN ('active', 'inactive', 'suspended', 'archived', 'pending_setup')),
                    CONSTRAINT valid_plan CHECK (plan IN ('starter', 'professional', 'enterprise', 'custom'))
                );

                -- Resource quotas table
                CREATE TABLE IF NOT EXISTS tenant_quotas (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id VARCHAR(100) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
                    resource_type VARCHAR(50) NOT NULL,
                    quota_limit INTEGER NOT NULL,
                    current_usage INTEGER DEFAULT 0,
                    warning_threshold DECIMAL(3,2) DEFAULT 0.80,
                    hard_limit_reached BOOLEAN DEFAULT FALSE,
                    last_updated TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(tenant_id, resource_type)
                );

                -- Tenant usage metrics table
                CREATE TABLE IF NOT EXISTS tenant_usage (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id VARCHAR(100) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
                    metric_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    templates_created INTEGER DEFAULT 0,
                    templates_accessed INTEGER DEFAULT 0,
                    api_requests INTEGER DEFAULT 0,
                    unique_users INTEGER DEFAULT 0,
                    storage_used_gb DECIMAL(10,2) DEFAULT 0,
                    search_queries INTEGER DEFAULT 0,
                    collaboration_sessions INTEGER DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(tenant_id, metric_date)
                );

                -- Tenant-specific template sharing permissions
                CREATE TABLE IF NOT EXISTS tenant_template_sharing (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
                    owner_tenant_id VARCHAR(100) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
                    shared_with_tenant_id VARCHAR(100) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
                    permission_level VARCHAR(20) NOT NULL DEFAULT 'read',
                    shared_at TIMESTAMPTZ DEFAULT NOW(),
                    shared_by VARCHAR(100) NOT NULL,
                    expires_at TIMESTAMPTZ,
                    CONSTRAINT valid_permission CHECK (permission_level IN ('read', 'write', 'admin')),
                    UNIQUE(template_id, shared_with_tenant_id)
                );

                -- Tenant audit log
                CREATE TABLE IF NOT EXISTS tenant_audit_log (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id VARCHAR(100) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
                    action VARCHAR(100) NOT NULL,
                    resource_type VARCHAR(50) NOT NULL,
                    resource_id VARCHAR(100),
                    user_id VARCHAR(100) NOT NULL,
                    user_email VARCHAR(200),
                    details JSONB DEFAULT '{}',
                    ip_address INET,
                    user_agent TEXT,
                    timestamp TIMESTAMPTZ DEFAULT NOW(),
                    session_id VARCHAR(100)
                );

                -- Add tenant_id column to existing templates table if it doesn't exist
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                   WHERE table_name = 'templates' AND column_name = 'tenant_id') THEN
                        ALTER TABLE templates ADD COLUMN tenant_id VARCHAR(100) DEFAULT 'default' REFERENCES tenants(tenant_id);
                    END IF;
                END $$;

                -- Create indexes for performance
                CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status);
                CREATE INDEX IF NOT EXISTS idx_tenants_plan ON tenants(plan);
                CREATE INDEX IF NOT EXISTS idx_tenant_quotas_tenant_id ON tenant_quotas(tenant_id);
                CREATE INDEX IF NOT EXISTS idx_tenant_usage_tenant_date ON tenant_usage(tenant_id, metric_date);
                CREATE INDEX IF NOT EXISTS idx_templates_tenant_id ON templates(tenant_id);
                CREATE INDEX IF NOT EXISTS idx_tenant_audit_timestamp ON tenant_audit_log(tenant_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_tenant_sharing_template ON tenant_template_sharing(template_id);
            """
            )

    async def _create_default_tenant(self):
        """Create default tenant if it doesn't exist"""
        async with self.db_pool.acquire() as conn:
            exists = await conn.fetchval(
                """
                SELECT EXISTS(SELECT 1 FROM tenants WHERE tenant_id = 'default')
            """
            )

            if not exists:
                await conn.execute(
                    """
                    INSERT INTO tenants (tenant_id, organization_name, display_name, status, plan)
                    VALUES ('default', 'Default Organization', 'Default', 'active', 'enterprise')
                """
                )

                # Set up default quotas
                await self._setup_tenant_quotas("default", TenantPlan.ENTERPRISE)
                logger.info("Default tenant created")

    def _load_default_quotas(self) -> Dict[TenantPlan, Dict[ResourceType, int]]:
        """Load default resource quotas by plan"""
        return {
            TenantPlan.STARTER: {
                ResourceType.TEMPLATES: 100,
                ResourceType.STORAGE_GB: 1,
                ResourceType.USERS: 5,
                ResourceType.API_REQUESTS: 10000,
                ResourceType.SEARCHES_PER_DAY: 1000,
            },
            TenantPlan.PROFESSIONAL: {
                ResourceType.TEMPLATES: 1000,
                ResourceType.STORAGE_GB: 10,
                ResourceType.USERS: 25,
                ResourceType.API_REQUESTS: 100000,
                ResourceType.SEARCHES_PER_DAY: 10000,
            },
            TenantPlan.ENTERPRISE: {
                ResourceType.TEMPLATES: 10000,
                ResourceType.STORAGE_GB: 100,
                ResourceType.USERS: 100,
                ResourceType.API_REQUESTS: 1000000,
                ResourceType.SEARCHES_PER_DAY: 100000,
            },
            TenantPlan.CUSTOM: {
                ResourceType.TEMPLATES: 50000,
                ResourceType.STORAGE_GB: 500,
                ResourceType.USERS: 500,
                ResourceType.API_REQUESTS: 5000000,
                ResourceType.SEARCHES_PER_DAY: 500000,
            },
        }

    def _load_plan_features(self) -> Dict[TenantPlan, List[str]]:
        """Load features available by plan"""
        return {
            TenantPlan.STARTER: ["basic_templates", "semantic_search", "basic_analytics"],
            TenantPlan.PROFESSIONAL: [
                "basic_templates",
                "semantic_search",
                "basic_analytics",
                "custom_branding",
                "api_access",
                "template_sharing",
                "advanced_search",
            ],
            TenantPlan.ENTERPRISE: [
                "basic_templates",
                "semantic_search",
                "basic_analytics",
                "custom_branding",
                "api_access",
                "template_sharing",
                "advanced_search",
                "rbac_security",
                "approval_workflows",
                "governance_dashboard",
                "performance_monitoring",
                "audit_trail",
            ],
            TenantPlan.CUSTOM: ["all_features", "custom_integrations", "dedicated_support"],
        }

    async def create_tenant(
        self,
        organization_name: str,
        display_name: str,
        plan: TenantPlan,
        created_by: str,
        custom_config: Dict[str, Any] = None,
    ) -> str:
        """Create new tenant"""
        tenant_id = f"tenant_{uuid.uuid4().hex[:8]}"

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tenants
                (tenant_id, organization_name, display_name, status, plan,
                 branding, features, settings, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
                tenant_id,
                organization_name,
                display_name,
                TenantStatus.PENDING_SETUP.value,
                plan.value,
                json.dumps(custom_config.get("branding", {}) if custom_config else {}),
                json.dumps(self.plan_features.get(plan, [])),
                json.dumps(custom_config.get("settings", {}) if custom_config else {}),
                created_by,
            )

        # Set up quotas
        await self._setup_tenant_quotas(tenant_id, plan, custom_config)

        # Log tenant creation
        await self._log_tenant_action(
            tenant_id, "tenant_created", "tenant", tenant_id, created_by, {"plan": plan.value}
        )

        logger.info(f"Created tenant {tenant_id} for {organization_name}")
        return tenant_id

    async def _setup_tenant_quotas(
        self, tenant_id: str, plan: TenantPlan, custom_config: Dict[str, Any] = None
    ):
        """Set up resource quotas for tenant"""
        quotas = self.default_quotas.get(plan, self.default_quotas[TenantPlan.STARTER])

        # Override with custom quotas if provided
        if custom_config and "quotas" in custom_config:
            for resource, limit in custom_config["quotas"].items():
                if ResourceType(resource) in quotas:
                    quotas[ResourceType(resource)] = limit

        async with self.db_pool.acquire() as conn:
            for resource_type, limit in quotas.items():
                await conn.execute(
                    """
                    INSERT INTO tenant_quotas (tenant_id, resource_type, quota_limit)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (tenant_id, resource_type) DO UPDATE SET
                        quota_limit = EXCLUDED.quota_limit,
                        last_updated = NOW()
                """,
                    tenant_id,
                    resource_type.value,
                    limit,
                )

    async def get_tenant(self, tenant_id: str) -> Optional[TenantConfiguration]:
        """Get tenant configuration"""
        async with self.db_pool.acquire() as conn:
            tenant_row = await conn.fetchrow(
                """
                SELECT * FROM tenants WHERE tenant_id = $1
            """,
                tenant_id,
            )

            if not tenant_row:
                return None

            return TenantConfiguration(
                tenant_id=tenant_row["tenant_id"],
                organization_name=tenant_row["organization_name"],
                display_name=tenant_row["display_name"],
                status=TenantStatus(tenant_row["status"]),
                plan=TenantPlan(tenant_row["plan"]),
                custom_domain=tenant_row["custom_domain"],
                branding=json.loads(tenant_row["branding"] or "{}"),
                features=json.loads(tenant_row["features"] or "[]"),
                quotas=json.loads(tenant_row["quotas"] or "{}"),
                settings=json.loads(tenant_row["settings"] or "{}"),
                parent_tenant_id=tenant_row["parent_tenant_id"],
                created_at=tenant_row["created_at"],
                updated_at=tenant_row["updated_at"],
            )

    async def list_tenants(
        self,
        status_filter: Optional[TenantStatus] = None,
        plan_filter: Optional[TenantPlan] = None,
        parent_tenant_id: Optional[str] = None,
    ) -> List[TenantConfiguration]:
        """List tenants with optional filters"""
        conditions = []
        params = []
        param_count = 0

        if status_filter:
            param_count += 1
            conditions.append(f"status = ${param_count}")
            params.append(status_filter.value)

        if plan_filter:
            param_count += 1
            conditions.append(f"plan = ${param_count}")
            params.append(plan_filter.value)

        if parent_tenant_id is not None:
            param_count += 1
            if parent_tenant_id == "":
                conditions.append("parent_tenant_id IS NULL")
            else:
                conditions.append(f"parent_tenant_id = ${param_count}")
                params.append(parent_tenant_id)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM tenants {where_clause}
                ORDER BY created_at DESC
            """,
                *params,
            )

            tenants = []
            for row in rows:
                tenants.append(
                    TenantConfiguration(
                        tenant_id=row["tenant_id"],
                        organization_name=row["organization_name"],
                        display_name=row["display_name"],
                        status=TenantStatus(row["status"]),
                        plan=TenantPlan(row["plan"]),
                        custom_domain=row["custom_domain"],
                        branding=json.loads(row["branding"] or "{}"),
                        features=json.loads(row["features"] or "[]"),
                        quotas=json.loads(row["quotas"] or "{}"),
                        settings=json.loads(row["settings"] or "{}"),
                        parent_tenant_id=row["parent_tenant_id"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
                )

            return tenants

    async def update_tenant(self, tenant_id: str, updates: Dict[str, Any], updated_by: str) -> bool:
        """Update tenant configuration"""
        if not updates:
            return False

        set_clauses = []
        params = []
        param_count = 0

        # Handle direct field updates
        direct_fields = ["organization_name", "display_name", "status", "plan", "custom_domain"]
        for field in direct_fields:
            if field in updates:
                param_count += 1
                set_clauses.append(f"{field} = ${param_count}")
                params.append(updates[field])

        # Handle JSON field updates
        json_fields = ["branding", "features", "settings"]
        for field in json_fields:
            if field in updates:
                param_count += 1
                set_clauses.append(f"{field} = ${param_count}")
                params.append(json.dumps(updates[field]))

        if not set_clauses:
            return False

        # Add updated_at
        param_count += 1
        set_clauses.append(f"updated_at = ${param_count}")
        params.append(datetime.now())

        # Add tenant_id for WHERE clause
        param_count += 1
        params.append(tenant_id)

        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                f"""
                UPDATE tenants SET {', '.join(set_clauses)}
                WHERE tenant_id = ${param_count}
            """,
                *params,
            )

            if result.split()[-1] == "1":
                # Log update
                await self._log_tenant_action(
                    tenant_id, "tenant_updated", "tenant", tenant_id, updated_by, updates
                )
                return True

        return False

    async def delete_tenant(self, tenant_id: str, deleted_by: str, force: bool = False) -> bool:
        """Delete/archive tenant"""
        if tenant_id == "default":
            raise ValueError("Cannot delete default tenant")

        async with self.db_pool.acquire() as conn:
            # Check if tenant has child tenants
            has_children = await conn.fetchval(
                """
                SELECT EXISTS(SELECT 1 FROM tenants WHERE parent_tenant_id = $1)
            """,
                tenant_id,
            )

            if has_children and not force:
                raise ValueError(
                    "Cannot delete tenant with child tenants. Use force=True or delete children first."
                )

            # Check if tenant has templates
            template_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM templates WHERE tenant_id = $1
            """,
                tenant_id,
            )

            if template_count > 0 and not force:
                # Archive instead of delete
                await conn.execute(
                    """
                    UPDATE tenants SET status = $1, updated_at = NOW()
                    WHERE tenant_id = $2
                """,
                    TenantStatus.ARCHIVED.value,
                    tenant_id,
                )

                await self._log_tenant_action(
                    tenant_id,
                    "tenant_archived",
                    "tenant",
                    tenant_id,
                    deleted_by,
                    {"template_count": template_count},
                )
                logger.info(f"Archived tenant {tenant_id} with {template_count} templates")
                return True
            else:
                # Hard delete
                await conn.execute("DELETE FROM tenants WHERE tenant_id = $1", tenant_id)
                await self._log_tenant_action(
                    tenant_id, "tenant_deleted", "tenant", tenant_id, deleted_by, {"force": force}
                )
                logger.info(f"Deleted tenant {tenant_id}")
                return True

    async def get_tenant_quotas(self, tenant_id: str) -> List[ResourceQuota]:
        """Get tenant resource quotas"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM tenant_quotas WHERE tenant_id = $1
                ORDER BY resource_type
            """,
                tenant_id,
            )

            quotas = []
            for row in rows:
                quotas.append(
                    ResourceQuota(
                        tenant_id=row["tenant_id"],
                        resource_type=ResourceType(row["resource_type"]),
                        quota_limit=row["quota_limit"],
                        current_usage=row["current_usage"],
                        warning_threshold=float(row["warning_threshold"]),
                        hard_limit_reached=row["hard_limit_reached"],
                        last_updated=row["last_updated"],
                    )
                )

            return quotas

    async def update_resource_usage(
        self, tenant_id: str, resource_type: ResourceType, usage_delta: int = 1
    ) -> bool:
        """Update resource usage for tenant"""
        async with self.db_pool.acquire() as conn:
            # Update current usage
            result = await conn.execute(
                """
                UPDATE tenant_quotas
                SET current_usage = current_usage + $1,
                    last_updated = NOW(),
                    hard_limit_reached = (current_usage + $1) >= quota_limit
                WHERE tenant_id = $2 AND resource_type = $3
                RETURNING current_usage, quota_limit, hard_limit_reached
            """,
                usage_delta,
                tenant_id,
                resource_type.value,
            )

            if result.split()[-1] == "1":
                # Check if quota exceeded
                quota_info = await conn.fetchrow(
                    """
                    SELECT current_usage, quota_limit, warning_threshold, hard_limit_reached
                    FROM tenant_quotas
                    WHERE tenant_id = $1 AND resource_type = $2
                """,
                    tenant_id,
                    resource_type.value,
                )

                if quota_info:
                    usage_percent = quota_info["current_usage"] / quota_info["quota_limit"]

                    # Log quota events
                    if quota_info["hard_limit_reached"]:
                        await self._log_tenant_action(
                            tenant_id,
                            "quota_exceeded",
                            "quota",
                            resource_type.value,
                            "system",
                            {
                                "current_usage": quota_info["current_usage"],
                                "quota_limit": quota_info["quota_limit"],
                                "usage_percent": round(usage_percent * 100, 2),
                            },
                        )
                    elif usage_percent >= quota_info["warning_threshold"]:
                        await self._log_tenant_action(
                            tenant_id,
                            "quota_warning",
                            "quota",
                            resource_type.value,
                            "system",
                            {
                                "current_usage": quota_info["current_usage"],
                                "quota_limit": quota_info["quota_limit"],
                                "usage_percent": round(usage_percent * 100, 2),
                            },
                        )

                return True

        return False

    async def check_quota_availability(
        self, tenant_id: str, resource_type: ResourceType, requested_amount: int = 1
    ) -> bool:
        """Check if tenant has available quota"""
        async with self.db_pool.acquire() as conn:
            quota_info = await conn.fetchrow(
                """
                SELECT current_usage, quota_limit
                FROM tenant_quotas
                WHERE tenant_id = $1 AND resource_type = $2
            """,
                tenant_id,
                resource_type.value,
            )

            if quota_info:
                available = quota_info["quota_limit"] - quota_info["current_usage"]
                return available >= requested_amount

        return False

    async def get_tenant_usage_metrics(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[TenantUsageMetrics]:
        """Get tenant usage metrics"""
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM tenant_usage
                WHERE tenant_id = $1 AND metric_date BETWEEN $2 AND $3
                ORDER BY metric_date DESC
            """,
                tenant_id,
                start_date.date(),
                end_date.date(),
            )

            metrics = []
            for row in rows:
                # Convert date to datetime for period start/end
                period_start = datetime.combine(row["metric_date"], datetime.min.time())
                period_end = datetime.combine(row["metric_date"], datetime.max.time())

                metrics.append(
                    TenantUsageMetrics(
                        tenant_id=row["tenant_id"],
                        period_start=period_start,
                        period_end=period_end,
                        templates_created=row["templates_created"],
                        templates_accessed=row["templates_accessed"],
                        api_requests=row["api_requests"],
                        unique_users=row["unique_users"],
                        storage_used_gb=float(row["storage_used_gb"]),
                        search_queries=row["search_queries"],
                        collaboration_sessions=row["collaboration_sessions"],
                    )
                )

            return metrics

    async def record_usage_metric(self, tenant_id: str, metric_type: str, value: int = 1):
        """Record usage metric for tenant"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO tenant_usage (tenant_id, {metric_type})
                VALUES ($1, $2)
                ON CONFLICT (tenant_id, metric_date) DO UPDATE SET
                    {metric_type} = tenant_usage.{metric_type} + EXCLUDED.{metric_type}
            """,
                tenant_id,
                value,
            )

    async def share_template_with_tenant(
        self,
        template_id: str,
        owner_tenant_id: str,
        target_tenant_id: str,
        permission_level: str,
        shared_by: str,
        expires_at: Optional[datetime] = None,
    ) -> bool:
        """Share template with another tenant"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tenant_template_sharing
                (template_id, owner_tenant_id, shared_with_tenant_id, permission_level, shared_by, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (template_id, shared_with_tenant_id) DO UPDATE SET
                    permission_level = EXCLUDED.permission_level,
                    shared_at = NOW(),
                    shared_by = EXCLUDED.shared_by,
                    expires_at = EXCLUDED.expires_at
            """,
                template_id,
                owner_tenant_id,
                target_tenant_id,
                permission_level,
                shared_by,
                expires_at,
            )

            await self._log_tenant_action(
                owner_tenant_id,
                "template_shared",
                "template",
                template_id,
                shared_by,
                {"target_tenant": target_tenant_id, "permission_level": permission_level},
            )

            return True

    async def get_shared_templates(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get templates shared with tenant"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT t.*, s.permission_level, s.shared_at, s.expires_at,
                       owner.organization_name as owner_org
                FROM templates t
                JOIN tenant_template_sharing s ON t.id = s.template_id
                JOIN tenants owner ON s.owner_tenant_id = owner.tenant_id
                WHERE s.shared_with_tenant_id = $1
                  AND (s.expires_at IS NULL OR s.expires_at > NOW())
                ORDER BY s.shared_at DESC
            """,
                tenant_id,
            )

            return [dict(row) for row in rows]

    async def _log_tenant_action(
        self,
        tenant_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        user_id: str,
        details: Dict[str, Any] = None,
        ip_address: str = None,
        user_agent: str = None,
    ):
        """Log tenant action for audit trail"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tenant_audit_log
                (tenant_id, action, resource_type, resource_id, user_id, details, ip_address, user_agent)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                tenant_id,
                action,
                resource_type,
                resource_id,
                user_id,
                json.dumps(details or {}),
                ip_address,
                user_agent,
            )

    async def get_tenant_audit_log(
        self, tenant_id: str, limit: int = 100, action_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get tenant audit log"""
        conditions = ["tenant_id = $1"]
        params = [tenant_id]

        if action_filter:
            conditions.append("action = $2")
            params.append(action_filter)

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM tenant_audit_log
                WHERE {' AND '.join(conditions)}
                ORDER BY timestamp DESC
                LIMIT ${len(params) + 1}
            """,
                *params,
                limit,
            )

            return [dict(row) for row in rows]

    async def get_multi_tenant_analytics(self) -> Dict[str, Any]:
        """Get multi-tenant analytics overview"""
        async with self.db_pool.acquire() as conn:
            # Tenant counts by status
            status_counts = await conn.fetch(
                """
                SELECT status, COUNT(*) as count
                FROM tenants
                GROUP BY status
                ORDER BY count DESC
            """
            )

            # Tenant counts by plan
            plan_counts = await conn.fetch(
                """
                SELECT plan, COUNT(*) as count
                FROM tenants
                GROUP BY plan
                ORDER BY count DESC
            """
            )

            # Resource usage summary
            resource_usage = await conn.fetch(
                """
                SELECT resource_type,
                       SUM(current_usage) as total_usage,
                       SUM(quota_limit) as total_quota,
                       COUNT(*) as tenant_count
                FROM tenant_quotas
                GROUP BY resource_type
            """
            )

            # Top tenants by template count
            top_tenants = await conn.fetch(
                """
                SELECT t.tenant_id, t.organization_name, COUNT(tpl.id) as template_count
                FROM tenants t
                LEFT JOIN templates tpl ON t.tenant_id = tpl.tenant_id
                WHERE t.status = 'active'
                GROUP BY t.tenant_id, t.organization_name
                ORDER BY template_count DESC
                LIMIT 10
            """
            )

            return {
                "tenant_counts": {
                    "by_status": [dict(row) for row in status_counts],
                    "by_plan": [dict(row) for row in plan_counts],
                },
                "resource_usage": [dict(row) for row in resource_usage],
                "top_tenants": [dict(row) for row in top_tenants],
                "generated_at": datetime.now().isoformat(),
            }

    async def cleanup(self):
        """Cleanup resources"""
        if self.db_pool:
            await self.db_pool.close()
        logger.info("Multi-tenancy manager cleanup completed")


# Tenant context manager for request isolation
class TenantContext:
    """Context manager for tenant-specific operations"""

    def __init__(self, tenant_id: str, multi_tenancy_manager: MultiTenancyManager):
        self.tenant_id = tenant_id
        self.manager = multi_tenancy_manager
        self.tenant_config = None

    async def __aenter__(self):
        """Enter tenant context"""
        self.tenant_config = await self.manager.get_tenant(self.tenant_id)
        if not self.tenant_config:
            raise ValueError(f"Tenant {self.tenant_id} not found")

        if self.tenant_config.status != TenantStatus.ACTIVE:
            raise ValueError(
                f"Tenant {self.tenant_id} is not active (status: {self.tenant_config.status.value})"
            )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit tenant context"""
        pass

    def has_feature(self, feature: str) -> bool:
        """Check if tenant has specific feature"""
        if not self.tenant_config:
            return False

        return (
            feature in self.tenant_config.features or "all_features" in self.tenant_config.features
        )

    async def check_quota(self, resource_type: ResourceType, amount: int = 1) -> bool:
        """Check quota availability"""
        return await self.manager.check_quota_availability(self.tenant_id, resource_type, amount)

    async def consume_quota(self, resource_type: ResourceType, amount: int = 1) -> bool:
        """Consume quota"""
        return await self.manager.update_resource_usage(self.tenant_id, resource_type, amount)


if __name__ == "__main__":
    # Example usage
    import asyncio

    async def main():
        db_config = {
            "host": "localhost",
            "port": 5432,
            "database": "maestro_templates",
            "user": "postgres",
            "password": "your_password",
        }

        manager = MultiTenancyManager(db_config)
        await manager.initialize()

        # Create a new tenant
        tenant_id = await manager.create_tenant(
            "Acme Corporation", "Acme Corp", TenantPlan.ENTERPRISE, "admin@acme.com"
        )

        print(f"Created tenant: {tenant_id}")

        # Use tenant context
        async with TenantContext(tenant_id, manager) as tenant_ctx:
            print(f"Tenant has RBAC: {tenant_ctx.has_feature('rbac_security')}")

            can_create = await tenant_ctx.check_quota(ResourceType.TEMPLATES, 1)
            print(f"Can create template: {can_create}")

        await manager.cleanup()

    # asyncio.run(main())
