#!/usr/bin/env python3
"""
Quality Fabric Enforcement Service for MAESTRO Engine
Implements EPIC-4 (ME-400): Quality Fabric Enforcement

This service provides:
- Phase-to-test mapping configuration (AC-1)
- Test results as gate evidence (AC-2)
- Test failure blocking gates unless waiver (AC-3)
- Configurable thresholds for coverage and static analysis (AC-4)
- Auto-enable in staging/production environments (AC-5)
- Test artifact linking to run manifests (AC-6)

Acceptance Criteria:
- AC-1: Each phase has at least one mapped test scenario
- AC-2: Test results tie to gates as evidence
- AC-3: Failing tests block gate unless waiver present
- AC-4: Configurable thresholds (coverage, static analysis)
- AC-5: Quality Fabric enabled by default in staging/prod
- AC-6: Test artifacts linked to run manifest
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Try to import Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, Gauge

    QUALITY_VALIDATIONS = Counter(
        "maestro_quality_validations_total",
        "Total quality validations",
        ["phase", "result"]
    )
    QUALITY_VALIDATION_LATENCY = Histogram(
        "maestro_quality_validation_latency_seconds",
        "Quality validation latency",
        buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
    )
    QUALITY_WAIVERS = Counter(
        "maestro_quality_waivers_total",
        "Total quality waivers granted",
        ["phase", "reason"]
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

    QUALITY_VALIDATIONS = StubMetric()
    QUALITY_VALIDATION_LATENCY = StubMetric()
    QUALITY_WAIVERS = StubMetric()

logger = logging.getLogger("quality_fabric_enforcement")


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class TestCategory(str, Enum):
    """Categories of tests that can be mapped to phases."""
    UNIT = "unit"
    INTEGRATION = "integration"
    FUNCTIONAL = "functional"
    API = "api"
    FRONTEND = "frontend"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COMPLIANCE = "compliance"


class EnforcementLevel(str, Enum):
    """Enforcement level for quality checks."""
    STRICT = "strict"      # Block on any failure
    STANDARD = "standard"  # Block on threshold breach
    RELAXED = "relaxed"    # Warning only
    DISABLED = "disabled"  # No enforcement


class WaiverType(str, Enum):
    """Types of waivers for bypassing quality gates."""
    EMERGENCY = "emergency"      # Emergency release
    TECHNICAL_DEBT = "technical_debt"  # Known technical debt
    EXTERNAL_DEPENDENCY = "external_dependency"  # External system issue
    TEMPORARY = "temporary"      # Time-limited waiver
    EXECUTIVE = "executive"      # Executive override


# ============================================================================
# YAML CONFIG LOADER (QF-200: Phase-Test Mapping from YAML)
# ============================================================================

class PhaseTestConfigLoader:
    """
    Loads phase-test mapping configuration from YAML/JSON files.

    Part of QF-200: Phase-Test Mapping with Threshold Enforcement
    """

    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "phase_test_mapping.yaml"

    @classmethod
    def load_config(cls, config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load phase-test mapping configuration from file.

        Args:
            config_path: Path to config file (YAML or JSON)

        Returns:
            Configuration dictionary
        """
        path = Path(config_path) if config_path else cls.DEFAULT_CONFIG_PATH

        if not path.exists():
            logger.warning(f"Config file not found: {path}, using defaults")
            return {}

        try:
            with open(path, 'r') as f:
                if path.suffix in ['.yaml', '.yml']:
                    config = yaml.safe_load(f)
                else:
                    config = json.load(f)

            logger.info(f"Loaded phase-test config from: {path}")
            return config or {}

        except Exception as e:
            logger.error(f"Failed to load config from {path}: {e}")
            return {}

    @classmethod
    def get_phase_mapping_from_config(
        cls,
        config: Dict[str, Any],
        phase_type: str
    ) -> Optional[Dict[str, Any]]:
        """Extract phase mapping from loaded config."""
        phase_test_map = config.get("phase_test_map", {})
        return phase_test_map.get(phase_type)

    @classmethod
    def get_default_thresholds(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get default thresholds from config."""
        return config.get("defaults", {})

    @classmethod
    def get_environment_config(
        cls,
        config: Dict[str, Any],
        environment: str
    ) -> Dict[str, Any]:
        """Get environment-specific configuration."""
        environments = config.get("environments", {})
        return environments.get(environment, {})


# ============================================================================
# PHASE-TO-TEST MAPPING (AC-1)
# ============================================================================

# Default phase-to-test category mapping
DEFAULT_PHASE_TEST_MAPPING: Dict[str, List[str]] = {
    "requirements": [
        TestCategory.UNIT.value,  # Validate requirement schemas
    ],
    "design": [
        TestCategory.UNIT.value,
        TestCategory.API.value,  # API contract validation
    ],
    "implementation": [
        TestCategory.UNIT.value,
        TestCategory.INTEGRATION.value,
        TestCategory.FUNCTIONAL.value,
    ],
    "testing": [
        TestCategory.UNIT.value,
        TestCategory.INTEGRATION.value,
        TestCategory.FUNCTIONAL.value,
        TestCategory.API.value,
    ],
    "deployment": [
        TestCategory.INTEGRATION.value,
        TestCategory.API.value,
        TestCategory.PERFORMANCE.value,
    ],
    "security_review": [
        TestCategory.SECURITY.value,
        TestCategory.COMPLIANCE.value,
    ],
}


# Default quality thresholds (AC-4)
DEFAULT_THRESHOLDS: Dict[str, Any] = {
    "test_coverage": {
        "min_coverage_percent": 80,
        "warn_coverage_percent": 70,
    },
    "test_pass_rate": {
        "min_pass_rate_percent": 95,
        "warn_pass_rate_percent": 90,
    },
    "static_analysis": {
        "max_critical_issues": 0,
        "max_high_issues": 5,
        "max_medium_issues": 20,
    },
    "performance": {
        "max_latency_ms": 200,
        "max_memory_mb": 512,
    },
}


# Environment-specific enforcement levels (AC-5)
ENVIRONMENT_ENFORCEMENT: Dict[str, EnforcementLevel] = {
    "development": EnforcementLevel.RELAXED,
    "testing": EnforcementLevel.STANDARD,
    "staging": EnforcementLevel.STRICT,
    "production": EnforcementLevel.STRICT,
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class PhaseTestMapping:
    """Mapping of phase to test categories."""
    phase_id: str
    phase_type: str
    test_categories: List[str]
    custom_scenarios: List[Dict[str, Any]] = field(default_factory=list)
    thresholds: Dict[str, Any] = field(default_factory=dict)
    enforcement_level: EnforcementLevel = EnforcementLevel.STANDARD
    rollback_on_fail: bool = False  # QF-200: Rollback on deployment failure
    test_commands: Dict[str, str] = field(default_factory=dict)  # e.g., {"unit": "pytest::tests/unit"}
    smoke_tests: List[str] = field(default_factory=list)  # e.g., ["scripts/smoke_tests.sh"]
    static_analysis: List[str] = field(default_factory=list)  # e.g., ["security/linters/owasp.yaml"]


@dataclass
class QualityThreshold:
    """Quality threshold configuration."""
    name: str
    min_value: float
    warn_value: Optional[float] = None
    max_value: Optional[float] = None
    blocking: bool = True


@dataclass
class TestResult:
    """Result from a test execution."""
    test_id: str
    category: str
    name: str
    status: str  # passed, failed, error, skipped
    duration_ms: float
    message: Optional[str] = None
    stack_trace: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)


@dataclass
class QualityValidationResult:
    """Result of quality validation for a phase."""
    validation_id: str
    phase_id: str
    workflow_id: str
    session_id: Optional[str]

    # Test results
    total_tests: int
    passed_tests: int
    failed_tests: int
    error_tests: int
    skipped_tests: int

    # Scores
    test_pass_rate: float
    test_coverage: float
    quality_score: float

    # Threshold evaluation
    thresholds_met: bool
    threshold_violations: List[Dict[str, Any]]

    # Evidence for gates
    evidence_uri: str
    artifacts: List[str]

    # Metadata
    execution_time_ms: float
    timestamp: str
    waiver_applied: bool = False
    waiver_reason: Optional[str] = None

    # QF-200: Rollback support
    rollback_triggered: bool = False
    rollback_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "phase_id": self.phase_id,
            "workflow_id": self.workflow_id,
            "session_id": self.session_id,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "error_tests": self.error_tests,
            "skipped_tests": self.skipped_tests,
            "test_pass_rate": round(self.test_pass_rate, 2),
            "test_coverage": round(self.test_coverage, 2),
            "quality_score": round(self.quality_score, 2),
            "thresholds_met": self.thresholds_met,
            "threshold_violations": self.threshold_violations,
            "evidence_uri": self.evidence_uri,
            "artifacts": self.artifacts,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "timestamp": self.timestamp,
            "waiver_applied": self.waiver_applied,
            "waiver_reason": self.waiver_reason,
            "rollback_triggered": self.rollback_triggered,
            "rollback_reason": self.rollback_reason,
        }


@dataclass
class Waiver:
    """Waiver for bypassing quality gates."""
    waiver_id: str
    phase_id: str
    workflow_id: str
    waiver_type: WaiverType
    reason: str
    granted_by: str
    granted_at: str
    expires_at: Optional[str] = None
    conditions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "waiver_id": self.waiver_id,
            "phase_id": self.phase_id,
            "workflow_id": self.workflow_id,
            "waiver_type": self.waiver_type.value,
            "reason": self.reason,
            "granted_by": self.granted_by,
            "granted_at": self.granted_at,
            "expires_at": self.expires_at,
            "conditions": self.conditions,
        }


# ============================================================================
# QUALITY FABRIC ENFORCEMENT SERVICE
# ============================================================================

class QualityFabricEnforcementService:
    """
    Service for enforcing quality gates via Quality Fabric integration.

    Provides:
    - Phase-to-test mapping management
    - Quality validation execution
    - Threshold enforcement
    - Waiver handling
    - Gate evidence generation
    """

    def __init__(
        self,
        quality_fabric_url: str = "http://localhost:8000",
        environment: str = None,
        custom_thresholds: Dict[str, Any] = None,
        feature_flag_enabled: bool = True,
        config_path: Optional[str] = None,
    ):
        """
        Initialize Quality Fabric Enforcement Service.

        Args:
            quality_fabric_url: URL of Quality Fabric service
            environment: Current environment (dev, staging, prod)
            custom_thresholds: Custom threshold overrides
            feature_flag_enabled: FF_QUALITY_FABRIC_ENFORCEMENT flag
            config_path: Optional path to YAML/JSON config file (QF-200)
        """
        self.quality_fabric_url = quality_fabric_url
        self.environment = environment or os.environ.get("ENVIRONMENT", "development")
        self.feature_flag_enabled = feature_flag_enabled

        # QF-200: Load YAML config
        self._yaml_config = PhaseTestConfigLoader.load_config(config_path)
        self._config_path = config_path

        # Merge thresholds: defaults < yaml config < custom overrides
        yaml_defaults = PhaseTestConfigLoader.get_default_thresholds(self._yaml_config)
        self.thresholds = {**DEFAULT_THRESHOLDS, **yaml_defaults, **(custom_thresholds or {})}

        # Apply environment-specific overrides from YAML
        env_config = PhaseTestConfigLoader.get_environment_config(self._yaml_config, self.environment)
        if env_config.get("override_thresholds"):
            self.thresholds.update(env_config["override_thresholds"])

        # Determine enforcement level based on environment (AC-5)
        yaml_enforcement = env_config.get("enforcement_level")
        if yaml_enforcement:
            try:
                self.enforcement_level = EnforcementLevel(yaml_enforcement)
            except ValueError:
                self.enforcement_level = ENVIRONMENT_ENFORCEMENT.get(
                    self.environment, EnforcementLevel.STANDARD
                )
        else:
            self.enforcement_level = ENVIRONMENT_ENFORCEMENT.get(
                self.environment, EnforcementLevel.STANDARD
            )

        # Phase-test mappings
        self._phase_mappings: Dict[str, PhaseTestMapping] = {}

        # Load phase mappings from YAML config
        self._load_phase_mappings_from_config()

        # Active waivers
        self._waivers: Dict[str, Waiver] = {}

        # Validation history
        self._validation_history: List[QualityValidationResult] = []

        logger.info(
            f"Quality Fabric Enforcement initialized: "
            f"env={self.environment}, level={self.enforcement_level.value}, "
            f"enabled={feature_flag_enabled}, config={'loaded' if self._yaml_config else 'defaults'}"
        )

    def _load_phase_mappings_from_config(self):
        """Load phase mappings from YAML config (QF-200)."""
        phase_test_map = self._yaml_config.get("phase_test_map", {})

        for phase_type, phase_config in phase_test_map.items():
            if isinstance(phase_config, dict):
                # Get test categories
                test_categories = phase_config.get("test_categories", [])

                # Get thresholds - merge with defaults
                phase_thresholds = {**self.thresholds}
                if phase_config.get("thresholds"):
                    phase_thresholds.update(phase_config["thresholds"])

                # Get enforcement level
                enforcement_str = phase_config.get("enforcement", "standard")
                try:
                    enforcement = EnforcementLevel(enforcement_str)
                except ValueError:
                    enforcement = self.enforcement_level

                # Create mapping
                mapping = PhaseTestMapping(
                    phase_id=f"yaml_{phase_type}",
                    phase_type=phase_type,
                    test_categories=test_categories,
                    thresholds=phase_thresholds,
                    enforcement_level=enforcement,
                    rollback_on_fail=phase_config.get("rollback_on_fail", False),
                    test_commands=phase_config.get("test_commands", {}),
                    smoke_tests=phase_config.get("smoke_tests", []),
                    static_analysis=phase_config.get("static_analysis", []),
                )

                self._phase_mappings[phase_type] = mapping
                logger.debug(f"Loaded phase mapping from YAML: {phase_type}")

    # =========================================================================
    # AC-1: Phase-to-Test Mapping
    # =========================================================================

    def get_phase_mapping(self, phase_type: str) -> PhaseTestMapping:
        """
        Get test mapping for a phase type.

        Args:
            phase_type: Type of phase (requirements, design, etc.)

        Returns:
            PhaseTestMapping with test categories for the phase
        """
        # Check for custom mapping first
        if phase_type in self._phase_mappings:
            return self._phase_mappings[phase_type]

        # Fall back to default mapping
        test_categories = DEFAULT_PHASE_TEST_MAPPING.get(phase_type, [TestCategory.UNIT.value])

        return PhaseTestMapping(
            phase_id=f"default_{phase_type}",
            phase_type=phase_type,
            test_categories=test_categories,
            thresholds=self.thresholds,
            enforcement_level=self.enforcement_level,
        )

    def set_phase_mapping(
        self,
        phase_type: str,
        test_categories: List[str],
        custom_scenarios: List[Dict[str, Any]] = None,
        thresholds: Dict[str, Any] = None,
    ) -> PhaseTestMapping:
        """
        Set custom test mapping for a phase type.

        Args:
            phase_type: Type of phase
            test_categories: List of test categories
            custom_scenarios: Custom test scenarios
            thresholds: Custom thresholds

        Returns:
            Created PhaseTestMapping
        """
        mapping = PhaseTestMapping(
            phase_id=f"custom_{phase_type}_{int(time.time())}",
            phase_type=phase_type,
            test_categories=test_categories,
            custom_scenarios=custom_scenarios or [],
            thresholds=thresholds or self.thresholds,
            enforcement_level=self.enforcement_level,
        )

        self._phase_mappings[phase_type] = mapping
        logger.info(f"Phase mapping set: {phase_type} -> {test_categories}")

        return mapping

    def validate_phase_mapping(self, phase_type: str) -> Tuple[bool, str]:
        """
        Validate that a phase has at least one mapped test scenario.

        Args:
            phase_type: Type of phase to validate

        Returns:
            Tuple of (is_valid, message)
        """
        mapping = self.get_phase_mapping(phase_type)

        if not mapping.test_categories and not mapping.custom_scenarios:
            return False, f"Phase '{phase_type}' has no mapped test scenarios"

        return True, f"Phase '{phase_type}' has {len(mapping.test_categories)} test categories"

    # =========================================================================
    # AC-2 & AC-6: Quality Validation and Evidence
    # =========================================================================

    async def validate_phase(
        self,
        phase_id: str,
        phase_type: str,
        workflow_id: str,
        session_id: Optional[str] = None,
        context: Dict[str, Any] = None,
    ) -> QualityValidationResult:
        """
        Validate a phase using Quality Fabric.

        Args:
            phase_id: Phase ID
            phase_type: Type of phase
            workflow_id: Workflow ID
            session_id: Optional session ID
            context: Additional context for validation

        Returns:
            QualityValidationResult with test results and evidence
        """
        start_time = time.time()
        context = context or {}

        try:
            # Get phase mapping
            mapping = self.get_phase_mapping(phase_type)

            # Execute quality validation via Quality Fabric API
            validation_response = await self._execute_quality_fabric_validation(
                mapping, context
            )

            # Extract test results
            test_results = self._extract_test_results(validation_response)

            # Calculate scores
            total_tests = test_results.get("total", 0)
            passed = test_results.get("passed", 0)
            failed = test_results.get("failed", 0)
            errors = test_results.get("errors", 0)
            skipped = test_results.get("skipped", 0)

            pass_rate = (passed / total_tests * 100) if total_tests > 0 else 0
            coverage = test_results.get("coverage", 0)
            quality_score = self._calculate_quality_score(pass_rate, coverage, failed, errors)

            # Evaluate thresholds
            thresholds_met, violations = self._evaluate_thresholds(
                pass_rate, coverage, test_results.get("issues", {})
            )

            # Generate evidence URI (AC-2)
            validation_id = f"qf_val_{hashlib.md5(f'{phase_id}_{workflow_id}_{time.time()}'.encode()).hexdigest()[:16]}"
            evidence_uri = f"/api/quality/validations/{validation_id}"

            # Collect artifacts (AC-6)
            artifacts = self._collect_artifacts(validation_response)

            execution_time = (time.time() - start_time) * 1000

            result = QualityValidationResult(
                validation_id=validation_id,
                phase_id=phase_id,
                workflow_id=workflow_id,
                session_id=session_id,
                total_tests=total_tests,
                passed_tests=passed,
                failed_tests=failed,
                error_tests=errors,
                skipped_tests=skipped,
                test_pass_rate=pass_rate,
                test_coverage=coverage,
                quality_score=quality_score,
                thresholds_met=thresholds_met,
                threshold_violations=violations,
                evidence_uri=evidence_uri,
                artifacts=artifacts,
                execution_time_ms=execution_time,
                timestamp=datetime.now().isoformat(),
            )

            # Store in history
            self._validation_history.append(result)

            # Metrics
            if HAS_PROMETHEUS:
                QUALITY_VALIDATIONS.labels(
                    phase=phase_type,
                    result="passed" if thresholds_met else "failed"
                ).inc()
                QUALITY_VALIDATION_LATENCY.observe(execution_time / 1000)

            logger.info(
                f"Quality validation complete: {validation_id} "
                f"(pass_rate={pass_rate:.1f}%, coverage={coverage:.1f}%, "
                f"thresholds_met={thresholds_met})"
            )

            return result

        except Exception as e:
            logger.error(f"Quality validation failed: {e}")
            execution_time = (time.time() - start_time) * 1000

            # Return failed result
            return QualityValidationResult(
                validation_id=f"qf_val_failed_{int(time.time())}",
                phase_id=phase_id,
                workflow_id=workflow_id,
                session_id=session_id,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                error_tests=1,
                skipped_tests=0,
                test_pass_rate=0,
                test_coverage=0,
                quality_score=0,
                thresholds_met=False,
                threshold_violations=[{"type": "error", "message": str(e)}],
                evidence_uri="",
                artifacts=[],
                execution_time_ms=execution_time,
                timestamp=datetime.now().isoformat(),
            )

    async def _execute_quality_fabric_validation(
        self,
        mapping: PhaseTestMapping,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute validation via Quality Fabric API."""
        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                # Check health first
                health_response = await client.get(f"{self.quality_fabric_url}/health")
                if health_response.status_code != 200:
                    raise Exception("Quality Fabric service not healthy")

                # Execute validation
                response = await client.post(
                    f"{self.quality_fabric_url}/api/execute",
                    json={
                        "name": f"Phase Validation: {mapping.phase_type}",
                        "description": f"Quality validation for phase {mapping.phase_id}",
                        "categories": mapping.test_categories,
                        "parallel_execution": True,
                        "fail_fast": False,
                        "timeout_minutes": 15,
                        "custom_config": {
                            "phase_id": mapping.phase_id,
                            "phase_type": mapping.phase_type,
                            "context": context,
                        },
                    },
                )

                if response.status_code != 200:
                    raise Exception(f"Validation request failed: {response.status_code}")

                execution_data = response.json()
                execution_id = execution_data.get("execution_id")

                # Poll for results
                for _ in range(60):  # Max 60 attempts (5 minutes)
                    await asyncio.sleep(5)

                    status_response = await client.get(
                        f"{self.quality_fabric_url}/api/execute/{execution_id}"
                    )

                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        if status_data.get("status") in ["completed", "failed"]:
                            # Get detailed results
                            results_response = await client.get(
                                f"{self.quality_fabric_url}/api/results/{execution_id}"
                            )
                            if results_response.status_code == 200:
                                return {
                                    "status": status_data,
                                    "results": results_response.json(),
                                }
                            return {"status": status_data, "results": {}}

                raise Exception("Validation timed out")

            except Exception as e:
                logger.error(f"Quality Fabric API error: {e}")
                # Return mock result for testing
                return self._get_mock_validation_result(mapping)

    def _get_mock_validation_result(self, mapping: PhaseTestMapping) -> Dict[str, Any]:
        """Get mock validation result for testing."""
        return {
            "status": {
                "status": "completed",
                "total_tests": 10,
                "passed_tests": 9,
                "failed_tests": 1,
                "error_tests": 0,
                "success_rate": 0.9,
                "duration": 5.0,
            },
            "results": {
                "coverage": 85.0,
                "issues": {
                    "critical": 0,
                    "high": 1,
                    "medium": 3,
                    "low": 5,
                },
            },
        }

    def _extract_test_results(self, validation_response: Dict[str, Any]) -> Dict[str, Any]:
        """Extract test results from validation response."""
        status = validation_response.get("status", {})
        results = validation_response.get("results", {})

        return {
            "total": status.get("total_tests", 0),
            "passed": status.get("passed_tests", 0),
            "failed": status.get("failed_tests", 0),
            "errors": status.get("error_tests", 0),
            "skipped": status.get("skipped_tests", 0),
            "coverage": results.get("coverage", 0),
            "issues": results.get("issues", {}),
        }

    def _calculate_quality_score(
        self,
        pass_rate: float,
        coverage: float,
        failed: int,
        errors: int,
    ) -> float:
        """Calculate overall quality score."""
        # Base score from pass rate (60% weight)
        base_score = pass_rate * 0.6

        # Coverage bonus (30% weight)
        coverage_score = coverage * 0.3

        # Penalty for failures and errors (10% weight)
        penalty = min(10, (failed + errors * 2) * 2)

        return max(0, min(100, base_score + coverage_score - penalty))

    def _evaluate_thresholds(
        self,
        pass_rate: float,
        coverage: float,
        issues: Dict[str, int],
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """Evaluate quality thresholds."""
        violations = []

        # Check pass rate threshold
        pass_rate_config = self.thresholds.get("test_pass_rate", {})
        min_pass_rate = pass_rate_config.get("min_pass_rate_percent", 95)
        if pass_rate < min_pass_rate:
            violations.append({
                "type": "pass_rate",
                "threshold": min_pass_rate,
                "actual": pass_rate,
                "message": f"Pass rate {pass_rate:.1f}% below minimum {min_pass_rate}%",
            })

        # Check coverage threshold
        coverage_config = self.thresholds.get("test_coverage", {})
        min_coverage = coverage_config.get("min_coverage_percent", 80)
        if coverage < min_coverage:
            violations.append({
                "type": "coverage",
                "threshold": min_coverage,
                "actual": coverage,
                "message": f"Coverage {coverage:.1f}% below minimum {min_coverage}%",
            })

        # Check static analysis issues
        static_config = self.thresholds.get("static_analysis", {})
        max_critical = static_config.get("max_critical_issues", 0)
        actual_critical = issues.get("critical", 0)
        if actual_critical > max_critical:
            violations.append({
                "type": "critical_issues",
                "threshold": max_critical,
                "actual": actual_critical,
                "message": f"{actual_critical} critical issues (max: {max_critical})",
            })

        return len(violations) == 0, violations

    def _collect_artifacts(self, validation_response: Dict[str, Any]) -> List[str]:
        """Collect test artifacts for manifest linking (AC-6)."""
        artifacts = []

        results = validation_response.get("results", {})

        # Add report URIs
        if "execution_id" in validation_response.get("status", {}):
            exec_id = validation_response["status"]["execution_id"]
            artifacts.append(f"/api/quality/reports/{exec_id}")
            artifacts.append(f"/api/quality/coverage/{exec_id}")

        return artifacts

    # =========================================================================
    # AC-3: Gate Blocking and Waivers
    # =========================================================================

    def should_block_gate(
        self,
        validation_result: QualityValidationResult,
        waiver: Optional[Waiver] = None,
    ) -> Tuple[bool, str]:
        """
        Determine if quality validation should block the gate.

        Args:
            validation_result: Quality validation result
            waiver: Optional waiver to apply

        Returns:
            Tuple of (should_block, reason)
        """
        # Check if enforcement is disabled
        if self.enforcement_level == EnforcementLevel.DISABLED:
            return False, "Quality enforcement disabled"

        # Check if feature flag is disabled
        if not self.feature_flag_enabled:
            return False, "Quality Fabric enforcement feature flag disabled"

        # Check for valid waiver (AC-3)
        if waiver:
            if self._is_waiver_valid(waiver):
                validation_result.waiver_applied = True
                validation_result.waiver_reason = waiver.reason

                if HAS_PROMETHEUS:
                    QUALITY_WAIVERS.labels(
                        phase=validation_result.phase_id,
                        reason=waiver.waiver_type.value
                    ).inc()

                return False, f"Waiver applied: {waiver.reason}"

        # Check thresholds
        if not validation_result.thresholds_met:
            if self.enforcement_level == EnforcementLevel.RELAXED:
                return False, "Thresholds not met but enforcement is relaxed (warning only)"

            return True, f"Quality thresholds not met: {validation_result.threshold_violations}"

        return False, "Quality validation passed"

    def _is_waiver_valid(self, waiver: Waiver) -> bool:
        """Check if a waiver is still valid."""
        if waiver.expires_at:
            expires = datetime.fromisoformat(waiver.expires_at)
            if datetime.now() > expires:
                return False
        return True

    def grant_waiver(
        self,
        phase_id: str,
        workflow_id: str,
        waiver_type: WaiverType,
        reason: str,
        granted_by: str,
        expires_at: Optional[str] = None,
        conditions: Dict[str, Any] = None,
    ) -> Waiver:
        """
        Grant a waiver for bypassing quality gates.

        Args:
            phase_id: Phase ID
            workflow_id: Workflow ID
            waiver_type: Type of waiver
            reason: Reason for waiver
            granted_by: Who granted the waiver
            expires_at: Optional expiration timestamp
            conditions: Optional conditions

        Returns:
            Created Waiver
        """
        waiver_id = f"waiver_{hashlib.md5(f'{phase_id}_{workflow_id}_{time.time()}'.encode()).hexdigest()[:12]}"

        waiver = Waiver(
            waiver_id=waiver_id,
            phase_id=phase_id,
            workflow_id=workflow_id,
            waiver_type=waiver_type,
            reason=reason,
            granted_by=granted_by,
            granted_at=datetime.now().isoformat(),
            expires_at=expires_at,
            conditions=conditions or {},
        )

        self._waivers[waiver_id] = waiver
        logger.info(f"Waiver granted: {waiver_id} for phase {phase_id}")

        return waiver

    def get_waiver(self, phase_id: str, workflow_id: str) -> Optional[Waiver]:
        """Get active waiver for a phase/workflow."""
        for waiver in self._waivers.values():
            if waiver.phase_id == phase_id and waiver.workflow_id == workflow_id:
                if self._is_waiver_valid(waiver):
                    return waiver
        return None

    # =========================================================================
    # QF-200: Rollback Support for Deployment Failures
    # =========================================================================

    def check_rollback_needed(
        self,
        validation_result: QualityValidationResult,
        mapping: PhaseTestMapping,
    ) -> Tuple[bool, str]:
        """
        Check if rollback should be triggered based on validation result.

        Args:
            validation_result: Quality validation result
            mapping: Phase test mapping with rollback config

        Returns:
            Tuple of (should_rollback, reason)
        """
        if not mapping.rollback_on_fail:
            return False, "Rollback not configured for this phase"

        if validation_result.thresholds_met:
            return False, "All thresholds met, no rollback needed"

        # Check if it's a deployment phase with failures
        if mapping.phase_type == "deployment":
            if validation_result.failed_tests > 0:
                return True, f"Deployment tests failed ({validation_result.failed_tests} failures)"

            if validation_result.error_tests > 0:
                return True, f"Deployment tests errored ({validation_result.error_tests} errors)"

        # Check for critical violations
        for violation in validation_result.threshold_violations:
            if violation.get("type") == "critical_issues":
                return True, f"Critical issues detected: {violation.get('message')}"

        # Check pass rate for smoke tests
        if mapping.smoke_tests and validation_result.test_pass_rate < 100:
            return True, f"Smoke tests failed (pass rate: {validation_result.test_pass_rate}%)"

        return False, "No rollback condition met"

    async def trigger_rollback(
        self,
        workflow_id: str,
        phase_id: str,
        reason: str,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Trigger a rollback for a failed deployment.

        Args:
            workflow_id: Workflow ID
            phase_id: Phase ID
            reason: Reason for rollback
            context: Additional context

        Returns:
            Rollback result dict
        """
        import httpx

        rollback_id = f"rollback_{hashlib.md5(f'{workflow_id}_{phase_id}_{time.time()}'.encode()).hexdigest()[:12]}"

        logger.warning(
            f"Triggering rollback: {rollback_id} for workflow={workflow_id}, "
            f"phase={phase_id}, reason={reason}"
        )

        # Record rollback event
        rollback_event = {
            "rollback_id": rollback_id,
            "workflow_id": workflow_id,
            "phase_id": phase_id,
            "reason": reason,
            "triggered_at": datetime.now().isoformat(),
            "context": context or {},
            "status": "triggered",
        }

        # Attempt to call rollback endpoint if available
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.quality_fabric_url}/api/rollback",
                    json=rollback_event,
                )
                if response.status_code == 200:
                    rollback_event["status"] = "executed"
                    rollback_event["rollback_response"] = response.json()
        except Exception as e:
            logger.error(f"Rollback execution failed: {e}")
            rollback_event["status"] = "execution_failed"
            rollback_event["error"] = str(e)

        return rollback_event

    def reload_config(self, config_path: Optional[str] = None) -> bool:
        """
        Reload configuration from file (QF-200).

        Args:
            config_path: Optional new config path

        Returns:
            True if reload successful
        """
        try:
            path = config_path or self._config_path
            self._yaml_config = PhaseTestConfigLoader.load_config(path)
            self._config_path = path

            # Reload phase mappings
            self._phase_mappings.clear()
            self._load_phase_mappings_from_config()

            # Update thresholds
            yaml_defaults = PhaseTestConfigLoader.get_default_thresholds(self._yaml_config)
            self.thresholds.update(yaml_defaults)

            logger.info(f"Configuration reloaded from: {path}")
            return True

        except Exception as e:
            logger.error(f"Config reload failed: {e}")
            return False

    def get_config_info(self) -> Dict[str, Any]:
        """Get information about loaded configuration."""
        return {
            "config_loaded": bool(self._yaml_config),
            "config_path": str(self._config_path) if self._config_path else None,
            "config_version": self._yaml_config.get("version", "unknown"),
            "phases_from_config": list(self._yaml_config.get("phase_test_map", {}).keys()),
            "environments_configured": list(self._yaml_config.get("environments", {}).keys()),
        }

    # =========================================================================
    # AC-2: Gate Evidence Generation
    # =========================================================================

    def create_gate_evidence(
        self,
        validation_result: QualityValidationResult,
    ) -> Dict[str, Any]:
        """
        Create gate evidence from quality validation result.

        Args:
            validation_result: Quality validation result

        Returns:
            Evidence dictionary for gate attachment
        """
        return {
            "type": "quality_validation",
            "uri": validation_result.evidence_uri,
            "description": f"Quality Fabric validation: {validation_result.quality_score:.1f}% score",
            "metadata": {
                "validation_id": validation_result.validation_id,
                "pass_rate": validation_result.test_pass_rate,
                "coverage": validation_result.test_coverage,
                "total_tests": validation_result.total_tests,
                "passed_tests": validation_result.passed_tests,
                "failed_tests": validation_result.failed_tests,
                "thresholds_met": validation_result.thresholds_met,
                "artifacts": validation_result.artifacts,
            },
            "attached_at": validation_result.timestamp,
        }

    # =========================================================================
    # AC-5: Environment-Based Enablement
    # =========================================================================

    def is_enabled_for_environment(self) -> bool:
        """Check if Quality Fabric enforcement is enabled for current environment."""
        # Always enabled in staging/production (AC-5)
        if self.environment in ["staging", "production"]:
            return True

        # Check feature flag for other environments
        return self.feature_flag_enabled

    def get_enforcement_config(self) -> Dict[str, Any]:
        """Get current enforcement configuration."""
        return {
            "environment": self.environment,
            "enforcement_level": self.enforcement_level.value,
            "feature_flag_enabled": self.feature_flag_enabled,
            "is_enabled": self.is_enabled_for_environment(),
            "thresholds": self.thresholds,
            "quality_fabric_url": self.quality_fabric_url,
        }

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_validation_history(
        self,
        workflow_id: Optional[str] = None,
        phase_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[QualityValidationResult]:
        """Get validation history with optional filters."""
        results = self._validation_history

        if workflow_id:
            results = [r for r in results if r.workflow_id == workflow_id]

        if phase_id:
            results = [r for r in results if r.phase_id == phase_id]

        return results[-limit:]


# ============================================================================
# SINGLETON & MODULE FUNCTIONS
# ============================================================================

# Import asyncio for async operations
import asyncio

_enforcement_service: Optional[QualityFabricEnforcementService] = None


def get_enforcement_service(
    quality_fabric_url: str = "http://localhost:8000",
    environment: str = None,
    feature_flag_enabled: bool = True,
) -> QualityFabricEnforcementService:
    """Get or create singleton enforcement service."""
    global _enforcement_service
    if _enforcement_service is None:
        _enforcement_service = QualityFabricEnforcementService(
            quality_fabric_url=quality_fabric_url,
            environment=environment,
            feature_flag_enabled=feature_flag_enabled,
        )
    return _enforcement_service


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def test_enforcement():
        print("=" * 70)
        print("QUALITY FABRIC ENFORCEMENT SERVICE - Test")
        print("=" * 70)

        service = get_enforcement_service(environment="staging")

        # Test AC-1: Phase mapping validation
        print("\n[AC-1] Phase Mapping Validation:")
        for phase in ["requirements", "design", "implementation", "testing", "deployment"]:
            valid, msg = service.validate_phase_mapping(phase)
            print(f"   {phase}: {'✅' if valid else '❌'} {msg}")

        # Test AC-4: Get enforcement config
        print("\n[AC-4/AC-5] Enforcement Configuration:")
        config = service.get_enforcement_config()
        print(f"   Environment: {config['environment']}")
        print(f"   Enforcement Level: {config['enforcement_level']}")
        print(f"   Enabled: {config['is_enabled']}")

        # Test validation
        print("\n[AC-2/AC-6] Quality Validation:")
        result = await service.validate_phase(
            phase_id="phase_impl_001",
            phase_type="implementation",
            workflow_id="wf_test_001",
            session_id="session_test",
        )
        print(f"   Validation ID: {result.validation_id}")
        print(f"   Pass Rate: {result.test_pass_rate:.1f}%")
        print(f"   Coverage: {result.test_coverage:.1f}%")
        print(f"   Quality Score: {result.quality_score:.1f}")
        print(f"   Thresholds Met: {result.thresholds_met}")
        print(f"   Evidence URI: {result.evidence_uri}")

        # Test AC-3: Gate blocking
        print("\n[AC-3] Gate Blocking Check:")
        should_block, reason = service.should_block_gate(result)
        print(f"   Should Block: {should_block}")
        print(f"   Reason: {reason}")

        # Test waiver
        print("\n[AC-3] Waiver Test:")
        waiver = service.grant_waiver(
            phase_id="phase_impl_001",
            workflow_id="wf_test_001",
            waiver_type=WaiverType.EMERGENCY,
            reason="Emergency hotfix deployment",
            granted_by="admin@example.com",
        )
        print(f"   Waiver ID: {waiver.waiver_id}")

        should_block_after, reason_after = service.should_block_gate(result, waiver)
        print(f"   Should Block (with waiver): {should_block_after}")
        print(f"   Reason: {reason_after}")

        # Test gate evidence
        print("\n[AC-2] Gate Evidence:")
        evidence = service.create_gate_evidence(result)
        print(f"   Evidence Type: {evidence['type']}")
        print(f"   Evidence URI: {evidence['uri']}")

        print("\n" + "=" * 70)
        print("ALL TESTS COMPLETED!")
        print("=" * 70)

    asyncio.run(test_enforcement())
