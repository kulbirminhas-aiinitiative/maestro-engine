"""
DAG Catalog Service

Manages storage, retrieval, and organization of DAG workflow definitions.
Provides a catalog of pre-built templates and user-created custom workflows.

Storage: Redis for fast access, with optional PostgreSQL backup
Schema:
    dag:template:{id} → Hash with {dag_json, metadata}
    dag:catalog → Sorted set of DAG IDs by creation time
    dag:category:{category} → Set of DAG IDs in that category
    dag:user:{user_id}:dags → Set of user's custom DAG IDs
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from workflow.dag import DAG, TaskNode, TaskType, WorkflowBuilder
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class DAGCatalogService:
    """
    Service for managing workflow DAG definitions.

    Features:
    - Store DAG definitions (templates and custom)
    - Retrieve DAG by ID
    - List/search DAGs by category
    - Convert legacy templates to DAG format
    - Version management
    """

    def __init__(self, redis_url: str = "redis://localhost:6380", db: int = 1):
        """
        Initialize DAG Catalog Service.

        Args:
            redis_url: Redis connection URL
            db: Redis database number (use separate DB from workflow state)
        """
        self.redis_url = redis_url
        self.db = db
        self.client: Optional[redis.Redis] = None
        logger.info(f"📚 DAG Catalog Service initialized: {redis_url} (DB {db})")

    async def connect(self):
        """Establish Redis connection"""
        if self.client is None:
            self.client = await redis.from_url(
                self.redis_url,
                db=self.db,
                decode_responses=True,
                encoding="utf-8"
            )
            logger.info("✅ Connected to Redis (DAG Catalog)")

    async def disconnect(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            self.client = None
            logger.info("Disconnected from Redis (DAG Catalog)")

    # ========================================================================
    # STORAGE OPERATIONS
    # ========================================================================

    async def store_dag(
        self,
        dag: DAG,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        Store a DAG definition in the catalog.

        Args:
            dag: DAG instance to store
            metadata: Additional metadata (category, description, etc.)
            user_id: User who created this DAG (for custom workflows)

        Returns:
            DAG ID
        """
        await self.connect()

        dag_id = dag.workflow_id

        # Prepare storage data
        storage_data = {
            "dag_id": dag_id,
            "dag_json": dag.to_json(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "version": "1.0"
        }

        # Add metadata
        if metadata:
            storage_data.update(metadata)

        if user_id:
            storage_data["created_by"] = user_id
            storage_data["is_template"] = False
        else:
            storage_data["is_template"] = True

        # Store DAG
        await self.client.hset(
            f"dag:template:{dag_id}",
            mapping={k: str(v) for k, v in storage_data.items()}
        )

        # Add to catalog index (sorted by creation time)
        timestamp = datetime.now().timestamp()
        await self.client.zadd("dag:catalog", {dag_id: timestamp})

        # Add to category index if provided
        if metadata and "category" in metadata:
            category = metadata["category"]
            await self.client.sadd(f"dag:category:{category}", dag_id)

        # Add to user's DAG list if custom
        if user_id:
            await self.client.sadd(f"dag:user:{user_id}:dags", dag_id)

        # Set TTL (30 days for templates, 7 days for custom)
        ttl = 2592000 if not user_id else 604800
        await self.client.expire(f"dag:template:{dag_id}", ttl)

        logger.info(f"📝 Stored DAG: {dag_id} (name: {dag.name})")
        return dag_id

    async def get_dag(self, dag_id: str) -> Optional[DAG]:
        """
        Retrieve a DAG by ID.

        Args:
            dag_id: DAG identifier

        Returns:
            DAG instance or None if not found
        """
        await self.connect()

        # Get DAG data
        data = await self.client.hgetall(f"dag:template:{dag_id}")

        if not data or "dag_json" not in data:
            logger.warning(f"DAG not found: {dag_id}")
            return None

        # Deserialize DAG
        try:
            dag = DAG.from_json(data["dag_json"])
            logger.info(f"📖 Retrieved DAG: {dag_id}")
            return dag
        except Exception as e:
            logger.error(f"Failed to deserialize DAG {dag_id}: {e}")
            return None

    async def get_dag_metadata(self, dag_id: str) -> Optional[Dict[str, Any]]:
        """
        Get DAG metadata without loading full DAG.

        Args:
            dag_id: DAG identifier

        Returns:
            Dict with metadata or None
        """
        await self.connect()

        data = await self.client.hgetall(f"dag:template:{dag_id}")

        if not data:
            return None

        # Remove dag_json for lightweight response
        metadata = dict(data)
        metadata.pop("dag_json", None)

        return metadata

    async def list_dags(
        self,
        category: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List DAGs with optional filtering.

        Args:
            category: Filter by category
            user_id: Filter by user (custom DAGs only)
            limit: Maximum number of results

        Returns:
            List of DAG metadata (without full DAG JSON)
        """
        await self.connect()

        # Get DAG IDs based on filter
        if user_id:
            # Get user's custom DAGs
            dag_ids = list(await self.client.smembers(f"dag:user:{user_id}:dags"))
        elif category:
            # Get DAGs in category
            dag_ids = list(await self.client.smembers(f"dag:category:{category}"))
        else:
            # Get all DAGs (sorted by creation time, newest first)
            dag_ids = await self.client.zrevrange("dag:catalog", 0, limit - 1)

        # Fetch metadata for each DAG
        results = []
        for dag_id in dag_ids[:limit]:
            metadata = await self.get_dag_metadata(dag_id)
            if metadata:
                results.append(metadata)

        logger.info(f"📋 Listed {len(results)} DAGs (category={category}, user={user_id})")
        return results

    async def search_dags(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search DAGs by name or description.

        Args:
            query: Search query string
            limit: Maximum results

        Returns:
            List of matching DAG metadata
        """
        await self.connect()

        # Get all DAGs
        all_dags = await self.list_dags(limit=1000)

        # Simple text matching (can be enhanced with better search)
        query_lower = query.lower()
        matches = []

        for dag_meta in all_dags:
            # Search in name, description, category
            searchable = " ".join([
                dag_meta.get("name", ""),
                dag_meta.get("description", ""),
                dag_meta.get("category", "")
            ]).lower()

            if query_lower in searchable:
                matches.append(dag_meta)

            if len(matches) >= limit:
                break

        logger.info(f"🔍 Search '{query}' found {len(matches)} results")
        return matches

    async def delete_dag(self, dag_id: str, user_id: Optional[str] = None) -> bool:
        """
        Delete a DAG from catalog.

        Args:
            dag_id: DAG identifier
            user_id: User ID (required for custom DAGs)

        Returns:
            Success status
        """
        await self.connect()

        # Get metadata to check ownership
        metadata = await self.get_dag_metadata(dag_id)

        if not metadata:
            return False

        # Prevent deletion of templates unless explicitly allowed
        if metadata.get("is_template") == "True":
            logger.warning(f"Cannot delete template DAG: {dag_id}")
            return False

        # Check ownership for custom DAGs
        if user_id and metadata.get("created_by") != user_id:
            logger.warning(f"User {user_id} cannot delete DAG {dag_id} (not owner)")
            return False

        # Delete DAG data
        await self.client.delete(f"dag:template:{dag_id}")

        # Remove from indexes
        await self.client.zrem("dag:catalog", dag_id)

        if metadata.get("category"):
            await self.client.srem(f"dag:category:{metadata['category']}", dag_id)

        if user_id:
            await self.client.srem(f"dag:user:{user_id}:dags", dag_id)

        logger.info(f"🗑️  Deleted DAG: {dag_id}")
        return True

    # ========================================================================
    # TEMPLATE INITIALIZATION
    # ========================================================================

    async def initialize_templates(self):
        """
        Initialize catalog with pre-built DAG templates.

        Creates 4 templates matching the frontend:
        - SaaS Application
        - Microservice API
        - Mobile App
        - Enterprise System
        """
        logger.info("\n" + "="*80)
        logger.info("🏗️  INITIALIZING DAG TEMPLATES")
        logger.info("="*80)

        templates = [
            await self._create_saas_template(),
            await self._create_microservice_template(),
            await self._create_mobile_template(),
            await self._create_enterprise_template()
        ]

        for dag, metadata in templates:
            await self.store_dag(dag, metadata)

        logger.info(f"✅ Initialized {len(templates)} templates")
        logger.info("="*80 + "\n")

    async def _create_saas_template(self) -> tuple[DAG, Dict]:
        """Create SaaS Application template"""

        builder = WorkflowBuilder(
            workflow_id="template_saas_app",
            name="SaaS Application",
            description="Complete workflow for SaaS product development with frontend, backend, and deployment"
        )

        dag = (builder
            .add_task(
                "requirements",
                "Requirements Analysis",
                "Gather and document requirements, user stories, and acceptance criteria",
                task_type=TaskType.RESEARCH,
                priority=10,
                metadata={"duration_estimate": "2-3 days", "phase_type": "planning"},
                tags=["requirements", "planning", "user-stories"]
            )
            .add_task(
                "architecture",
                "System Architecture",
                "Design system architecture, tech stack selection, and database schema",
                task_type=TaskType.RESEARCH,
                depends_on=["requirements"],
                priority=9,
                metadata={"duration_estimate": "3-5 days", "phase_type": "design"},
                tags=["architecture", "design", "tech-stack"]
            )
            .add_task(
                "frontend",
                "Frontend Development",
                "Build user interface with React/Vue, responsive design, and accessibility",
                task_type=TaskType.CODE,
                depends_on=["architecture"],
                priority=8,
                metadata={"duration_estimate": "1-2 weeks", "phase_type": "development"},
                tags=["frontend", "ui", "react"]
            )
            .add_task(
                "backend",
                "Backend Development",
                "Implement REST APIs, business logic, authentication, and database integration",
                task_type=TaskType.CODE,
                depends_on=["architecture"],
                priority=8,
                metadata={"duration_estimate": "1-2 weeks", "phase_type": "development"},
                tags=["backend", "api", "database"]
            )
            .add_task(
                "integration",
                "System Integration",
                "Integrate frontend with backend, end-to-end testing, and bug fixes",
                task_type=TaskType.TEST,
                depends_on=["frontend", "backend"],
                priority=7,
                metadata={"duration_estimate": "3-5 days", "phase_type": "integration"},
                tags=["integration", "testing", "e2e"]
            )
            .add_task(
                "deployment",
                "Production Deployment",
                "Deploy to cloud (AWS/GCP/Azure), configure CI/CD, monitoring setup",
                task_type=TaskType.DEPLOY,
                depends_on=["integration"],
                priority=10,
                metadata={"duration_estimate": "2-3 days", "phase_type": "deployment"},
                tags=["deployment", "cicd", "monitoring"]
            )
            .build()
        )

        metadata = {
            "category": "saas",
            "complexity": "moderate",
            "duration": "2-4 weeks",
            "phase_count": 6,
            "description": "Complete workflow for SaaS product development",
            "typical_use_cases": json.dumps(["web applications", "saas platforms", "dashboards"]),
            "tech_stack": json.dumps(["react", "node.js", "postgresql", "aws"]),
            "team_roles": json.dumps(["product_manager", "architect", "frontend_dev", "backend_dev", "devops"])
        }

        return dag, metadata

    async def _create_microservice_template(self) -> tuple[DAG, Dict]:
        """Create Microservice API template"""

        builder = WorkflowBuilder(
            workflow_id="template_microservice_api",
            name="Microservice API",
            description="Workflow for building RESTful microservices with containerization"
        )

        dag = (builder
            .add_task(
                "requirements",
                "API Requirements",
                "Define API contract, endpoints, request/response schemas, and documentation",
                task_type=TaskType.RESEARCH,
                priority=10,
                metadata={"duration_estimate": "1-2 days", "phase_type": "planning"},
                tags=["requirements", "api", "openapi"]
            )
            .add_task(
                "architecture",
                "Microservice Architecture",
                "Design service boundaries, data models, and communication patterns",
                task_type=TaskType.RESEARCH,
                depends_on=["requirements"],
                priority=9,
                metadata={"duration_estimate": "2-3 days", "phase_type": "design"},
                tags=["architecture", "microservices", "design"]
            )
            .add_task(
                "implementation",
                "API Implementation",
                "Implement REST endpoints, business logic, database layer, and error handling",
                task_type=TaskType.CODE,
                depends_on=["architecture"],
                priority=8,
                metadata={"duration_estimate": "5-7 days", "phase_type": "development"},
                tags=["implementation", "rest-api", "crud"]
            )
            .add_task(
                "testing",
                "API Testing",
                "Unit tests, integration tests, API testing, and load testing",
                task_type=TaskType.TEST,
                depends_on=["implementation"],
                priority=9,
                metadata={"duration_estimate": "3-4 days", "phase_type": "testing"},
                tags=["testing", "unit-tests", "integration-tests"]
            )
            .add_task(
                "deployment",
                "Container Deployment",
                "Dockerize service, deploy to Kubernetes/ECS, setup monitoring and logging",
                task_type=TaskType.DEPLOY,
                depends_on=["testing"],
                priority=10,
                metadata={"duration_estimate": "2-3 days", "phase_type": "deployment"},
                tags=["deployment", "docker", "kubernetes"]
            )
            .build()
        )

        metadata = {
            "category": "microservice",
            "complexity": "simple",
            "duration": "1-2 weeks",
            "phase_count": 5,
            "description": "Workflow for building RESTful microservices",
            "typical_use_cases": json.dumps(["rest apis", "microservices", "backend services"]),
            "tech_stack": json.dumps(["fastapi", "python", "postgresql", "docker", "kubernetes"]),
            "team_roles": json.dumps(["backend_dev", "api_designer", "qa_engineer", "devops"])
        }

        return dag, metadata

    async def _create_mobile_template(self) -> tuple[DAG, Dict]:
        """Create Mobile App template"""

        builder = WorkflowBuilder(
            workflow_id="template_mobile_app",
            name="Mobile App",
            description="Cross-platform mobile application workflow with iOS and Android"
        )

        dag = (builder
            .add_task(
                "requirements",
                "Mobile Requirements",
                "Define app requirements, user flows, and platform-specific considerations",
                task_type=TaskType.RESEARCH,
                priority=10,
                metadata={"duration_estimate": "2-3 days", "phase_type": "planning"},
                tags=["requirements", "mobile", "user-flows"]
            )
            .add_task(
                "design",
                "UI/UX Design",
                "Create wireframes, mockups, design system, and interactive prototypes",
                task_type=TaskType.RESEARCH,
                depends_on=["requirements"],
                priority=9,
                metadata={"duration_estimate": "1 week", "phase_type": "design"},
                tags=["design", "ui-ux", "prototypes"]
            )
            .add_task(
                "ios",
                "iOS Development",
                "Build iOS app with Swift/SwiftUI, implement features, and native integrations",
                task_type=TaskType.CODE,
                depends_on=["design"],
                priority=8,
                metadata={"duration_estimate": "2 weeks", "phase_type": "development"},
                tags=["ios", "swift", "mobile"]
            )
            .add_task(
                "android",
                "Android Development",
                "Build Android app with Kotlin, implement features, and native integrations",
                task_type=TaskType.CODE,
                depends_on=["design"],
                priority=8,
                metadata={"duration_estimate": "2 weeks", "phase_type": "development"},
                tags=["android", "kotlin", "mobile"]
            )
            .add_task(
                "backend",
                "Backend API",
                "Develop backend API for mobile app, push notifications, and data sync",
                task_type=TaskType.CODE,
                depends_on=["design"],
                priority=8,
                metadata={"duration_estimate": "1-2 weeks", "phase_type": "development"},
                tags=["backend", "api", "sync"]
            )
            .add_task(
                "testing",
                "Mobile Testing",
                "Cross-platform testing, device testing, performance testing, and bug fixes",
                task_type=TaskType.TEST,
                depends_on=["ios", "android", "backend"],
                priority=9,
                metadata={"duration_estimate": "1 week", "phase_type": "testing"},
                tags=["testing", "qa", "devices"]
            )
            .add_task(
                "deployment",
                "App Store Deployment",
                "Prepare app store submissions, deploy to iOS App Store and Google Play Store",
                task_type=TaskType.DEPLOY,
                depends_on=["testing"],
                priority=10,
                metadata={"duration_estimate": "3-5 days", "phase_type": "deployment"},
                tags=["deployment", "app-store", "play-store"]
            )
            .build()
        )

        metadata = {
            "category": "mobile",
            "complexity": "complex",
            "duration": "3-6 weeks",
            "phase_count": 7,
            "description": "Cross-platform mobile application workflow",
            "typical_use_cases": json.dumps(["mobile apps", "ios apps", "android apps"]),
            "tech_stack": json.dumps(["swift", "kotlin", "react-native", "firebase"]),
            "team_roles": json.dumps(["product_manager", "ui_designer", "ios_dev", "android_dev", "backend_dev", "qa_engineer"])
        }

        return dag, metadata

    async def _create_enterprise_template(self) -> tuple[DAG, Dict]:
        """Create Enterprise System template"""

        builder = WorkflowBuilder(
            workflow_id="template_enterprise_system",
            name="Enterprise System",
            description="Large-scale enterprise application with compliance and security requirements"
        )

        dag = (builder
            .add_task(
                "requirements",
                "Requirements & Compliance",
                "Gather requirements, compliance requirements (GDPR, HIPAA), and stakeholder analysis",
                task_type=TaskType.RESEARCH,
                priority=10,
                metadata={"duration_estimate": "1 week", "phase_type": "planning"},
                tags=["requirements", "compliance", "enterprise"]
            )
            .add_task(
                "architecture",
                "Enterprise Architecture",
                "Design scalable architecture, security model, data governance, and integration patterns",
                task_type=TaskType.RESEARCH,
                depends_on=["requirements"],
                priority=10,
                metadata={"duration_estimate": "1-2 weeks", "phase_type": "design"},
                tags=["architecture", "security", "scalability"]
            )
            .add_task(
                "design",
                "System Design",
                "Create detailed design specifications, UI/UX design system, and accessibility guidelines",
                task_type=TaskType.RESEARCH,
                depends_on=["architecture"],
                priority=9,
                metadata={"duration_estimate": "1 week", "phase_type": "design"},
                tags=["design", "ui-ux", "accessibility"]
            )
            .add_task(
                "development",
                "System Development",
                "Implement core system features, business logic, integrations, and data layers",
                task_type=TaskType.CODE,
                depends_on=["design"],
                priority=8,
                metadata={"duration_estimate": "3-4 weeks", "phase_type": "development"},
                tags=["development", "enterprise", "implementation"]
            )
            .add_task(
                "integration",
                "Legacy Integration",
                "Integrate with legacy systems, third-party services, and data migration",
                task_type=TaskType.CODE,
                depends_on=["development"],
                priority=8,
                metadata={"duration_estimate": "1-2 weeks", "phase_type": "integration"},
                tags=["integration", "legacy", "migration"]
            )
            .add_task(
                "security",
                "Security & Audit",
                "Security testing, penetration testing, compliance audit, and vulnerability assessment",
                task_type=TaskType.TEST,
                depends_on=["integration"],
                priority=10,
                metadata={"duration_estimate": "1 week", "phase_type": "security"},
                tags=["security", "audit", "compliance"]
            )
            .add_task(
                "testing",
                "Comprehensive Testing",
                "System testing, UAT, performance testing, load testing, and disaster recovery testing",
                task_type=TaskType.TEST,
                depends_on=["security"],
                priority=9,
                metadata={"duration_estimate": "1-2 weeks", "phase_type": "testing"},
                tags=["testing", "uat", "performance"]
            )
            .add_task(
                "deployment",
                "Production Deployment",
                "Staged rollout, monitoring setup, backup systems, and documentation",
                task_type=TaskType.DEPLOY,
                depends_on=["testing"],
                priority=10,
                metadata={"duration_estimate": "1 week", "phase_type": "deployment"},
                tags=["deployment", "monitoring", "documentation"]
            )
            .build()
        )

        metadata = {
            "category": "enterprise",
            "complexity": "enterprise",
            "duration": "8-12 weeks",
            "phase_count": 8,
            "description": "Large-scale enterprise application with compliance",
            "typical_use_cases": json.dumps(["enterprise systems", "erp", "crm", "healthcare", "finance"]),
            "tech_stack": json.dumps(["java", "spring", "oracle", "kubernetes", "terraform"]),
            "team_roles": json.dumps(["business_analyst", "architect", "security_engineer", "dev_team", "qa_team", "devops_team"])
        }

        return dag, metadata


# ========================================================================
# UTILITY FUNCTIONS
# ========================================================================

async def initialize_dag_catalog():
    """Initialize DAG catalog with templates (run once on startup)"""
    service = DAGCatalogService()
    await service.initialize_templates()
    await service.disconnect()


if __name__ == "__main__":
    import asyncio

    # Initialize templates
    asyncio.run(initialize_dag_catalog())

    print("\n✅ DAG Catalog initialized successfully!")
    print("Templates available:")
    print("  1. SaaS Application (6 phases, 2-4 weeks)")
    print("  2. Microservice API (5 phases, 1-2 weeks)")
    print("  3. Mobile App (7 phases, 3-6 weeks)")
    print("  4. Enterprise System (8 phases, 8-12 weeks)")
