"""
MAESTRO Enterprise Template Repository Manager
Version: 1.0
Purpose: Core template management with AI-powered intelligence and enterprise features
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import aiofiles
import asyncpg

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TemplateStatus(Enum):
    """Template approval status"""

    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    DEPRECATED = "deprecated"


class ComplexityLevel(Enum):
    """Template complexity levels"""

    SIMPLE = "simple"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class StorageTier(Enum):
    """Storage tier for performance optimization"""

    HOT = 1  # Frequently used, in-memory cache
    WARM = 2  # Moderately used, file system
    COLD = 3  # Rarely used, cloud storage


@dataclass
class TemplateMetadata:
    """Comprehensive template metadata"""

    name: str
    category: str
    language: str
    description: str
    file_path: str
    created_by: str
    version: str = "1.0.0"
    framework: Optional[str] = None
    domain: Optional[str] = None
    pattern: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    complexity: ComplexityLevel = ComplexityLevel.INTERMEDIATE
    status: TemplateStatus = TemplateStatus.DRAFT
    organization: Optional[str] = None

    # Quality metrics
    quality_score: float = 0.0
    security_score: int = 0
    performance_score: int = 0
    maintainability_score: int = 0
    test_coverage: float = 0.0

    # Usage metrics
    usage_count: int = 0
    success_rate: float = 0.0
    popularity: str = "cold"
    maturity: str = "experimental"

    # System fields
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    vector_id: Optional[str] = None
    storage_tier: StorageTier = StorageTier.WARM

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "language": self.language,
            "framework": self.framework,
            "domain": self.domain,
            "pattern": self.pattern,
            "version": self.version,
            "description": self.description,
            "tags": self.tags,
            "complexity": self.complexity.value,
            "status": self.status.value,
            "quality_score": self.quality_score,
            "security_score": self.security_score,
            "performance_score": self.performance_score,
            "maintainability_score": self.maintainability_score,
            "test_coverage": self.test_coverage,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "popularity": self.popularity,
            "maturity": self.maturity,
            "file_path": self.file_path,
            "created_by": self.created_by,
            "organization": self.organization,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "vector_id": self.vector_id,
            "storage_tier": self.storage_tier.value,
        }


@dataclass
class TemplateSearchQuery:
    """Advanced template search parameters"""

    query: Optional[str] = None
    language: Optional[List[str]] = None
    framework: Optional[List[str]] = None
    domain: Optional[List[str]] = None
    category: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    quality_min: float = 0.0
    complexity: Optional[List[ComplexityLevel]] = None
    status: Optional[List[TemplateStatus]] = None
    semantic_search: bool = True
    limit: int = 10
    offset: int = 0


class EnterpriseTemplateRepository:
    """
    Enterprise-grade template repository with AI intelligence

    Features:
    - Multi-tier storage (Hot/Warm/Cold)
    - Quality analysis integration
    - Semantic search with ChromaDB
    - Usage analytics and recommendations
    - Enterprise security and governance
    """

    def __init__(
        self,
        repository_path: str = "/data/maestro-v1/enterprise_template_repository",
        db_url: str = "postgresql://postgres:postgres@localhost:5433/maestro_personas",
    ):
        self.repository_path = Path(repository_path)
        self.templates_path = self.repository_path / "maestro_templates"
        self.db_url = db_url
        self.db_pool: Optional[asyncpg.Pool] = None

        # Ensure repository structure exists
        self.templates_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"✅ Enterprise Template Repository initialized at {repository_path}")

    async def initialize(self):
        """Initialize database connections and repository structure"""
        try:
            # Initialize database connection pool
            self.db_pool = await asyncpg.create_pool(
                self.db_url, min_size=5, max_size=20, command_timeout=60
            )

            # Create database schema if not exists
            await self._ensure_database_schema()

            logger.info("✅ Enterprise Template Repository fully initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize repository: {e}")
            raise

    async def _ensure_database_schema(self):
        """Ensure database schema exists"""
        schema_path = self.repository_path / "schema.sql"
        if schema_path.exists():
            async with self.db_pool.acquire() as conn:
                async with aiofiles.open(schema_path, "r") as f:
                    schema_sql = await f.read()
                    try:
                        await conn.execute(schema_sql)
                        logger.info("✅ Database schema validated")
                    except Exception as e:
                        if "already exists" in str(e).lower():
                            logger.info("✅ Database schema already exists")
                        else:
                            logger.warning(f"⚠️ Schema validation warning: {e}")

    async def create_template(
        self,
        content: str,
        metadata: TemplateMetadata,
        test_content: Optional[str] = None,
        examples: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Create a new template with comprehensive metadata and quality analysis

        Args:
            content: Template source code
            metadata: Template metadata
            test_content: Optional test file content
            examples: Optional usage examples

        Returns:
            Template ID
        """
        try:
            # Generate content hash for version control
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            # Create template directory structure
            template_dir = self._get_template_path(metadata)
            version_dir = template_dir / f"v{metadata.version}"
            version_dir.mkdir(parents=True, exist_ok=True)

            # Save template files
            await self._save_template_files(version_dir, content, metadata, test_content, examples)

            # Store metadata in database
            await self._store_template_metadata(metadata, content_hash)

            # Create version record
            await self._create_version_record(metadata.id, metadata.version, content_hash)

            # Create latest symlink
            await self._update_latest_symlink(template_dir, f"v{metadata.version}")

            # Trigger quality analysis (async)
            asyncio.create_task(self._analyze_template_quality(metadata.id, content))

            # Log creation in audit trail
            await self._log_audit_event(
                metadata.id,
                "create",
                metadata.created_by,
                {
                    "template_name": metadata.name,
                    "version": metadata.version,
                    "language": metadata.language,
                },
            )

            logger.info(f"✅ Template created: {metadata.name} v{metadata.version} [{metadata.id}]")
            return metadata.id

        except Exception as e:
            logger.error(f"❌ Failed to create template: {e}")
            raise

    async def search_templates(self, search_query: TemplateSearchQuery) -> List[Dict[str, Any]]:
        """
        Advanced template search with semantic and metadata filtering

        Args:
            search_query: Search parameters

        Returns:
            List of matching templates with metadata
        """
        try:
            # Build SQL query with filters
            sql_parts = ["SELECT * FROM templates WHERE 1=1"]
            params = []
            param_count = 0

            # Language filter
            if search_query.language:
                param_count += 1
                sql_parts.append(f"AND language = ANY(${param_count})")
                params.append(search_query.language)

            # Framework filter
            if search_query.framework:
                param_count += 1
                sql_parts.append(f"AND framework = ANY(${param_count})")
                params.append(search_query.framework)

            # Domain filter
            if search_query.domain:
                param_count += 1
                sql_parts.append(f"AND domain = ANY(${param_count})")
                params.append(search_query.domain)

            # Category filter
            if search_query.category:
                param_count += 1
                sql_parts.append(f"AND category = ANY(${param_count})")
                params.append(search_query.category)

            # Quality filter
            if search_query.quality_min > 0:
                param_count += 1
                sql_parts.append(f"AND quality_score >= ${param_count}")
                params.append(search_query.quality_min)

            # Status filter (default to approved)
            status_filter = search_query.status or [TemplateStatus.APPROVED]
            param_count += 1
            sql_parts.append(f"AND status = ANY(${param_count})")
            params.append([s.value for s in status_filter])

            # Text search
            if search_query.query:
                param_count += 1
                sql_parts.append(
                    f"AND (name ILIKE ${param_count} OR description ILIKE ${param_count})"
                )
                search_pattern = f"%{search_query.query}%"
                params.extend([search_pattern, search_pattern])
                param_count += 1

            # Ordering and pagination
            sql_parts.extend(
                [
                    "ORDER BY quality_score DESC, usage_count DESC, created_at DESC",
                    f"LIMIT {search_query.limit} OFFSET {search_query.offset}",
                ]
            )

            query_sql = " ".join(sql_parts)

            # Execute query
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(query_sql, *params)

            templates = []
            for row in rows:
                template_dict = dict(row)
                # Convert timestamps to ISO format
                for date_field in ["created_at", "updated_at", "approved_at", "last_accessed_at"]:
                    if template_dict.get(date_field):
                        template_dict[date_field] = template_dict[date_field].isoformat()

                templates.append(template_dict)

            logger.info(
                f"🔍 Found {len(templates)} templates for query: {search_query.query or 'filtered search'}"
            )
            return templates

        except Exception as e:
            logger.error(f"❌ Template search failed: {e}")
            raise

    async def get_template(
        self, template_id: str, version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get template with content and metadata

        Args:
            template_id: Template UUID
            version: Specific version (defaults to latest)

        Returns:
            Template data with content, or None if not found
        """
        try:
            # Get template metadata
            async with self.db_pool.acquire() as conn:
                template_row = await conn.fetchrow(
                    "SELECT * FROM templates WHERE id = $1", template_id
                )

            if not template_row:
                return None

            template_data = dict(template_row)

            # Convert timestamps
            for date_field in ["created_at", "updated_at", "approved_at", "last_accessed_at"]:
                if template_data.get(date_field):
                    template_data[date_field] = template_data[date_field].isoformat()

            # Load template content
            version_to_load = version or await self._get_latest_version(template_id)
            if version_to_load:
                content = await self._load_template_content(template_data, version_to_load)
                template_data.update(content)

            # Track access
            await self._track_template_access(template_id)

            return template_data

        except Exception as e:
            logger.error(f"❌ Failed to get template {template_id}: {e}")
            return None

    async def update_template_quality_metrics(
        self,
        template_id: str,
        quality_score: float,
        security_score: int,
        performance_score: int,
        maintainability_score: int,
        test_coverage: float,
    ):
        """Update template quality metrics from analysis"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE templates
                    SET quality_score = $2,
                        security_score = $3,
                        performance_score = $4,
                        maintainability_score = $5,
                        test_coverage = $6,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $1
                """,
                    template_id,
                    quality_score,
                    security_score,
                    performance_score,
                    maintainability_score,
                    test_coverage,
                )

            logger.info(
                f"✅ Updated quality metrics for template {template_id}: Q={quality_score:.1f}"
            )

        except Exception as e:
            logger.error(f"❌ Failed to update quality metrics: {e}")

    async def track_template_usage(
        self,
        template_id: str,
        session_id: str,
        success: bool,
        feedback_score: Optional[int] = None,
        modifications_made: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Track template usage for analytics"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO template_usage
                    (template_id, session_id, success, feedback_score, modifications_made,
                     user_id, organization, project_type, generation_time_ms)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                    template_id,
                    session_id,
                    success,
                    feedback_score,
                    modifications_made,
                    context.get("user_id") if context else None,
                    context.get("organization") if context else None,
                    context.get("project_type") if context else None,
                    context.get("generation_time_ms") if context else None,
                )

            logger.info(
                f"📊 Tracked usage for template {template_id}: {'success' if success else 'failure'}"
            )

        except Exception as e:
            logger.error(f"❌ Failed to track usage: {e}")

    async def get_template_analytics(self, template_id: str) -> Dict[str, Any]:
        """Get comprehensive analytics for a template"""
        try:
            async with self.db_pool.acquire() as conn:
                # Basic metrics
                template_info = await conn.fetchrow(
                    "SELECT name, usage_count, success_rate, quality_score FROM templates WHERE id = $1",
                    template_id,
                )

                # Usage statistics
                usage_stats = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as total_uses,
                        AVG(CASE WHEN feedback_score IS NOT NULL THEN feedback_score END) as avg_feedback,
                        AVG(CASE WHEN satisfaction_score IS NOT NULL THEN satisfaction_score END) as avg_satisfaction,
                        COUNT(CASE WHEN success = TRUE THEN 1 END)::float / COUNT(*) * 100 as success_percentage
                    FROM template_usage
                    WHERE template_id = $1
                """,
                    template_id,
                )

                # Recent usage trend (last 30 days)
                usage_trend = await conn.fetch(
                    """
                    SELECT
                        DATE(used_at) as date,
                        COUNT(*) as daily_usage
                    FROM template_usage
                    WHERE template_id = $1 AND used_at > CURRENT_DATE - INTERVAL '30 days'
                    GROUP BY DATE(used_at)
                    ORDER BY date DESC
                    LIMIT 30
                """,
                    template_id,
                )

            analytics = {
                "template": dict(template_info) if template_info else None,
                "usage_statistics": dict(usage_stats) if usage_stats else None,
                "usage_trend": [dict(row) for row in usage_trend],
                "generated_at": datetime.now().isoformat(),
            }

            return analytics

        except Exception as e:
            logger.error(f"❌ Failed to get analytics for {template_id}: {e}")
            return {}

    def _get_template_path(self, metadata: TemplateMetadata) -> Path:
        """Generate template storage path based on classification"""
        path_parts = []

        # Primary classification
        if metadata.language:
            path_parts.extend(["languages", metadata.language])
        elif metadata.framework:
            path_parts.extend(["frameworks", metadata.framework])
        elif metadata.pattern:
            path_parts.extend(["patterns", metadata.pattern])
        elif metadata.domain:
            path_parts.extend(["domains", metadata.domain])
        else:
            path_parts.extend(["general", metadata.category])

        # Add template name
        path_parts.append(metadata.name.lower().replace(" ", "-"))

        return self.templates_path / Path(*path_parts)

    async def _save_template_files(
        self,
        version_dir: Path,
        content: str,
        metadata: TemplateMetadata,
        test_content: Optional[str],
        examples: Optional[Dict[str, str]],
    ):
        """Save template files to storage"""
        # Main template file
        template_ext = self._get_file_extension(metadata.language)
        template_file = version_dir / f"template{template_ext}"
        async with aiofiles.open(template_file, "w") as f:
            await f.write(content)

        # Metadata file
        metadata_file = version_dir / "metadata.json"
        async with aiofiles.open(metadata_file, "w") as f:
            await f.write(json.dumps(metadata.to_dict(), indent=2))

        # Test file
        if test_content:
            test_ext = (
                ".spec" + template_ext
                if metadata.language == "javascript"
                else ".test" + template_ext
            )
            test_file = version_dir / f"test{test_ext}"
            async with aiofiles.open(test_file, "w") as f:
                await f.write(test_content)

        # Examples
        if examples:
            examples_dir = version_dir / "usage_examples"
            examples_dir.mkdir(exist_ok=True)
            for example_name, example_content in examples.items():
                example_file = examples_dir / f"{example_name}{template_ext}"
                async with aiofiles.open(example_file, "w") as f:
                    await f.write(example_content)

    def _get_file_extension(self, language: str) -> str:
        """Get appropriate file extension for language"""
        extensions = {
            "typescript": ".ts",
            "javascript": ".js",
            "python": ".py",
            "java": ".java",
            "go": ".go",
            "rust": ".rs",
            "cpp": ".cpp",
            "csharp": ".cs",
        }
        return extensions.get(language.lower(), ".txt")

    async def _store_template_metadata(self, metadata: TemplateMetadata, content_hash: str):
        """Store template metadata in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO templates (
                    id, name, category, language, framework, domain, pattern, version,
                    description, tags, complexity_level, status, quality_score,
                    security_score, performance_score, maintainability_score, test_coverage,
                    file_path, created_by, organization, storage_tier
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
                )
            """,
                metadata.id,
                metadata.name,
                metadata.category,
                metadata.language,
                metadata.framework,
                metadata.domain,
                metadata.pattern,
                metadata.version,
                metadata.description,
                metadata.tags,
                metadata.complexity.value,
                metadata.status.value,
                metadata.quality_score,
                metadata.security_score,
                metadata.performance_score,
                metadata.maintainability_score,
                metadata.test_coverage,
                metadata.file_path,
                metadata.created_by,
                metadata.organization,
                metadata.storage_tier.value,
            )

    async def _create_version_record(self, template_id: str, version: str, content_hash: str):
        """Create version record for template"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO template_versions (template_id, version, content_hash)
                VALUES ($1, $2, $3)
            """,
                template_id,
                version,
                content_hash,
            )

    async def _update_latest_symlink(self, template_dir: Path, version_dir_name: str):
        """Update latest symlink to point to current version"""
        latest_link = template_dir / "latest"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(version_dir_name)

    async def _analyze_template_quality(self, template_id: str, content: str):
        """Analyze template quality (placeholder for integration with existing tools)"""
        # This would integrate with existing quality analysis pipeline
        # For now, provide basic metrics
        quality_score = min(100.0, len(content.split("\n")) * 2.5)  # Placeholder
        security_score = 85  # Placeholder
        performance_score = 90  # Placeholder
        maintainability_score = 88  # Placeholder
        test_coverage = 75.0  # Placeholder

        await self.update_template_quality_metrics(
            template_id,
            quality_score,
            security_score,
            performance_score,
            maintainability_score,
            test_coverage,
        )

    async def _log_audit_event(
        self, template_id: str, action: str, actor_id: str, details: Dict[str, Any]
    ):
        """Log audit event"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO template_audit_log (template_id, action, actor_id, details)
                VALUES ($1, $2, $3, $4)
            """,
                template_id,
                action,
                actor_id,
                json.dumps(details),
            )

    async def _get_latest_version(self, template_id: str) -> Optional[str]:
        """Get latest version for template"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT version FROM templates WHERE id = $1", template_id)
            return row["version"] if row else None

    async def _load_template_content(
        self, template_data: Dict[str, Any], version: str
    ) -> Dict[str, Any]:
        """Load template content from file system"""
        # This would load the actual template files
        # For now, return placeholder content
        return {
            "content": f"// Template: {template_data['name']} v{version}\n// Generated by MAESTRO",
            "test_content": f"// Test for {template_data['name']}",
            "examples": {"basic": f"// Basic usage of {template_data['name']}"},
        }

    async def _track_template_access(self, template_id: str):
        """Track template access for analytics"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE templates
                SET last_accessed_at = CURRENT_TIMESTAMP,
                    access_frequency = access_frequency + 1
                WHERE id = $1
            """,
                template_id,
            )

    async def close(self):
        """Clean up resources"""
        if self.db_pool:
            await self.db_pool.close()
        logger.info("✅ Enterprise Template Repository closed")


# Example usage and testing
async def main():
    """Example usage of the Enterprise Template Repository"""

    repo = EnterpriseTemplateRepository()
    await repo.initialize()

    # Create sample template
    metadata = TemplateMetadata(
        name="User Authentication Component",
        category="components",
        language="typescript",
        framework="react",
        domain="auth",
        description="Reusable user authentication component with JWT support",
        created_by="MAESTRO",
        tags=["react", "auth", "jwt", "typescript"],
        complexity=ComplexityLevel.INTERMEDIATE,
        organization="MAESTRO",
    )

    sample_content = """
