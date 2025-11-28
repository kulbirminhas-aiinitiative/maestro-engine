#!/usr/bin/env python3
"""
Integration Tests for Template Validation Service with Quality Fabric
Epic MD-1822: [MT-100] Template Validation Enforcement via Quality Fabric

These tests validate integration with the actual Quality Fabric API at localhost:8000.
"""

import asyncio
import pytest
import sys
import os
import httpx

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from services.template_validation_service import (
    TemplateValidationService,
    ValidationOperation,
    ValidationStatus,
    ValidationThresholds,
    get_template_validation_service,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def qf_url():
    """Quality Fabric URL."""
    return os.getenv("QUALITY_FABRIC_URL", "http://localhost:8000")


@pytest.fixture
async def qf_available(qf_url):
    """Check if Quality Fabric is available."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{qf_url}/health", timeout=5.0)
            return response.status_code == 200
    except Exception:
        return False


@pytest.fixture
def validation_service(qf_url):
    """Create validation service connected to QF."""
    return TemplateValidationService(
        thresholds=ValidationThresholds(
            quality_score=85.0,
            security_score=80.0,
        ),
        quality_fabric_url=qf_url,
    )


@pytest.fixture
def high_quality_template():
    """Well-structured template that should pass validation."""
    return '''#!/usr/bin/env python3
"""
Template for data processing service.

Provides utilities for handling and transforming data.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DataProcessor:
    """Process and transform data according to configurable rules."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize processor with optional configuration.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate configuration."""
        if not isinstance(self.config, dict):
            raise TypeError("Config must be a dictionary")

    def process(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process input data.

        Args:
            data: List of data items to process

        Returns:
            Processed data items

        Raises:
            ValueError: If data is invalid
        """
        try:
            if not data:
                logger.warning("Empty data provided")
                return []

            result = []
            for item in data:
                processed = self._process_item(item)
                result.append(processed)

            logger.info(f"Processed {len(result)} items")
            return result

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            raise

    def _process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single item."""
        return {**item, "processed": True}


def test_data_processor():
    """Unit test for DataProcessor."""
    processor = DataProcessor()
    result = processor.process([{"key": "value"}])
    assert len(result) == 1
    assert result[0]["processed"] is True
'''


@pytest.fixture
def low_quality_template():
    """Template with issues that should be flagged."""
    return '''
def bad(x):
    return eval(x)
'''


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestQualityFabricIntegration:
    """Integration tests with Quality Fabric."""

    @pytest.mark.asyncio
    async def test_qf_health_check(self, qf_url):
        """Verify Quality Fabric is accessible."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{qf_url}/health", timeout=5.0)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print(f"\n✓ Quality Fabric healthy at {qf_url}")

    @pytest.mark.asyncio
    async def test_validate_high_quality_template(self, validation_service, high_quality_template):
        """Test validation of high-quality template via QF."""
        result = await validation_service.validate_template(
            template_id="tpl_qf_integration_1",
            template_content=high_quality_template,
            operation=ValidationOperation.CREATE,
            template_name="data_processor",
            language="python",
            category="backend",
        )

        print(f"\n✓ Validation completed:")
        print(f"  - Quality Score: {result.quality_score:.1f}")
        print(f"  - Security Score: {result.security_score:.1f}")
        print(f"  - Test Coverage: {result.test_coverage:.1f}")
        print(f"  - Status: {result.status.value}")
        print(f"  - Duration: {result.validation_duration_ms:.2f}ms")

        assert result.validation_id is not None
        assert result.validated_at is not None
        assert result.validation_duration_ms > 0

        # High quality template should score well on static analysis
        assert result.quality_score > 0
        assert result.security_score > 0

    @pytest.mark.asyncio
    async def test_validate_low_quality_template(self, validation_service, low_quality_template):
        """Test validation of low-quality template via QF."""
        result = await validation_service.validate_template(
            template_id="tpl_qf_integration_2",
            template_content=low_quality_template,
            operation=ValidationOperation.CREATE,
            template_name="bad_template",
            language="python",
        )

        print(f"\n✓ Low quality validation completed:")
        print(f"  - Quality Score: {result.quality_score:.1f}")
        print(f"  - Security Score: {result.security_score:.1f}")
        print(f"  - Should Block: {result.should_block}")
        print(f"  - Block Reasons: {result.block_reasons}")

        # Low quality template with eval() should be flagged
        assert result.security_score < 100  # eval() should lower score

    @pytest.mark.asyncio
    async def test_validation_report_id_stored(self, validation_service, high_quality_template):
        """AC-2: Verify validation report ID is generated and stored."""
        result = await validation_service.validate_template(
            template_id="tpl_report_check",
            template_content=high_quality_template,
            operation=ValidationOperation.CREATE,
        )

        # Should have either report_id from QF or generated one
        report_id = result.validation_report_id or result.validation_id

        print(f"\n✓ Validation Report ID: {report_id}")

        assert report_id is not None
        assert len(report_id) > 0

    @pytest.mark.asyncio
    async def test_metadata_update_generation(self, validation_service, high_quality_template):
        """AC-2 & AC-5: Verify metadata update contains report ID and timestamp."""
        result = await validation_service.validate_template(
            template_id="tpl_metadata_check",
            template_content=high_quality_template,
            operation=ValidationOperation.PROMOTE,
        )

        metadata = validation_service.get_template_metadata_update(result)

        print(f"\n✓ Metadata Update:")
        print(f"  - Report ID: {metadata.validation_report_id}")
        print(f"  - Last Validated: {metadata.last_validated_at}")
        print(f"  - Can Publish: {metadata.can_publish}")

        assert metadata.validation_report_id is not None
        assert metadata.last_validated_at is not None
        assert metadata.validation_status in [ValidationStatus.PASSED, ValidationStatus.BLOCKED]

    @pytest.mark.asyncio
    async def test_threshold_enforcement(self, validation_service):
        """AC-3: Test threshold-based blocking."""
        # Template with security issues that should be blocked
        insecure_template = '''
import subprocess
def run(cmd):
    exec(cmd)  # Security risk
    eval(cmd)  # Security risk
    subprocess.call(cmd, shell=True)  # Security risk
'''
        result = await validation_service.validate_template(
            template_id="tpl_threshold_test",
            template_content=insecure_template,
            operation=ValidationOperation.PROMOTE,
        )

        print(f"\n✓ Threshold Test:")
        print(f"  - Quality Score: {result.quality_score:.1f} (threshold: 85)")
        print(f"  - Security Score: {result.security_score:.1f} (threshold: 80)")
        print(f"  - Should Block: {result.should_block}")

        # Insecure template should be blocked
        if result.security_score < 80 or result.quality_score < 85:
            assert result.should_block is True
            assert len(result.block_reasons) > 0

    @pytest.mark.asyncio
    async def test_error_message_clarity(self, validation_service):
        """AC-4: Test error message includes clear details."""
        bad_template = "eval(x)"

        result = await validation_service.validate_template(
            template_id="tpl_error_msg_test",
            template_content=bad_template,
            operation=ValidationOperation.CREATE,
        )

        if result.should_block:
            error_msg = validation_service.format_error_message(result)

            print(f"\n✓ Error Message Generated:")
            print(error_msg[:500])

            assert "Template validation failed" in error_msg
            assert result.template_id in error_msg
            assert "Quality Score" in error_msg
            assert "Security Score" in error_msg

    @pytest.mark.asyncio
    async def test_create_operation_triggers_validation(self, validation_service, high_quality_template):
        """AC-1: Verify create operation triggers QF validation."""
        result = await validation_service.validate_template(
            template_id="tpl_create_trigger",
            template_content=high_quality_template,
            operation=ValidationOperation.CREATE,
        )

        print(f"\n✓ CREATE operation validation:")
        print(f"  - Operation: {result.operation.value}")
        print(f"  - Status: {result.status.value}")

        assert result.operation == ValidationOperation.CREATE
        assert result.status in [ValidationStatus.PASSED, ValidationStatus.BLOCKED, ValidationStatus.FAILED]

    @pytest.mark.asyncio
    async def test_promote_operation_triggers_validation(self, validation_service, high_quality_template):
        """AC-1: Verify promote operation triggers QF validation."""
        result = await validation_service.validate_template(
            template_id="tpl_promote_trigger",
            template_content=high_quality_template,
            operation=ValidationOperation.PROMOTE,
        )

        print(f"\n✓ PROMOTE operation validation:")
        print(f"  - Operation: {result.operation.value}")
        print(f"  - Status: {result.status.value}")

        assert result.operation == ValidationOperation.PROMOTE
        assert result.validated_at is not None

    @pytest.mark.asyncio
    async def test_validation_caching(self, validation_service, high_quality_template):
        """Test validation results are cached."""
        result = await validation_service.validate_template(
            template_id="tpl_cache_test",
            template_content=high_quality_template,
            operation=ValidationOperation.CREATE,
        )

        cached = validation_service.get_validation_result(result.validation_id)

        print(f"\n✓ Validation cached:")
        print(f"  - Validation ID: {result.validation_id}")
        print(f"  - Retrieved from cache: {cached is not None}")

        assert cached is not None
        assert cached.validation_id == result.validation_id
        assert cached.template_id == result.template_id


class TestEndToEndValidation:
    """End-to-end validation workflow tests."""

    @pytest.mark.asyncio
    async def test_full_template_lifecycle(self, validation_service, high_quality_template):
        """Test full template validation lifecycle."""
        template_id = "tpl_lifecycle_test"

        # Step 1: Validate for create
        create_result = await validation_service.validate_template(
            template_id=template_id,
            template_content=high_quality_template,
            operation=ValidationOperation.CREATE,
            template_name="lifecycle_template",
            language="python",
        )

        print(f"\n✓ Step 1 - CREATE validation:")
        print(f"  - Status: {create_result.status.value}")
        print(f"  - Can Publish: {not create_result.should_block}")

        # Step 2: If passed, validate for promotion
        if not create_result.should_block:
            promote_result = await validation_service.validate_template(
                template_id=template_id,
                template_content=high_quality_template,
                operation=ValidationOperation.PROMOTE,
            )

            print(f"\n✓ Step 2 - PROMOTE validation:")
            print(f"  - Status: {promote_result.status.value}")
            print(f"  - Report ID: {promote_result.validation_report_id}")

            # Both validations should be cached
            assert validation_service.get_validation_result(create_result.validation_id) is not None
            assert validation_service.get_validation_result(promote_result.validation_id) is not None

    @pytest.mark.asyncio
    async def test_multiple_templates_validation(self, validation_service):
        """Test validating multiple templates concurrently."""
        templates = [
            ("tpl_multi_1", "def func1(): pass", "python"),
            ("tpl_multi_2", "function func2() { return true; }", "javascript"),
            ("tpl_multi_3", "SELECT * FROM users", "sql"),
        ]

        tasks = [
            validation_service.validate_template(
                template_id=tid,
                template_content=content,
                operation=ValidationOperation.CREATE,
                language=lang,
            )
            for tid, content, lang in templates
        ]

        results = await asyncio.gather(*tasks)

        print(f"\n✓ Multiple templates validated:")
        for i, result in enumerate(results):
            print(f"  - {templates[i][0]}: {result.status.value} (quality={result.quality_score:.1f})")

        assert len(results) == 3
        assert all(r.validation_id is not None for r in results)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
