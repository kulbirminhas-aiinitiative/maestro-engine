#!/usr/bin/env python3
"""
Template Versions & Recommendation Service for MAESTRO Engine
Implements Epic MD-1831: [MT-400] Template Versions & Recommendation APIs

This service provides:
- Version history API with changelog
- Intelligent recommendation engine using QF scores and Engine success metrics
- Context-aware template suggestions based on persona, tags, and scores
- Usage statistics tracking

Acceptance Criteria:
- AC-1: Versions API returns array with version, changes, date
- AC-2: Recommend API accepts persona, tag, min_score params
- AC-3: Recommendations ranked by composite score
- AC-4: Response includes usage_stats and citations
- AC-5: Pagination support for large result sets

Feature Flag: FF_TEMPLATE_VERSIONS_ENABLED
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Try to import Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, Gauge

    VERSION_OPERATIONS = Counter(
        "maestro_template_version_ops_total",
        "Total template version operations",
        ["operation", "status"]
    )
    RECOMMENDATION_OPERATIONS = Counter(
        "maestro_template_recommendation_ops_total",
        "Total recommendation operations",
        ["persona", "status"]
    )
    RECOMMENDATION_LATENCY = Histogram(
        "maestro_template_recommendation_latency_seconds",
        "Recommendation API latency",
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0]
    )
    TEMPLATE_USAGE_GAUGE = Gauge(
        "maestro_template_usage_total",
        "Template usage count",
        ["template_id"]
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

    class StubMetric:
        def inc(self): pass
        def observe(self, value): pass
        def labels(self, **kwargs): return self
        def set(self, value): pass

    VERSION_OPERATIONS = StubMetric()
    RECOMMENDATION_OPERATIONS = StubMetric()
    RECOMMENDATION_LATENCY = StubMetric()
    TEMPLATE_USAGE_GAUGE = StubMetric()

logger = logging.getLogger("template_versions_service")


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class VersionChangeType(str, Enum):
    """Type of version change."""
    MAJOR = "major"       # Breaking changes
    MINOR = "minor"       # New features, backward compatible
    PATCH = "patch"       # Bug fixes, small improvements
    INITIAL = "initial"   # First version


class RecommendationStrategy(str, Enum):
    """Strategy for ranking recommendations."""
    COMPOSITE = "composite"       # Balanced QF + success rate
    QUALITY_FIRST = "quality_first"  # Prioritize QF scores
    USAGE_FIRST = "usage_first"      # Prioritize success rate
    RECENT_FIRST = "recent_first"    # Prioritize recently updated


# Default weights for composite scoring
DEFAULT_SCORING_WEIGHTS = {
    "quality_score": 0.35,       # QF validation score
    "success_rate": 0.30,        # Engine execution success rate
    "usage_count": 0.15,         # How often template is used
    "recency": 0.10,             # How recently updated
    "match_score": 0.10,         # How well it matches filters
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class TemplateVersion:
    """Represents a single version of a template."""
    version: str                           # Semantic version (e.g., "1.2.3")
    template_id: str
    created_at: datetime
    created_by: str
    change_type: VersionChangeType
    changes: List[str]                     # List of change descriptions
    changelog: str                         # Full changelog entry
    parent_version: Optional[str] = None   # Previous version
    commit_hash: Optional[str] = None      # Git commit if available
    validation_report_id: Optional[str] = None
    quality_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "template_id": self.template_id,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "change_type": self.change_type.value,
            "changes": self.changes,
            "changelog": self.changelog,
            "parent_version": self.parent_version,
            "commit_hash": self.commit_hash,
            "validation_report_id": self.validation_report_id,
            "quality_score": self.quality_score,
            "metadata": self.metadata,
        }


@dataclass
class UsageStats:
    """Template usage statistics."""
    template_id: str
    applied_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    avg_quality_score: float = 0.0
    last_used_at: Optional[datetime] = None
    unique_users: int = 0
    unique_projects: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "applied_count": self.applied_count,
            "success_rate": round(self.success_rate, 3),
            "avg_quality_score": round(self.avg_quality_score, 2),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "unique_users": self.unique_users,
            "unique_projects": self.unique_projects,
        }


@dataclass
class TemplateRecommendation:
    """A single template recommendation."""
    template_id: str
    template_name: str
    version: str
    score: float                          # Composite recommendation score
    quality_score: float                  # QF validation score
    usage_stats: UsageStats
    citations: List[str]                  # References to golden projects
    match_reasons: List[str]              # Why this was recommended
    persona_match: bool = False
    tag_match: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_name": self.template_name,
            "version": self.version,
            "score": round(self.score, 2),
            "quality_score": round(self.quality_score, 2),
            "usage_stats": self.usage_stats.to_dict(),
            "citations": self.citations,
            "match_reasons": self.match_reasons,
            "persona_match": self.persona_match,
            "tag_match": self.tag_match,
            "metadata": self.metadata,
        }


@dataclass
class RecommendationRequest:
    """Request parameters for template recommendations."""
    persona: Optional[str] = None
    tags: Optional[List[str]] = None
    min_score: Optional[float] = None
    language: Optional[str] = None
    framework: Optional[str] = None
    category: Optional[str] = None
    limit: int = 10
    offset: int = 0
    strategy: RecommendationStrategy = RecommendationStrategy.COMPOSITE
    include_usage_stats: bool = True
    include_citations: bool = True


@dataclass
class RecommendationResponse:
    """Response containing recommendations."""
    recommendations: List[TemplateRecommendation]
    total: int
    page: int
    page_size: int
    has_more: bool
    filters_applied: Dict[str, Any]
    strategy_used: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendations": [r.to_dict() for r in self.recommendations],
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "has_more": self.has_more,
            "filters_applied": self.filters_applied,
            "strategy_used": self.strategy_used,
        }


# ============================================================================
# SERVICE IMPLEMENTATION
# ============================================================================

class TemplateVersionsService:
    """
    Template Versions & Recommendation Service

    Provides version history management and intelligent recommendation
    based on QF scores, Engine success metrics, and user context.
    """

    def __init__(
        self,
        feature_flag_enabled: bool = True,
        scoring_weights: Optional[Dict[str, float]] = None,
    ):
        self.feature_flag_enabled = feature_flag_enabled
        self.scoring_weights = scoring_weights or DEFAULT_SCORING_WEIGHTS

        # In-memory storage (would be database in production)
        self._versions: Dict[str, List[TemplateVersion]] = {}
        self._usage_stats: Dict[str, UsageStats] = {}
        self._templates: Dict[str, Dict[str, Any]] = {}
        self._citations: Dict[str, List[str]] = {}

        # Initialize with sample data for testing
        self._initialize_sample_data()

        logger.info("TemplateVersionsService initialized")

    def _initialize_sample_data(self):
        """Initialize sample data for testing."""
        sample_templates = [
            {
                "id": "api_auth_v3",
                "name": "API Authentication Template",
                "category": "api",
                "language": "python",
                "framework": "fastapi",
                "personas": ["backend_developer", "security_specialist"],
                "tags": ["auth", "security", "jwt", "oauth"],
                "quality_score": 92.5,
            },
            {
                "id": "web_dashboard_v2",
                "name": "Web Dashboard Template",
                "category": "web",
                "language": "typescript",
                "framework": "react",
                "personas": ["frontend_developer", "ui_ux_designer"],
                "tags": ["dashboard", "analytics", "charts"],
                "quality_score": 88.0,
            },
            {
                "id": "microservice_base_v1",
                "name": "Microservice Base Template",
                "category": "backend",
                "language": "python",
                "framework": "fastapi",
                "personas": ["backend_developer", "devops_engineer"],
                "tags": ["microservice", "docker", "kubernetes"],
                "quality_score": 95.0,
            },
            {
                "id": "test_suite_v2",
                "name": "Comprehensive Test Suite Template",
                "category": "testing",
                "language": "python",
                "framework": "pytest",
                "personas": ["qa_engineer", "test_engineer"],
                "tags": ["testing", "pytest", "e2e", "unit"],
                "quality_score": 90.0,
            },
            {
                "id": "cicd_pipeline_v3",
                "name": "CI/CD Pipeline Template",
                "category": "devops",
                "language": "yaml",
                "framework": "github-actions",
                "personas": ["devops_engineer", "deployment_specialist"],
                "tags": ["cicd", "automation", "deployment"],
                "quality_score": 87.5,
            },
        ]

        for tmpl in sample_templates:
            self._templates[tmpl["id"]] = tmpl

            # Add version history
            self._versions[tmpl["id"]] = [
                TemplateVersion(
                    version="1.0.0",
                    template_id=tmpl["id"],
                    created_at=datetime(2025, 10, 1),
                    created_by="system",
                    change_type=VersionChangeType.INITIAL,
                    changes=["Initial release"],
                    changelog="Initial release of template",
                    quality_score=tmpl["quality_score"] - 5,
                ),
                TemplateVersion(
                    version="1.1.0",
                    template_id=tmpl["id"],
                    created_at=datetime(2025, 11, 1),
                    created_by="ai-agent",
                    change_type=VersionChangeType.MINOR,
                    changes=["Added new features", "Improved documentation"],
                    changelog="Added new features and improved documentation",
                    parent_version="1.0.0",
                    quality_score=tmpl["quality_score"],
                ),
            ]

            # Add usage stats
            self._usage_stats[tmpl["id"]] = UsageStats(
                template_id=tmpl["id"],
                applied_count=50 + hash(tmpl["id"]) % 100,
                success_count=45 + hash(tmpl["id"]) % 50,
                success_rate=0.85 + (hash(tmpl["id"]) % 15) / 100,
                avg_quality_score=tmpl["quality_score"],
                last_used_at=datetime.now(),
                unique_users=10 + hash(tmpl["id"]) % 20,
                unique_projects=5 + hash(tmpl["id"]) % 10,
            )

            # Add citations
            self._citations[tmpl["id"]] = [
                f"golden-projects/{tmpl['category']}-reference",
                f"successful-runs/run-{hash(tmpl['id']) % 1000}",
            ]

    # ========================================================================
    # VERSION HISTORY API
    # ========================================================================

    def get_template_versions(
        self,
        template_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[TemplateVersion], int]:
        """
        Get version history for a template.

        AC-1: Returns array with version, changes, date

        Args:
            template_id: Template ID
            limit: Maximum versions to return
            offset: Offset for pagination

        Returns:
            Tuple of (versions list, total count)
        """
        start_time = time.time()

        try:
            versions = self._versions.get(template_id, [])
            total = len(versions)

            # Sort by version (newest first)
            sorted_versions = sorted(
                versions,
                key=lambda v: self._parse_version(v.version),
                reverse=True
            )

            # Apply pagination
            paginated = sorted_versions[offset:offset + limit]

            VERSION_OPERATIONS.labels(operation="get_versions", status="success").inc()

            logger.info(f"Retrieved {len(paginated)} versions for template {template_id}")
            return paginated, total

        except Exception as e:
            VERSION_OPERATIONS.labels(operation="get_versions", status="error").inc()
            logger.error(f"Error getting versions for {template_id}: {e}")
            return [], 0

    def get_version_details(
        self,
        template_id: str,
        version: str,
    ) -> Optional[TemplateVersion]:
        """Get details for a specific version."""
        versions = self._versions.get(template_id, [])
        for v in versions:
            if v.version == version:
                return v
        return None

    def create_version(
        self,
        template_id: str,
        version: str,
        changes: List[str],
        changelog: str,
        created_by: str,
        change_type: VersionChangeType = VersionChangeType.MINOR,
        commit_hash: Optional[str] = None,
        validation_report_id: Optional[str] = None,
        quality_score: Optional[float] = None,
    ) -> TemplateVersion:
        """
        Create a new version for a template.

        Args:
            template_id: Template ID
            version: Semantic version string
            changes: List of change descriptions
            changelog: Full changelog entry
            created_by: User/agent creating the version
            change_type: Type of version change
            commit_hash: Git commit hash if available
            validation_report_id: QF validation report ID
            quality_score: Quality score from validation

        Returns:
            Created TemplateVersion
        """
        # Get parent version
        existing = self._versions.get(template_id, [])
        parent_version = None
        if existing:
            sorted_versions = sorted(
                existing,
                key=lambda v: self._parse_version(v.version),
                reverse=True
            )
            parent_version = sorted_versions[0].version

        new_version = TemplateVersion(
            version=version,
            template_id=template_id,
            created_at=datetime.now(),
            created_by=created_by,
            change_type=change_type,
            changes=changes,
            changelog=changelog,
            parent_version=parent_version,
            commit_hash=commit_hash,
            validation_report_id=validation_report_id,
            quality_score=quality_score,
        )

        if template_id not in self._versions:
            self._versions[template_id] = []
        self._versions[template_id].append(new_version)

        VERSION_OPERATIONS.labels(operation="create_version", status="success").inc()
        logger.info(f"Created version {version} for template {template_id}")

        return new_version

    def rollback_version(
        self,
        template_id: str,
        target_version: str,
        rolled_back_by: str,
        reason: Optional[str] = None,
    ) -> Optional[TemplateVersion]:
        """
        Rollback a template to a previous version.

        This creates a new version that restores the content from the target version,
        maintaining full version history for audit purposes.

        Args:
            template_id: Template ID to rollback
            target_version: Version to rollback to
            rolled_back_by: User/agent performing the rollback
            reason: Optional reason for the rollback

        Returns:
            New TemplateVersion representing the rollback, or None if failed
        """
        try:
            # Get the target version
            target = self.get_version_details(template_id, target_version)
            if not target:
                logger.error(f"Rollback failed: version {target_version} not found for {template_id}")
                VERSION_OPERATIONS.labels(operation="rollback", status="error").inc()
                return None

            # Get current (latest) version
            versions, _ = self.get_template_versions(template_id, limit=1)
            if not versions:
                logger.error(f"Rollback failed: no versions found for {template_id}")
                VERSION_OPERATIONS.labels(operation="rollback", status="error").inc()
                return None

            current_version = versions[0]

            # Don't rollback to the same version
            if current_version.version == target_version:
                logger.warning(f"Rollback skipped: already at version {target_version}")
                return current_version

            # Calculate new version number (increment patch)
            current_parts = self._parse_version(current_version.version)
            new_version_str = f"{current_parts[0]}.{current_parts[1]}.{current_parts[2] + 1}"

            # Create rollback changelog
            rollback_reason = reason or "No reason provided"
            changelog = (
                f"Rollback from {current_version.version} to {target_version}. "
                f"Reason: {rollback_reason}"
            )

            # Create the rollback version
            rollback_version = self.create_version(
                template_id=template_id,
                version=new_version_str,
                changes=[
                    f"Rolled back from {current_version.version}",
                    f"Restored to version {target_version}",
                    f"Reason: {rollback_reason}",
                ],
                changelog=changelog,
                created_by=rolled_back_by,
                change_type=VersionChangeType.PATCH,
                quality_score=target.quality_score,
                commit_hash=target.commit_hash,
                validation_report_id=target.validation_report_id,
            )

            # Add rollback metadata
            rollback_version.metadata["rollback"] = {
                "from_version": current_version.version,
                "to_version": target_version,
                "reason": rollback_reason,
                "timestamp": datetime.now().isoformat(),
            }

            VERSION_OPERATIONS.labels(operation="rollback", status="success").inc()
            logger.info(
                f"Rolled back template {template_id} from {current_version.version} "
                f"to {target_version} (new version: {new_version_str})"
            )

            return rollback_version

        except Exception as e:
            VERSION_OPERATIONS.labels(operation="rollback", status="error").inc()
            logger.error(f"Rollback failed for {template_id}: {e}")
            return None

    def get_rollback_candidates(
        self,
        template_id: str,
        max_versions: int = 5,
    ) -> List[TemplateVersion]:
        """
        Get list of versions that can be rolled back to.

        Returns previous versions sorted by version number (newest first),
        excluding the current version.

        Args:
            template_id: Template ID
            max_versions: Maximum number of candidates to return

        Returns:
            List of TemplateVersion objects that can be rolled back to
        """
        versions, total = self.get_template_versions(template_id, limit=max_versions + 1)

        # Exclude the current (first) version
        if len(versions) > 1:
            return versions[1:max_versions + 1]
        return []

    def validate_rollback(
        self,
        template_id: str,
        target_version: str,
    ) -> Dict[str, Any]:
        """
        Validate if a rollback is safe to perform.

        Checks:
        - Target version exists
        - Target version has quality score above threshold
        - No blocking issues

        Args:
            template_id: Template ID
            target_version: Version to rollback to

        Returns:
            Validation result with 'valid' boolean and 'issues' list
        """
        issues = []
        warnings = []

        # Check if target version exists
        target = self.get_version_details(template_id, target_version)
        if not target:
            issues.append(f"Version {target_version} not found")
            return {"valid": False, "issues": issues, "warnings": warnings}

        # Check quality score
        if target.quality_score and target.quality_score < 70:
            warnings.append(
                f"Target version has low quality score: {target.quality_score}"
            )

        # Check if it's a very old version (more than 5 versions back)
        versions, _ = self.get_template_versions(template_id, limit=10)
        version_index = next(
            (i for i, v in enumerate(versions) if v.version == target_version),
            -1
        )
        if version_index > 5:
            warnings.append(
                f"Rolling back {version_index} versions - consider impact carefully"
            )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "target_version": target.to_dict() if target else None,
        }

    def _parse_version(self, version: str) -> Tuple[int, int, int]:
        """Parse semantic version string to tuple for comparison."""
        try:
            parts = version.split(".")
            return (
                int(parts[0]) if len(parts) > 0 else 0,
                int(parts[1]) if len(parts) > 1 else 0,
                int(parts[2]) if len(parts) > 2 else 0,
            )
        except (ValueError, IndexError):
            return (0, 0, 0)

    # ========================================================================
    # RECOMMENDATION API
    # ========================================================================

    def get_recommendations(
        self,
        request: RecommendationRequest,
    ) -> RecommendationResponse:
        """
        Get template recommendations based on context.

        AC-2: Accepts persona, tag, min_score params
        AC-3: Recommendations ranked by composite score
        AC-4: Response includes usage_stats and citations
        AC-5: Pagination support

        Args:
            request: RecommendationRequest with filters

        Returns:
            RecommendationResponse with ranked recommendations
        """
        start_time = time.time()

        try:
            # Get all templates and filter
            candidates = list(self._templates.values())

            # Apply filters
            filtered = self._apply_filters(candidates, request)

            # Score and rank
            scored = self._score_templates(filtered, request)

            # Sort by score
            scored.sort(key=lambda x: x.score, reverse=True)

            # Apply pagination
            total = len(scored)
            page = (request.offset // request.limit) + 1 if request.limit > 0 else 1
            paginated = scored[request.offset:request.offset + request.limit]
            has_more = (request.offset + request.limit) < total

            # Build response
            response = RecommendationResponse(
                recommendations=paginated,
                total=total,
                page=page,
                page_size=request.limit,
                has_more=has_more,
                filters_applied={
                    "persona": request.persona,
                    "tags": request.tags,
                    "min_score": request.min_score,
                    "language": request.language,
                    "framework": request.framework,
                    "category": request.category,
                },
                strategy_used=request.strategy.value,
            )

            latency = time.time() - start_time
            RECOMMENDATION_LATENCY.observe(latency)
            RECOMMENDATION_OPERATIONS.labels(
                persona=request.persona or "none",
                status="success"
            ).inc()

            logger.info(
                f"Generated {len(paginated)} recommendations "
                f"(total: {total}) in {latency:.3f}s"
            )

            return response

        except Exception as e:
            RECOMMENDATION_OPERATIONS.labels(
                persona=request.persona or "none",
                status="error"
            ).inc()
            logger.error(f"Error generating recommendations: {e}")
            return RecommendationResponse(
                recommendations=[],
                total=0,
                page=1,
                page_size=request.limit,
                has_more=False,
                filters_applied={},
                strategy_used=request.strategy.value,
            )

    def _apply_filters(
        self,
        templates: List[Dict[str, Any]],
        request: RecommendationRequest,
    ) -> List[Dict[str, Any]]:
        """Apply filters to template list."""
        filtered = templates

        # Filter by persona
        if request.persona:
            filtered = [
                t for t in filtered
                if request.persona in t.get("personas", [])
            ]

        # Filter by tags (any match)
        if request.tags:
            filtered = [
                t for t in filtered
                if any(tag in t.get("tags", []) for tag in request.tags)
            ]

        # Filter by min_score
        if request.min_score is not None:
            filtered = [
                t for t in filtered
                if t.get("quality_score", 0) >= request.min_score
            ]

        # Filter by language
        if request.language:
            filtered = [
                t for t in filtered
                if t.get("language", "").lower() == request.language.lower()
            ]

        # Filter by framework
        if request.framework:
            filtered = [
                t for t in filtered
                if t.get("framework", "").lower() == request.framework.lower()
            ]

        # Filter by category
        if request.category:
            filtered = [
                t for t in filtered
                if t.get("category", "").lower() == request.category.lower()
            ]

        return filtered

    def _score_templates(
        self,
        templates: List[Dict[str, Any]],
        request: RecommendationRequest,
    ) -> List[TemplateRecommendation]:
        """Score and convert templates to recommendations."""
        recommendations = []

        for tmpl in templates:
            template_id = tmpl["id"]

            # Get usage stats
            usage_stats = self._usage_stats.get(
                template_id,
                UsageStats(template_id=template_id)
            )

            # Get citations
            citations = self._citations.get(template_id, [])

            # Get latest version
            versions = self._versions.get(template_id, [])
            latest_version = "1.0.0"
            if versions:
                sorted_versions = sorted(
                    versions,
                    key=lambda v: self._parse_version(v.version),
                    reverse=True
                )
                latest_version = sorted_versions[0].version

            # Calculate composite score based on strategy
            quality_score = tmpl.get("quality_score", 0)
            score = self._calculate_composite_score(
                quality_score=quality_score,
                success_rate=usage_stats.success_rate,
                usage_count=usage_stats.applied_count,
                request=request,
                template=tmpl,
            )

            # Build match reasons
            match_reasons = []
            persona_match = False
            tag_match = False

            if request.persona and request.persona in tmpl.get("personas", []):
                match_reasons.append(f"Matches persona: {request.persona}")
                persona_match = True

            if request.tags:
                matching_tags = [
                    tag for tag in request.tags
                    if tag in tmpl.get("tags", [])
                ]
                if matching_tags:
                    match_reasons.append(f"Matches tags: {', '.join(matching_tags)}")
                    tag_match = True

            if quality_score >= 90:
                match_reasons.append("High quality score (90+)")

            if usage_stats.success_rate >= 0.9:
                match_reasons.append("High success rate (90%+)")

            recommendation = TemplateRecommendation(
                template_id=template_id,
                template_name=tmpl.get("name", template_id),
                version=latest_version,
                score=score,
                quality_score=quality_score,
                usage_stats=usage_stats,
                citations=citations if request.include_citations else [],
                match_reasons=match_reasons,
                persona_match=persona_match,
                tag_match=tag_match,
                metadata={
                    "category": tmpl.get("category"),
                    "language": tmpl.get("language"),
                    "framework": tmpl.get("framework"),
                },
            )

            recommendations.append(recommendation)

        return recommendations

    def _calculate_composite_score(
        self,
        quality_score: float,
        success_rate: float,
        usage_count: int,
        request: RecommendationRequest,
        template: Dict[str, Any],
    ) -> float:
        """Calculate composite recommendation score."""
        weights = self.scoring_weights

        # Normalize values to 0-100 scale
        normalized_quality = quality_score
        normalized_success = success_rate * 100
        normalized_usage = min(usage_count / 2, 100)  # Cap at 200 uses = 100
        normalized_recency = 80  # Placeholder for recency score

        # Calculate match score
        match_score = 0
        if request.persona and request.persona in template.get("personas", []):
            match_score += 50
        if request.tags:
            matching = len([
                t for t in request.tags
                if t in template.get("tags", [])
            ])
            match_score += min(matching * 25, 50)

        # Apply strategy
        if request.strategy == RecommendationStrategy.QUALITY_FIRST:
            weights = {**weights, "quality_score": 0.6, "success_rate": 0.2}
        elif request.strategy == RecommendationStrategy.USAGE_FIRST:
            weights = {**weights, "success_rate": 0.5, "usage_count": 0.3}
        elif request.strategy == RecommendationStrategy.RECENT_FIRST:
            weights = {**weights, "recency": 0.4, "quality_score": 0.3}

        # Calculate weighted score
        score = (
            weights["quality_score"] * normalized_quality +
            weights["success_rate"] * normalized_success +
            weights["usage_count"] * normalized_usage +
            weights["recency"] * normalized_recency +
            weights["match_score"] * match_score
        )

        return min(score, 100)  # Cap at 100

    # ========================================================================
    # USAGE TRACKING
    # ========================================================================

    def record_template_usage(
        self,
        template_id: str,
        success: bool,
        quality_score: Optional[float] = None,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> None:
        """Record template usage for statistics."""
        if template_id not in self._usage_stats:
            self._usage_stats[template_id] = UsageStats(template_id=template_id)

        stats = self._usage_stats[template_id]
        stats.applied_count += 1

        if success:
            stats.success_count += 1
        else:
            stats.failure_count += 1

        # Update success rate
        total = stats.success_count + stats.failure_count
        stats.success_rate = stats.success_count / total if total > 0 else 0

        # Update quality score average
        if quality_score is not None:
            current_avg = stats.avg_quality_score
            stats.avg_quality_score = (
                (current_avg * (stats.applied_count - 1) + quality_score) /
                stats.applied_count
            )

        stats.last_used_at = datetime.now()

        # Track unique users/projects (simplified)
        if user_id:
            stats.unique_users = min(stats.unique_users + 1, stats.applied_count)
        if project_id:
            stats.unique_projects = min(stats.unique_projects + 1, stats.applied_count)

        TEMPLATE_USAGE_GAUGE.labels(template_id=template_id).set(stats.applied_count)
        logger.debug(f"Recorded usage for template {template_id}: success={success}")

    def get_usage_stats(self, template_id: str) -> Optional[UsageStats]:
        """Get usage statistics for a template."""
        return self._usage_stats.get(template_id)

    # ========================================================================
    # CITATION MANAGEMENT
    # ========================================================================

    def add_citation(
        self,
        template_id: str,
        citation: str,
    ) -> None:
        """Add a citation to a template."""
        if template_id not in self._citations:
            self._citations[template_id] = []

        if citation not in self._citations[template_id]:
            self._citations[template_id].append(citation)
            logger.info(f"Added citation '{citation}' to template {template_id}")

    def get_citations(self, template_id: str) -> List[str]:
        """Get citations for a template."""
        return self._citations.get(template_id, [])


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_service_instance: Optional[TemplateVersionsService] = None


def get_template_versions_service() -> TemplateVersionsService:
    """Get or create the singleton service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = TemplateVersionsService()
    return _service_instance


# For convenience
template_versions_service = get_template_versions_service()
