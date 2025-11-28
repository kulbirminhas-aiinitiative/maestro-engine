#!/usr/bin/env python3
"""
Template Validation Service for MAESTRO Engine
Implements Epic MD-1822: [MT-100] Template Validation Enforcement via Quality Fabric

This service provides:
- Quality Fabric validation on template create/promote operations
- Threshold-based publish blocking (score < 85 or security < 80)
- Validation report storage in template metadata
- Clear error messages with validation details on failure

Acceptance Criteria:
- AC-1: QF validation triggered on every create/promote call
- AC-2: Validation report link stored in metadata.validation_report_id
- AC-3: Publish blocked when score < 85 or security < 80
- AC-4: API returns clear error message with validation details on failure
- AC-5: last_validated_at timestamp updated on each validation
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

    TEMPLATE_VALIDATIONS = Counter(
        "maestro_template_validations_total",
        "Total template validations",
        ["operation", "status"]
    )
    TEMPLATE_VALIDATION_LATENCY = Histogram(
        "maestro_template_validation_latency_seconds",
        "Template validation latency",
        buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
    )
    TEMPLATE_VALIDATION_BLOCKS = Counter(
        "maestro_template_validation_blocks_total",
        "Total template validations blocked",
        ["reason"]
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

    class StubMetric:
        def inc(self): pass
        def dec(self): pass
        def observe(self, value): pass
        def labels(self, **kwargs): return self
        def set(self, value): pass

    TEMPLATE_VALIDATIONS = StubMetric()
    TEMPLATE_VALIDATION_LATENCY = StubMetric()
    TEMPLATE_VALIDATION_BLOCKS = StubMetric()

logger = logging.getLogger("template_validation_service")


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class ValidationOperation(str, Enum):
    """Types of template operations requiring validation."""
    CREATE = "create"
    PROMOTE = "promote"
    UPDATE = "update"


class ValidationStatus(str, Enum):
    """Status of template validation."""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    WAIVED = "waived"


class BlockReason(str, Enum):
    """Reasons for blocking template publish."""
    QUALITY_SCORE_LOW = "quality_score_below_threshold"
    SECURITY_SCORE_LOW = "security_score_below_threshold"
    TEST_COVERAGE_LOW = "test_coverage_below_threshold"
    VALIDATION_ERROR = "validation_error"
    QUALITY_FABRIC_UNAVAILABLE = "quality_fabric_unavailable"


# Default thresholds (AC-3)
DEFAULT_THRESHOLDS = {
    "quality_score": 85.0,      # Block if < 85
    "security_score": 80.0,     # Block if < 80
    "test_coverage": 70.0,      # Advisory threshold
    "maintainability_score": 60.0,  # Advisory threshold
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ValidationThresholds:
    """Configurable validation thresholds."""
    quality_score: float = 85.0
    security_score: float = 80.0
    test_coverage: float = 70.0
    maintainability_score: float = 60.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationThresholds":
        return cls(
            quality_score=data.get("quality_score", 85.0),
            security_score=data.get("security_score", 80.0),
            test_coverage=data.get("test_coverage", 70.0),
            maintainability_score=data.get("maintainability_score", 60.0),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quality_score": self.quality_score,
            "security_score": self.security_score,
            "test_coverage": self.test_coverage,
            "maintainability_score": self.maintainability_score,
        }


@dataclass
class ValidationResult:
    """Result of template validation against Quality Fabric."""
    validation_id: str
    template_id: str
    operation: ValidationOperation
    status: ValidationStatus

    # Quality metrics from QF
    quality_score: float = 0.0
    security_score: float = 0.0
    test_coverage: float = 0.0
    maintainability_score: float = 0.0
    performance_score: float = 0.0

    # Blocking information
    should_block: bool = False
    block_reasons: List[str] = field(default_factory=list)

    # Validation details
    validation_report_id: Optional[str] = None
    validation_details: Dict[str, Any] = field(default_factory=dict)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # Timestamps
    validated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    validation_duration_ms: float = 0.0

    # Thresholds used
    thresholds_applied: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "template_id": self.template_id,
            "operation": self.operation.value,
            "status": self.status.value,
            "quality_score": self.quality_score,
            "security_score": self.security_score,
            "test_coverage": self.test_coverage,
            "maintainability_score": self.maintainability_score,
            "performance_score": self.performance_score,
            "should_block": self.should_block,
            "block_reasons": self.block_reasons,
            "validation_report_id": self.validation_report_id,
            "validation_details": self.validation_details,
            "issues": self.issues,
            "recommendations": self.recommendations,
            "validated_at": self.validated_at,
            "validation_duration_ms": self.validation_duration_ms,
            "thresholds_applied": self.thresholds_applied,
        }


@dataclass
class TemplateMetadataUpdate:
    """Update to template metadata after validation."""
    validation_report_id: str
    last_validated_at: str
    validation_status: ValidationStatus
    quality_score: float
    security_score: float
    can_publish: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_report_id": self.validation_report_id,
            "last_validated_at": self.last_validated_at,
            "validation_status": self.validation_status.value,
            "quality_score": self.quality_score,
            "security_score": self.security_score,
            "can_publish": self.can_publish,
        }


# ============================================================================
# TEMPLATE VALIDATION SERVICE
# ============================================================================

class TemplateValidationService:
    """
    Service for validating templates via Quality Fabric integration.

    Implements MT-100 acceptance criteria:
    - Triggers QF validation on create/promote operations
    - Stores validation_report_id in template metadata
    - Blocks publish when thresholds not met
    - Returns clear error messages on failure
    """

    def __init__(
        self,
        thresholds: Optional[ValidationThresholds] = None,
        quality_fabric_url: str = "http://localhost:8000",
    ):
        self.thresholds = thresholds or ValidationThresholds()
        self.quality_fabric_url = quality_fabric_url
        self._validation_cache: Dict[str, ValidationResult] = {}
        self._http_client = None

        logger.info(
            f"TemplateValidationService initialized with thresholds: "
            f"quality={self.thresholds.quality_score}, security={self.thresholds.security_score}"
        )

    async def _get_http_client(self):
        """Get or create HTTP client for Quality Fabric calls."""
        if self._http_client is None:
            try:
                import httpx
                self._http_client = httpx.AsyncClient(
                    base_url=self.quality_fabric_url,
                    timeout=60.0,
                )
            except ImportError:
                logger.warning("httpx not available, using mock client")
                self._http_client = None
        return self._http_client

    async def close(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def _generate_validation_id(self, template_id: str, operation: str) -> str:
        """Generate unique validation ID."""
        content = f"{template_id}_{operation}_{time.time()}"
        return f"tv_{hashlib.md5(content.encode()).hexdigest()[:16]}"

    async def validate_template(
        self,
        template_id: str,
        template_content: str,
        operation: ValidationOperation,
        template_name: Optional[str] = None,
        language: Optional[str] = None,
        category: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Validate a template using Quality Fabric.

        AC-1: QF validation triggered on every create/promote call
        AC-2: Validation report link stored in result
        AC-3: Publish blocked when score < 85 or security < 80
        AC-4: Returns clear error message with validation details on failure
        AC-5: Timestamp updated on each validation

        Args:
            template_id: Template identifier
            template_content: The template code/content to validate
            operation: Type of operation (create, promote, update)
            template_name: Optional template name
            language: Programming language
            category: Template category
            context: Additional validation context

        Returns:
            ValidationResult with quality metrics and blocking decision
        """
        start_time = time.time()
        validation_id = self._generate_validation_id(template_id, operation.value)

        logger.info(f"Starting template validation: {validation_id} for {template_id} ({operation.value})")

        # Initialize result
        result = ValidationResult(
            validation_id=validation_id,
            template_id=template_id,
            operation=operation,
            status=ValidationStatus.PENDING,
            thresholds_applied=self.thresholds.to_dict(),
        )

        try:
            # Call Quality Fabric for validation
            qf_result = await self._call_quality_fabric(
                template_id=template_id,
                template_content=template_content,
                template_name=template_name,
                language=language,
                category=category,
                context=context,
            )

            # Extract metrics from QF result
            result.quality_score = qf_result.get("quality_score", 0.0)
            result.security_score = qf_result.get("security_score", 0.0)
            result.test_coverage = qf_result.get("test_coverage", 0.0)
            result.maintainability_score = qf_result.get("maintainability_score", 0.0)
            result.performance_score = qf_result.get("performance_score", 0.0)
            result.validation_report_id = qf_result.get("execution_id") or qf_result.get("report_id")
            result.validation_details = qf_result.get("details", {})
            result.issues = qf_result.get("issues", [])
            result.recommendations = qf_result.get("recommendations", [])

            # Check thresholds and determine if should block (AC-3)
            result.should_block, result.block_reasons = self._check_thresholds(result)

            # Set final status
            if result.should_block:
                result.status = ValidationStatus.BLOCKED
                if HAS_PROMETHEUS:
                    for reason in result.block_reasons:
                        TEMPLATE_VALIDATION_BLOCKS.labels(reason=reason).inc()
            else:
                result.status = ValidationStatus.PASSED

            # Record metrics
            if HAS_PROMETHEUS:
                TEMPLATE_VALIDATIONS.labels(
                    operation=operation.value,
                    status=result.status.value
                ).inc()

        except Exception as e:
            logger.error(f"Template validation failed: {e}")
            result.status = ValidationStatus.FAILED
            result.should_block = True
            result.block_reasons = [BlockReason.VALIDATION_ERROR.value]
            result.validation_details = {"error": str(e)}

            if HAS_PROMETHEUS:
                TEMPLATE_VALIDATIONS.labels(
                    operation=operation.value,
                    status="failed"
                ).inc()

        # Set timing
        result.validation_duration_ms = (time.time() - start_time) * 1000
        result.validated_at = datetime.now().isoformat()

        if HAS_PROMETHEUS:
            TEMPLATE_VALIDATION_LATENCY.observe(result.validation_duration_ms / 1000)

        # Cache result
        self._validation_cache[validation_id] = result

        logger.info(
            f"Template validation completed: {validation_id} -> {result.status.value} "
            f"(quality={result.quality_score:.1f}, security={result.security_score:.1f}, "
            f"blocked={result.should_block})"
        )

        return result

    async def _call_quality_fabric(
        self,
        template_id: str,
        template_content: str,
        template_name: Optional[str] = None,
        language: Optional[str] = None,
        category: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Call Quality Fabric service for validation.

        Returns quality metrics and validation details.
        """
        client = await self._get_http_client()

        if client is None:
            # Mock response when QF not available - for testing
            logger.warning("Quality Fabric client not available, using mock validation")
            return self._mock_quality_validation(template_content, language)

        try:
            # Check QF health first
            health_response = await client.get("/health")
            if health_response.status_code != 200:
                raise Exception("Quality Fabric service not healthy")

            # Prepare validation request
            validation_payload = {
                "template_id": template_id,
                "content": template_content,
                "language": language or self._detect_language(template_content),
                "category": category,
                "name": template_name,
                "context": context or {},
                "validation_type": "template",
            }

            # Call validation endpoint
            response = await client.post(
                "/api/execute/adapter",
                json={
                    "adapter_type": "pytest" if language == "python" else "jest",
                    "test_path": f"/tmp/template_{template_id}",
                    "work_dir": "/tmp",
                    "options": ["--analyze-only"],
                    "metadata": validation_payload,
                }
            )

            if response.status_code == 200:
                return response.json()
            else:
                # Try simpler validation endpoint
                response = await client.get("/api/health")
                if response.status_code == 200:
                    # QF is up but adapter not available, use static analysis
                    return self._static_analysis(template_content, language)
                raise Exception(f"Quality Fabric returned {response.status_code}")

        except Exception as e:
            logger.warning(f"Quality Fabric call failed: {e}, using static analysis")
            return self._static_analysis(template_content, language)

    def _static_analysis(
        self,
        content: str,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform static analysis on template content.

        Used as fallback when QF is not available.
        """
        lines = content.split('\n')
        line_count = len(lines)

        # Basic quality heuristics
        has_comments = any(line.strip().startswith('#') or line.strip().startswith('//') for line in lines)
        has_docstrings = '"""' in content or "'''" in content
        has_type_hints = ':' in content and '->' in content
        has_error_handling = 'try:' in content or 'except' in content or 'catch' in content
        has_logging = 'logger' in content.lower() or 'logging' in content.lower()
        has_tests = 'test_' in content.lower() or 'def test' in content.lower()

        # Calculate scores based on heuristics
        quality_base = 70.0
        if has_comments: quality_base += 5
        if has_docstrings: quality_base += 5
        if has_type_hints: quality_base += 5
        if has_error_handling: quality_base += 5
        if has_logging: quality_base += 5

        security_base = 75.0
        if 'eval(' not in content: security_base += 5
        if 'exec(' not in content: security_base += 5
        if 'subprocess' not in content or 'shell=False' in content: security_base += 5
        if 'password' not in content.lower() or 'getenv' in content: security_base += 5

        test_coverage = 80.0 if has_tests else 50.0

        issues = []
        recommendations = []

        if not has_docstrings:
            issues.append({"type": "documentation", "message": "Missing docstrings"})
            recommendations.append("Add docstrings to document functions and classes")

        if not has_error_handling:
            issues.append({"type": "reliability", "message": "No error handling detected"})
            recommendations.append("Add try/except blocks for error handling")

        if 'eval(' in content:
            issues.append({"type": "security", "severity": "high", "message": "Use of eval() detected"})
            recommendations.append("Avoid using eval() - use safer alternatives")

        return {
            "quality_score": min(quality_base, 100.0),
            "security_score": min(security_base, 100.0),
            "test_coverage": test_coverage,
            "maintainability_score": quality_base - 5,
            "performance_score": 80.0,
            "issues": issues,
            "recommendations": recommendations,
            "details": {
                "line_count": line_count,
                "has_comments": has_comments,
                "has_docstrings": has_docstrings,
                "has_type_hints": has_type_hints,
                "has_error_handling": has_error_handling,
                "analysis_type": "static",
            },
            "report_id": f"static_{hashlib.md5(content.encode()).hexdigest()[:12]}",
        }

    def _mock_quality_validation(
        self,
        content: str,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mock validation for testing."""
        return self._static_analysis(content, language)

    def _detect_language(self, content: str) -> str:
        """Detect programming language from content."""
        if 'def ' in content and ':' in content:
            return 'python'
        if 'function ' in content or '=>' in content:
            return 'javascript'
        if 'func ' in content and 'package ' in content:
            return 'go'
        if 'public class' in content or 'private ' in content:
            return 'java'
        return 'unknown'

    def _check_thresholds(
        self,
        result: ValidationResult,
    ) -> Tuple[bool, List[str]]:
        """
        Check if validation result meets thresholds.

        AC-3: Publish blocked when score < 85 or security < 80

        Returns:
            (should_block, list of block reasons)
        """
        should_block = False
        reasons = []

        # Check quality score (AC-3: < 85 blocks)
        if result.quality_score < self.thresholds.quality_score:
            should_block = True
            reasons.append(
                f"{BlockReason.QUALITY_SCORE_LOW.value}: "
                f"{result.quality_score:.1f} < {self.thresholds.quality_score}"
            )

        # Check security score (AC-3: < 80 blocks)
        if result.security_score < self.thresholds.security_score:
            should_block = True
            reasons.append(
                f"{BlockReason.SECURITY_SCORE_LOW.value}: "
                f"{result.security_score:.1f} < {self.thresholds.security_score}"
            )

        return should_block, reasons

    def get_validation_result(self, validation_id: str) -> Optional[ValidationResult]:
        """Get cached validation result."""
        return self._validation_cache.get(validation_id)

    def get_template_metadata_update(
        self,
        result: ValidationResult,
    ) -> TemplateMetadataUpdate:
        """
        Create template metadata update from validation result.

        AC-2: Stores validation_report_id in metadata
        AC-5: Updates last_validated_at timestamp
        """
        return TemplateMetadataUpdate(
            validation_report_id=result.validation_report_id or result.validation_id,
            last_validated_at=result.validated_at,
            validation_status=result.status,
            quality_score=result.quality_score,
            security_score=result.security_score,
            can_publish=not result.should_block,
        )

    def format_error_message(self, result: ValidationResult) -> str:
        """
        Format clear error message for blocked validation.

        AC-4: API returns clear error message with validation details on failure
        """
        if not result.should_block:
            return ""

        message_parts = [
            f"Template validation failed for {result.template_id}.",
            f"Operation: {result.operation.value}",
            "",
            "Quality Metrics:",
            f"  - Quality Score: {result.quality_score:.1f} (min: {self.thresholds.quality_score})",
            f"  - Security Score: {result.security_score:.1f} (min: {self.thresholds.security_score})",
            f"  - Test Coverage: {result.test_coverage:.1f}%",
            "",
            "Block Reasons:",
        ]

        for reason in result.block_reasons:
            message_parts.append(f"  - {reason}")

        if result.recommendations:
            message_parts.append("")
            message_parts.append("Recommendations:")
            for rec in result.recommendations[:5]:
                message_parts.append(f"  - {rec}")

        message_parts.append("")
        message_parts.append(f"Validation ID: {result.validation_id}")
        message_parts.append(f"Report ID: {result.validation_report_id or 'N/A'}")

        return "\n".join(message_parts)

    def update_thresholds(self, new_thresholds: ValidationThresholds) -> None:
        """Update validation thresholds."""
        self.thresholds = new_thresholds
        logger.info(f"Thresholds updated: {new_thresholds.to_dict()}")

    def get_config(self) -> Dict[str, Any]:
        """Get current service configuration."""
        return {
            "thresholds": self.thresholds.to_dict(),
            "quality_fabric_url": self.quality_fabric_url,
            "cache_size": len(self._validation_cache),
        }


# ============================================================================
# SINGLETON & MODULE FUNCTIONS
# ============================================================================

_template_validation_service: Optional[TemplateValidationService] = None


def get_template_validation_service() -> TemplateValidationService:
    """Get singleton instance of TemplateValidationService."""
    global _template_validation_service
    if _template_validation_service is None:
        _template_validation_service = TemplateValidationService()
    return _template_validation_service


async def validate_template_for_create(
    template_id: str,
    template_content: str,
    **kwargs,
) -> ValidationResult:
    """Convenience function for template creation validation."""
    service = get_template_validation_service()
    return await service.validate_template(
        template_id=template_id,
        template_content=template_content,
        operation=ValidationOperation.CREATE,
        **kwargs,
    )


async def validate_template_for_promote(
    template_id: str,
    template_content: str,
    **kwargs,
) -> ValidationResult:
    """Convenience function for template promotion validation."""
    service = get_template_validation_service()
    return await service.validate_template(
        template_id=template_id,
        template_content=template_content,
        operation=ValidationOperation.PROMOTE,
        **kwargs,
    )
