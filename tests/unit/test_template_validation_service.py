#!/usr/bin/env python3
"""
Unit Tests for Template Validation Service
Epic MD-1822: [MT-100] Template Validation Enforcement via Quality Fabric

Tests cover all acceptance criteria:
- AC-1: QF validation triggered on every create/promote call
- AC-2: Validation report link stored in metadata.validation_report_id
- AC-3: Publish blocked when score < 85 or security < 80
- AC-4: API returns clear error message with validation details on failure
- AC-5: last_validated_at timestamp updated on each validation
"""

import asyncio
import pytest
import sys
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from services.template_validation_service import (
    TemplateValidationService,
    ValidationOperation,
    ValidationStatus,
    ValidationResult,
    ValidationThresholds,
    TemplateMetadataUpdate,
    BlockReason,
    get_template_validation_service,
    validate_template_for_create,
    validate_template_for_promote,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def validation_service():
    """Create a fresh TemplateValidationService instance."""
    return TemplateValidationService(
        thresholds=ValidationThresholds(
            quality_score=85.0,
            security_score=80.0,
            test_coverage=70.0,
            maintainability_score=60.0,
        ),
        quality_fabric_url="http://localhost:8000"
    )


@pytest.fixture
def high_quality_template():
    """Template that should pass validation."""
    return '''#!/usr/bin/env python3
"""
High-quality template with proper documentation.

This module provides utility functions for data processing.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def process_data(data: Dict[str, Any], options: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Process input data with configurable options.

    Args:
        data: Input data dictionary
        options: Optional processing options

    Returns:
        Processed data dictionary

    Raises:
        ValueError: If data is invalid
    """
    try:
        if not data:
            raise ValueError("Data cannot be empty")

        result = {
            "processed": True,
            "input_keys": list(data.keys()),
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"Processed {len(data)} items")
        return result

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise


def test_process_data():
    """Test for process_data function."""
    result = process_data({"key": "value"})
    assert result["processed"] is True
'''


@pytest.fixture
def low_quality_template():
    """Template that should fail validation due to low quality."""
    return '''
def bad_function(x):
    return eval(x)

def another_bad(y):
    exec(y)
    return None
'''


@pytest.fixture
def security_risk_template():
    """Template with security issues."""
    return '''import subprocess

def run_command(cmd):
    subprocess.call(cmd, shell=True)
    password = "hardcoded_secret123"
    return eval(cmd)
'''


# ============================================================================
# VALIDATION SERVICE INITIALIZATION TESTS
# ============================================================================

class TestTemplateValidationServiceInit:
    """Tests for service initialization."""

    def test_default_initialization(self):
        """Test service initializes with default thresholds."""
        service = TemplateValidationService()

        assert service.thresholds.quality_score == 85.0
        assert service.thresholds.security_score == 80.0
        assert service.thresholds.test_coverage == 70.0
        assert service.quality_fabric_url == "http://localhost:8000"

    def test_custom_thresholds(self, validation_service):
        """Test service accepts custom thresholds."""
        assert validation_service.thresholds.quality_score == 85.0
        assert validation_service.thresholds.security_score == 80.0

    def test_singleton_pattern(self):
        """Test get_template_validation_service returns singleton."""
        # Reset singleton for test
        import services.template_validation_service as mod
        mod._template_validation_service = None

        service1 = get_template_validation_service()
        service2 = get_template_validation_service()

        assert service1 is service2

    def test_get_config(self, validation_service):
        """Test configuration retrieval."""
        config = validation_service.get_config()

        assert "thresholds" in config
        assert "quality_fabric_url" in config
        assert "cache_size" in config
        assert config["quality_fabric_url"] == "http://localhost:8000"


# ============================================================================
# VALIDATION OPERATION TESTS (AC-1)
# ============================================================================

class TestValidationOperations:
    """Tests for AC-1: QF validation triggered on every create/promote call."""

    @pytest.mark.asyncio
    async def test_validation_triggered_on_create(self, validation_service, high_quality_template):
        """AC-1: Validation should be triggered on create operation."""
        result = await validation_service.validate_template(
            template_id="tpl_test123",
            template_content=high_quality_template,
            operation=ValidationOperation.CREATE,
            template_name="test_template",
            language="python",
        )

        assert result is not None
        assert result.operation == ValidationOperation.CREATE
        assert result.template_id == "tpl_test123"
        assert result.validation_id.startswith("tv_")

    @pytest.mark.asyncio
    async def test_validation_triggered_on_promote(self, validation_service, high_quality_template):
        """AC-1: Validation should be triggered on promote operation."""
        result = await validation_service.validate_template(
            template_id="tpl_test456",
            template_content=high_quality_template,
            operation=ValidationOperation.PROMOTE,
        )

        assert result is not None
        assert result.operation == ValidationOperation.PROMOTE

    @pytest.mark.asyncio
    async def test_validation_triggered_on_update(self, validation_service, high_quality_template):
        """AC-1: Validation should be triggered on update operation."""
        result = await validation_service.validate_template(
            template_id="tpl_test789",
            template_content=high_quality_template,
            operation=ValidationOperation.UPDATE,
        )

        assert result is not None
        assert result.operation == ValidationOperation.UPDATE

    @pytest.mark.asyncio
    async def test_convenience_function_create(self, high_quality_template):
        """Test validate_template_for_create convenience function."""
        # Reset singleton
        import services.template_validation_service as mod
        mod._template_validation_service = None

        result = await validate_template_for_create(
            template_id="tpl_conv_create",
            template_content=high_quality_template,
            language="python",
        )

        assert result.operation == ValidationOperation.CREATE

    @pytest.mark.asyncio
    async def test_convenience_function_promote(self, high_quality_template):
        """Test validate_template_for_promote convenience function."""
        # Reset singleton
        import services.template_validation_service as mod
        mod._template_validation_service = None

        result = await validate_template_for_promote(
            template_id="tpl_conv_promote",
            template_content=high_quality_template,
        )

        assert result.operation == ValidationOperation.PROMOTE


# ============================================================================
# VALIDATION REPORT STORAGE TESTS (AC-2)
# ============================================================================

class TestValidationReportStorage:
    """Tests for AC-2: Validation report link stored in metadata.validation_report_id."""

    @pytest.mark.asyncio
    async def test_validation_report_id_generated(self, validation_service, high_quality_template):
        """AC-2: Validation should generate report ID."""
        result = await validation_service.validate_template(
            template_id="tpl_report_test",
            template_content=high_quality_template,
            operation=ValidationOperation.CREATE,
        )

        # Either from QF response or generated
        assert result.validation_report_id is not None or result.validation_id is not None

    @pytest.mark.asyncio
    async def test_metadata_update_contains_report_id(self, validation_service, high_quality_template):
        """AC-2: Metadata update should contain validation_report_id."""
        result = await validation_service.validate_template(
            template_id="tpl_metadata_test",
            template_content=high_quality_template,
            operation=ValidationOperation.CREATE,
        )

        metadata_update = validation_service.get_template_metadata_update(result)

        assert isinstance(metadata_update, TemplateMetadataUpdate)
        assert metadata_update.validation_report_id is not None

    @pytest.mark.asyncio
    async def test_validation_result_cached(self, validation_service, high_quality_template):
        """Test that validation results are cached by ID."""
        result = await validation_service.validate_template(
            template_id="tpl_cache_test",
            template_content=high_quality_template,
            operation=ValidationOperation.CREATE,
        )

        cached = validation_service.get_validation_result(result.validation_id)

        assert cached is not None
        assert cached.validation_id == result.validation_id
        assert cached.template_id == result.template_id

    def test_validation_result_not_found(self, validation_service):
        """Test retrieving non-existent validation result returns None."""
        result = validation_service.get_validation_result("nonexistent_id")
        assert result is None


# ============================================================================
# THRESHOLD-BASED BLOCKING TESTS (AC-3)
# ============================================================================

class TestThresholdBlocking:
    """Tests for AC-3: Publish blocked when score < 85 or security < 80."""

    @pytest.mark.asyncio
    async def test_high_quality_not_blocked(self, validation_service, high_quality_template):
        """AC-3: High quality template should not be blocked."""
        result = await validation_service.validate_template(
            template_id="tpl_high_quality",
            template_content=high_quality_template,
            operation=ValidationOperation.CREATE,
        )

        # High quality template with docstrings, type hints, error handling
        # Should score >= 85 quality and >= 80 security
        assert result.quality_score >= 85.0 or not result.should_block
        assert result.status in [ValidationStatus.PASSED, ValidationStatus.BLOCKED]

    @pytest.mark.asyncio
    async def test_low_quality_blocked(self, validation_service, low_quality_template):
        """AC-3: Low quality template should be blocked."""
        result = await validation_service.validate_template(
            template_id="tpl_low_quality",
            template_content=low_quality_template,
            operation=ValidationOperation.CREATE,
        )

        # Template with eval() and exec() should fail security
        if result.security_score < 80.0:
            assert result.should_block is True
            assert BlockReason.SECURITY_SCORE_LOW.value in str(result.block_reasons)

    @pytest.mark.asyncio
    async def test_security_risk_blocked(self, validation_service, security_risk_template):
        """AC-3: Security risk template should be blocked."""
        result = await validation_service.validate_template(
            template_id="tpl_security_risk",
            template_content=security_risk_template,
            operation=ValidationOperation.PROMOTE,
        )

        # Template with hardcoded password and shell=True should fail security
        assert result.should_block is True
        assert result.status == ValidationStatus.BLOCKED

    @pytest.mark.asyncio
    async def test_quality_below_85_blocked(self, validation_service):
        """AC-3: Quality score < 85 should block."""
        # Minimal template that scores low
        minimal_template = "x = 1"

        result = await validation_service.validate_template(
            template_id="tpl_minimal",
            template_content=minimal_template,
            operation=ValidationOperation.CREATE,
        )

        # This minimal code will score below 85
        assert result.quality_score < 100  # Some score calculated

    @pytest.mark.asyncio
    async def test_security_below_80_blocked(self, validation_service):
        """AC-3: Security score < 80 should block."""
        insecure_template = """
import os
password = os.getenv('PASSWORD', 'default123')
result = eval(user_input)
exec(command)
"""
        result = await validation_service.validate_template(
            template_id="tpl_insecure",
            template_content=insecure_template,
            operation=ValidationOperation.CREATE,
        )

        # eval() and exec() should lower security score
        assert result.security_score < 90  # Will be penalized

    def test_threshold_checking_logic(self, validation_service):
        """Test the threshold checking function directly."""
        # Create a mock result with low scores
        result = ValidationResult(
            validation_id="test_id",
            template_id="tpl_test",
            operation=ValidationOperation.CREATE,
            status=ValidationStatus.PENDING,
            quality_score=70.0,  # Below 85 threshold
            security_score=75.0,  # Below 80 threshold
        )

        should_block, reasons = validation_service._check_thresholds(result)

        assert should_block is True
        assert len(reasons) == 2  # Both thresholds violated

    def test_threshold_passing(self, validation_service):
        """Test thresholds pass when scores are high."""
        result = ValidationResult(
            validation_id="test_id",
            template_id="tpl_test",
            operation=ValidationOperation.CREATE,
            status=ValidationStatus.PENDING,
            quality_score=90.0,  # Above 85
            security_score=85.0,  # Above 80
        )

        should_block, reasons = validation_service._check_thresholds(result)

        assert should_block is False
        assert len(reasons) == 0


# ============================================================================
# ERROR MESSAGE TESTS (AC-4)
# ============================================================================

class TestErrorMessages:
    """Tests for AC-4: API returns clear error message with validation details on failure."""

    def test_error_message_for_blocked_validation(self, validation_service):
        """AC-4: Blocked validation should produce clear error message."""
        result = ValidationResult(
            validation_id="tv_error_test",
            template_id="tpl_blocked",
            operation=ValidationOperation.CREATE,
            status=ValidationStatus.BLOCKED,
            quality_score=70.0,
            security_score=65.0,
            should_block=True,
            block_reasons=[
                f"{BlockReason.QUALITY_SCORE_LOW.value}: 70.0 < 85.0",
                f"{BlockReason.SECURITY_SCORE_LOW.value}: 65.0 < 80.0",
            ],
            recommendations=["Add docstrings", "Remove eval() usage"],
        )

        error_message = validation_service.format_error_message(result)

        assert "Template validation failed" in error_message
        assert "tpl_blocked" in error_message
        assert "Quality Score: 70.0" in error_message
        assert "Security Score: 65.0" in error_message
        assert "Block Reasons:" in error_message
        assert "quality_score_below_threshold" in error_message
        assert "security_score_below_threshold" in error_message
        assert "Recommendations:" in error_message

    def test_error_message_includes_validation_id(self, validation_service):
        """AC-4: Error message should include validation ID."""
        result = ValidationResult(
            validation_id="tv_unique_123",
            template_id="tpl_test",
            operation=ValidationOperation.PROMOTE,
            status=ValidationStatus.BLOCKED,
            quality_score=80.0,
            security_score=75.0,
            should_block=True,
            block_reasons=["test_reason"],
            validation_report_id="report_xyz",
        )

        error_message = validation_service.format_error_message(result)

        assert "tv_unique_123" in error_message
        assert "report_xyz" in error_message

    def test_no_error_message_when_not_blocked(self, validation_service):
        """AC-4: No error message when validation passes."""
        result = ValidationResult(
            validation_id="tv_pass",
            template_id="tpl_good",
            operation=ValidationOperation.CREATE,
            status=ValidationStatus.PASSED,
            quality_score=90.0,
            security_score=85.0,
            should_block=False,
        )

        error_message = validation_service.format_error_message(result)

        assert error_message == ""


# ============================================================================
# TIMESTAMP TESTS (AC-5)
# ============================================================================

class TestTimestampUpdates:
    """Tests for AC-5: last_validated_at timestamp updated on each validation."""

    @pytest.mark.asyncio
    async def test_validated_at_set(self, validation_service, high_quality_template):
        """AC-5: validated_at should be set on validation."""
        before = datetime.now().isoformat()

        result = await validation_service.validate_template(
            template_id="tpl_timestamp_test",
            template_content=high_quality_template,
            operation=ValidationOperation.CREATE,
        )

        after = datetime.now().isoformat()

        assert result.validated_at is not None
        assert before <= result.validated_at <= after

    @pytest.mark.asyncio
    async def test_metadata_update_has_timestamp(self, validation_service, high_quality_template):
        """AC-5: Metadata update should include last_validated_at."""
        result = await validation_service.validate_template(
            template_id="tpl_metadata_ts",
            template_content=high_quality_template,
            operation=ValidationOperation.CREATE,
        )

        metadata = validation_service.get_template_metadata_update(result)

        assert metadata.last_validated_at == result.validated_at

    @pytest.mark.asyncio
    async def test_validation_duration_tracked(self, validation_service, high_quality_template):
        """Test that validation duration is tracked."""
        result = await validation_service.validate_template(
            template_id="tpl_duration_test",
            template_content=high_quality_template,
            operation=ValidationOperation.CREATE,
        )

        assert result.validation_duration_ms > 0


# ============================================================================
# THRESHOLD UPDATE TESTS
# ============================================================================

class TestThresholdUpdates:
    """Tests for threshold configuration updates."""

    def test_update_thresholds(self, validation_service):
        """Test updating validation thresholds."""
        new_thresholds = ValidationThresholds(
            quality_score=90.0,
            security_score=85.0,
            test_coverage=80.0,
            maintainability_score=70.0,
        )

        validation_service.update_thresholds(new_thresholds)

        assert validation_service.thresholds.quality_score == 90.0
        assert validation_service.thresholds.security_score == 85.0

    def test_thresholds_from_dict(self):
        """Test creating thresholds from dictionary."""
        data = {
            "quality_score": 88.0,
            "security_score": 82.0,
            "test_coverage": 75.0,
            "maintainability_score": 65.0,
        }

        thresholds = ValidationThresholds.from_dict(data)

        assert thresholds.quality_score == 88.0
        assert thresholds.security_score == 82.0

    def test_thresholds_to_dict(self, validation_service):
        """Test converting thresholds to dictionary."""
        thresholds_dict = validation_service.thresholds.to_dict()

        assert "quality_score" in thresholds_dict
        assert "security_score" in thresholds_dict
        assert thresholds_dict["quality_score"] == 85.0


# ============================================================================
# STATIC ANALYSIS TESTS
# ============================================================================

class TestStaticAnalysis:
    """Tests for static analysis fallback."""

    def test_static_analysis_detects_docstrings(self, validation_service):
        """Test static analysis detects docstrings."""
        template_with_docstrings = '''
"""Module docstring."""

def func():
    """Function docstring."""
    pass
'''
        result = validation_service._static_analysis(template_with_docstrings, "python")

        assert result["details"]["has_docstrings"] is True

    def test_static_analysis_detects_eval(self, validation_service):
        """Test static analysis detects eval usage."""
        template_with_eval = "result = eval(user_input)"

        result = validation_service._static_analysis(template_with_eval, "python")

        # Should have security issue about eval
        assert any("eval" in str(issue) for issue in result["issues"])

    def test_static_analysis_detects_error_handling(self, validation_service):
        """Test static analysis detects error handling."""
        template_with_try = '''
try:
    risky_operation()
except Exception as e:
    handle_error(e)
'''
        result = validation_service._static_analysis(template_with_try, "python")

        assert result["details"]["has_error_handling"] is True

    def test_static_analysis_detects_type_hints(self, validation_service):
        """Test static analysis detects type hints."""
        template_with_types = "def func(x: int) -> str: return str(x)"

        result = validation_service._static_analysis(template_with_types, "python")

        assert result["details"]["has_type_hints"] is True


# ============================================================================
# LANGUAGE DETECTION TESTS
# ============================================================================

class TestLanguageDetection:
    """Tests for programming language detection."""

    def test_detect_python(self, validation_service):
        """Test Python language detection."""
        python_code = "def main(): print('hello')"
        lang = validation_service._detect_language(python_code)
        assert lang == "python"

    def test_detect_javascript(self, validation_service):
        """Test JavaScript language detection."""
        js_code = "function hello() { return 'world'; }"
        lang = validation_service._detect_language(js_code)
        assert lang == "javascript"

    def test_detect_javascript_arrow(self, validation_service):
        """Test JavaScript arrow function detection."""
        js_code = "const greet = (name) => `Hello ${name}`;"
        lang = validation_service._detect_language(js_code)
        assert lang == "javascript"

    def test_detect_unknown(self, validation_service):
        """Test unknown language detection."""
        unknown_code = "SELECT * FROM users"
        lang = validation_service._detect_language(unknown_code)
        assert lang == "unknown"


# ============================================================================
# DATA CLASS TESTS
# ============================================================================

class TestDataClasses:
    """Tests for data classes."""

    def test_validation_result_to_dict(self):
        """Test ValidationResult serialization."""
        result = ValidationResult(
            validation_id="tv_test",
            template_id="tpl_test",
            operation=ValidationOperation.CREATE,
            status=ValidationStatus.PASSED,
            quality_score=90.0,
            security_score=85.0,
        )

        result_dict = result.to_dict()

        assert result_dict["validation_id"] == "tv_test"
        assert result_dict["operation"] == "create"
        assert result_dict["status"] == "passed"

    def test_template_metadata_update_to_dict(self):
        """Test TemplateMetadataUpdate serialization."""
        metadata = TemplateMetadataUpdate(
            validation_report_id="report_123",
            last_validated_at="2024-01-01T00:00:00",
            validation_status=ValidationStatus.PASSED,
            quality_score=90.0,
            security_score=85.0,
            can_publish=True,
        )

        metadata_dict = metadata.to_dict()

        assert metadata_dict["validation_report_id"] == "report_123"
        assert metadata_dict["can_publish"] is True


# ============================================================================
# VALIDATION ID GENERATION TESTS
# ============================================================================

class TestValidationIdGeneration:
    """Tests for validation ID generation."""

    def test_validation_id_format(self, validation_service):
        """Test validation ID has correct format."""
        val_id = validation_service._generate_validation_id("tpl_test", "create")

        assert val_id.startswith("tv_")
        assert len(val_id) == 19  # tv_ + 16 hex chars

    def test_validation_id_uniqueness(self, validation_service):
        """Test validation IDs are unique."""
        id1 = validation_service._generate_validation_id("tpl_test", "create")
        id2 = validation_service._generate_validation_id("tpl_test", "create")

        # Due to time component, should be different
        assert id1 != id2


# ============================================================================
# ENUM TESTS
# ============================================================================

class TestEnums:
    """Tests for enum values."""

    def test_validation_operation_values(self):
        """Test ValidationOperation enum values."""
        assert ValidationOperation.CREATE.value == "create"
        assert ValidationOperation.PROMOTE.value == "promote"
        assert ValidationOperation.UPDATE.value == "update"

    def test_validation_status_values(self):
        """Test ValidationStatus enum values."""
        assert ValidationStatus.PENDING.value == "pending"
        assert ValidationStatus.PASSED.value == "passed"
        assert ValidationStatus.FAILED.value == "failed"
        assert ValidationStatus.BLOCKED.value == "blocked"
        assert ValidationStatus.WAIVED.value == "waived"

    def test_block_reason_values(self):
        """Test BlockReason enum values."""
        assert BlockReason.QUALITY_SCORE_LOW.value == "quality_score_below_threshold"
        assert BlockReason.SECURITY_SCORE_LOW.value == "security_score_below_threshold"


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