import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';

interface LoginFormProps {
    onSuccess?: () => void;
    className?: string;
}

export const LoginForm: React.FC<LoginFormProps> = ({ onSuccess, className }) => {
    const [credentials, setCredentials] = useState({ username: '', password: '' });
    const { login, isLoading } = useAuth();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await login(credentials);
            onSuccess?.();
        } catch (error) {
            console.error('Login failed:', error);
        }
    };

    return (
        <form onSubmit={handleSubmit} className={className}>
            <input
                type="text"
                value={credentials.username}
                onChange={(e) => setCredentials(prev => ({ ...prev, username: e.target.value }))}
                placeholder="Username"
                required
            />
            <input
                type="password"
                value={credentials.password}
                onChange={(e) => setCredentials(prev => ({ ...prev, password: e.target.value }))}
                placeholder="Password"
                required
            />
            <button type="submit" disabled={isLoading}>
                {isLoading ? 'Logging in...' : 'Login'}
            </button>
        </form>
    );
};
"""

    # Create template
    template_id = await repo.create_template(sample_content, metadata)
    print(f"✅ Created template: {template_id}")

    # Search templates
    search_query = TemplateSearchQuery(
        language=["typescript"], framework=["react"], domain=["auth"]
    )

    results = await repo.search_templates(search_query)
    print(f"🔍 Found {len(results)} templates")

    # Get template
    template = await repo.get_template(template_id)
    if template:
        print(f"📄 Retrieved template: {template['name']}")

    # Track usage
    await repo.track_template_usage(
        template_id,
        "session123",
        True,
        4,
        context={"user_id": "user123", "project_type": "web_app", "generation_time_ms": 150},
    )

    # Get analytics
    analytics = await repo.get_template_analytics(template_id)
    print(f"📊 Analytics: {analytics}")

    await repo.close()


if __name__ == "__main__":
    asyncio.run(main())
