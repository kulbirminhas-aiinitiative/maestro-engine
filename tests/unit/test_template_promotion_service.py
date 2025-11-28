#!/usr/bin/env python3
"""
Unit tests for Template Promotion Service
Tests for MD-1844: [ME-600-2] Implement Promotion Service Core

Test Coverage:
- AC-1: Criteria validation with configurable thresholds
- AC-2: Metadata extraction and enrichment
- AC-3: Semantic versioning calculation
- AC-4: Changelog generation
- AC-5: Quality Fabric integration
- AC-6: Feature flag check
"""

import os
import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock

import sys
sys.path.insert(0, str(__file__).replace('/tests/unit/test_template_promotion_service.py', '/src'))

from services.template_promotion_service import (
    TemplatePromotionService,
    PromotionThresholds,
    TemplateMetadata,
    ChangelogEntry,
    Changelog,
    PromotionCriteria,
    PromotionResult,
    PromotionStatus,
    VersionBumpType,
    PromotionEnvironment,
    PromotionFailureReason,
    FeatureFlags,
    get_template_promotion_service,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def promotion_service():
    """Create a promotion service instance."""
    return TemplatePromotionService()


@pytest.fixture
def custom_thresholds():
    """Custom thresholds for testing."""
    return PromotionThresholds(
        quality_score=90.0,
        security_score=85.0,
        test_coverage=80.0,
        test_pass_rate=100.0,
    )


@pytest.fixture
def sample_template_content():
    """Sample Python template content."""
    return '''#!/usr/bin/env python3
"""
Sample Template Module

This is a sample template for testing promotion service.
@author: test_author
@tags: test, sample, demo
"""

import logging

logger = logging.getLogger(__name__)


def sample_function(value: int) -> int:
    """
    Sample function with docstring.

    Args:
        value: Input value

    Returns:
        Processed value
    """
    try:
        result = value * 2
        logger.info(f"Processed value: {result}")
        return result
    except Exception as e:
        logger.error(f"Error: {e}")
        raise


def test_sample_function():
    """Test for sample function."""
    assert sample_function(5) == 10
'''


@pytest.fixture
def sample_metadata():
    """Sample existing metadata."""
    return {
        "template_id": "tmpl-test-001",
        "name": "test-template",
        "version": "1.2.3",
        "description": "Test template",
        "author": "original_author",
        "language": "python",
        "category": "testing",
        "tags": ["existing-tag"],
    }


@pytest.fixture
def sample_changes():
    """Sample changes for versioning."""
    return [
        {
            "type": "feature",
            "description": "Added new function",
            "commit_hash": "abc123",
        },
        {
            "type": "fix",
            "description": "Fixed bug in processing",
            "commit_hash": "def456",
        },
    ]


# ============================================================================
# FEATURE FLAG TESTS (AC-6)
# ============================================================================

class TestFeatureFlags:
    """Tests for feature flag functionality."""

    def test_default_promotion_enabled(self):
        """Test default promotion flag is enabled."""
        with patch.dict(os.environ, {}, clear=True):
            assert FeatureFlags.promotion_enabled() is True

    def test_promotion_disabled(self):
        """Test promotion can be disabled."""
        with patch.dict(os.environ, {"FF_TEMPLATE_PROMOTION_ENABLED": "false"}):
            assert FeatureFlags.promotion_enabled() is False

    def test_promotion_enabled_explicit(self):
        """Test promotion enabled explicitly."""
        with patch.dict(os.environ, {"FF_TEMPLATE_PROMOTION_ENABLED": "true"}):
            assert FeatureFlags.promotion_enabled() is True

    def test_auto_version_enabled(self):
        """Test auto version flag."""
        with patch.dict(os.environ, {"FF_AUTO_VERSION_BUMP": "true"}):
            assert FeatureFlags.auto_version_enabled() is True

    def test_changelog_disabled(self):
        """Test changelog can be disabled."""
        with patch.dict(os.environ, {"FF_CHANGELOG_GENERATION": "false"}):
            assert FeatureFlags.changelog_enabled() is False


class TestFeatureFlagCheck:
    """Tests for service feature flag check."""

    def test_check_feature_flag_enabled(self, promotion_service):
        """Test feature flag check when enabled."""
        with patch.dict(os.environ, {"FF_TEMPLATE_PROMOTION_ENABLED": "true"}):
            enabled, error = promotion_service.check_feature_flag()
            assert enabled is True
            assert error is None

    def test_check_feature_flag_disabled(self, promotion_service):
        """Test feature flag check when disabled."""
        with patch.dict(os.environ, {"FF_TEMPLATE_PROMOTION_ENABLED": "false"}):
            enabled, error = promotion_service.check_feature_flag()
            assert enabled is False
            assert "disabled" in error.lower()


# ============================================================================
# CRITERIA VALIDATION TESTS (AC-1)
# ============================================================================

class TestPromotionCriteriaValidation:
    """Tests for promotion criteria validation."""

    def test_all_criteria_passed(self, promotion_service):
        """Test validation when all criteria are met."""
        criteria = promotion_service.validate_promotion_criteria(
            quality_score=90.0,
            security_score=85.0,
            test_pass_rate=100.0,
            test_coverage=80.0,
        )

        assert criteria.passed is True
        assert criteria.quality_score_met is True
        assert criteria.security_score_met is True
        assert criteria.tests_passed is True
        assert criteria.coverage_met is True
        assert len(criteria.failure_reasons) == 0

    def test_quality_score_failed(self, promotion_service):
        """Test validation when quality score fails."""
        criteria = promotion_service.validate_promotion_criteria(
            quality_score=80.0,  # Below threshold of 85
            security_score=85.0,
            test_pass_rate=100.0,
            test_coverage=80.0,
        )

        assert criteria.passed is False
        assert criteria.quality_score_met is False
        assert criteria.security_score_met is True
        assert len(criteria.failure_reasons) == 1
        assert "quality" in criteria.failure_reasons[0].lower()

    def test_security_score_failed(self, promotion_service):
        """Test validation when security score fails."""
        criteria = promotion_service.validate_promotion_criteria(
            quality_score=90.0,
            security_score=70.0,  # Below threshold of 80
            test_pass_rate=100.0,
            test_coverage=80.0,
        )

        assert criteria.passed is False
        assert criteria.security_score_met is False
        assert len(criteria.failure_reasons) == 1
        assert "security" in criteria.failure_reasons[0].lower()

    def test_tests_failed(self, promotion_service):
        """Test validation when tests fail."""
        criteria = promotion_service.validate_promotion_criteria(
            quality_score=90.0,
            security_score=85.0,
            test_pass_rate=95.0,  # Below threshold of 100
            test_coverage=80.0,
        )

        assert criteria.passed is False
        assert criteria.tests_passed is False
        assert len(criteria.failure_reasons) == 1
        assert "test pass rate" in criteria.failure_reasons[0].lower()

    def test_coverage_failed(self, promotion_service):
        """Test validation when coverage fails."""
        criteria = promotion_service.validate_promotion_criteria(
            quality_score=90.0,
            security_score=85.0,
            test_pass_rate=100.0,
            test_coverage=60.0,  # Below threshold of 70
        )

        assert criteria.passed is False
        assert criteria.coverage_met is False
        assert len(criteria.failure_reasons) == 1
        assert "coverage" in criteria.failure_reasons[0].lower()

    def test_multiple_failures(self, promotion_service):
        """Test validation with multiple failures."""
        criteria = promotion_service.validate_promotion_criteria(
            quality_score=70.0,
            security_score=60.0,
            test_pass_rate=80.0,
            test_coverage=50.0,
        )

        assert criteria.passed is False
        assert len(criteria.failure_reasons) == 4

    def test_custom_thresholds(self, promotion_service, custom_thresholds):
        """Test validation with custom thresholds."""
        # Should fail with custom thresholds (90% quality required)
        criteria = promotion_service.validate_promotion_criteria(
            quality_score=88.0,
            security_score=90.0,
            test_pass_rate=100.0,
            test_coverage=85.0,
            custom_thresholds=custom_thresholds,
        )

        assert criteria.passed is False
        assert criteria.quality_score_met is False
        assert criteria.thresholds["quality_score"] == 90.0

    def test_criteria_to_dict(self, promotion_service):
        """Test criteria serialization."""
        criteria = promotion_service.validate_promotion_criteria(
            quality_score=90.0,
            security_score=85.0,
            test_pass_rate=100.0,
            test_coverage=80.0,
        )

        data = criteria.to_dict()
        assert data["passed"] is True
        assert data["actual_quality_score"] == 90.0
        assert "thresholds" in data


# ============================================================================
# METADATA EXTRACTION TESTS (AC-2)
# ============================================================================

class TestMetadataExtraction:
    """Tests for metadata extraction and enrichment."""

    def test_extract_basic_metadata(self, promotion_service, sample_template_content):
        """Test basic metadata extraction."""
        metadata = promotion_service.extract_metadata(
            template_id="tmpl-001",
            template_content=sample_template_content,
        )

        assert metadata.template_id == "tmpl-001"
        assert metadata.language == "python"
        assert metadata.name == "tmpl-001"

    def test_extract_author(self, promotion_service, sample_template_content):
        """Test author extraction from content."""
        metadata = promotion_service.extract_metadata(
            template_id="tmpl-001",
            template_content=sample_template_content,
        )

        assert metadata.author == "test_author"

    def test_extract_tags(self, promotion_service, sample_template_content):
        """Test tags extraction from content."""
        metadata = promotion_service.extract_metadata(
            template_id="tmpl-001",
            template_content=sample_template_content,
        )

        assert "test" in metadata.tags
        assert "sample" in metadata.tags

    def test_extract_description(self, promotion_service, sample_template_content):
        """Test description extraction from docstring."""
        metadata = promotion_service.extract_metadata(
            template_id="tmpl-001",
            template_content=sample_template_content,
        )

        assert "Sample Template Module" in metadata.description

    def test_detect_framework(self, promotion_service):
        """Test framework detection."""
        fastapi_content = '''
from fastapi import FastAPI

def create_app():
    app = FastAPI()
    return app
'''
        metadata = promotion_service.extract_metadata(
            template_id="tmpl-001",
            template_content=fastapi_content,
        )

        # Framework detection requires Python language detection
        assert metadata.language == "python"
        assert metadata.framework == "fastapi"

    def test_merge_existing_metadata(self, promotion_service, sample_template_content, sample_metadata):
        """Test merging with existing metadata."""
        metadata = promotion_service.extract_metadata(
            template_id="tmpl-test-001",
            template_content=sample_template_content,
            existing_metadata=sample_metadata,
        )

        # Existing metadata should be preserved
        assert metadata.version == "1.2.3"
        assert metadata.category == "testing"

        # Tags should be merged
        assert "existing-tag" in metadata.tags
        assert "test" in metadata.tags

    def test_metadata_to_dict(self, promotion_service, sample_template_content):
        """Test metadata serialization."""
        metadata = promotion_service.extract_metadata(
            template_id="tmpl-001",
            template_content=sample_template_content,
        )

        data = metadata.to_dict()
        assert data["template_id"] == "tmpl-001"
        assert data["language"] == "python"


class TestLanguageDetection:
    """Tests for programming language detection."""

    def test_detect_python(self, promotion_service):
        """Test Python detection."""
        content = "def hello():\n    pass"
        assert promotion_service._detect_language(content) == "python"

    def test_detect_javascript(self, promotion_service):
        """Test JavaScript detection."""
        content = "function hello() { return 1; }"
        assert promotion_service._detect_language(content) == "javascript"

    def test_detect_go(self, promotion_service):
        """Test Go detection."""
        content = "package main\nfunc hello() {}"
        assert promotion_service._detect_language(content) == "go"

    def test_detect_java(self, promotion_service):
        """Test Java detection."""
        content = "public class Hello { private void test() {} }"
        assert promotion_service._detect_language(content) == "java"


# ============================================================================
# VERSION CALCULATION TESTS (AC-3)
# ============================================================================

class TestVersionCalculation:
    """Tests for semantic version calculation."""

    def test_patch_bump_default(self, promotion_service):
        """Test default patch bump."""
        new_version, bump_type = promotion_service.calculate_version(
            current_version="1.2.3",
            changes=[],
        )

        assert new_version == "1.2.4"
        assert bump_type == VersionBumpType.PATCH

    def test_minor_bump_feature(self, promotion_service):
        """Test minor bump for feature."""
        changes = [{"type": "feature", "description": "New feature"}]

        new_version, bump_type = promotion_service.calculate_version(
            current_version="1.2.3",
            changes=changes,
        )

        assert new_version == "1.3.0"
        assert bump_type == VersionBumpType.MINOR

    def test_major_bump_breaking(self, promotion_service):
        """Test major bump for breaking change."""
        changes = [{"type": "breaking", "description": "Breaking change"}]

        new_version, bump_type = promotion_service.calculate_version(
            current_version="1.2.3",
            changes=changes,
        )

        assert new_version == "2.0.0"
        assert bump_type == VersionBumpType.MAJOR

    def test_major_bump_flag(self, promotion_service):
        """Test major bump via breaking flag."""
        changes = [{"type": "fix", "description": "Fix", "breaking": True}]

        new_version, bump_type = promotion_service.calculate_version(
            current_version="1.2.3",
            changes=changes,
        )

        assert new_version == "2.0.0"
        assert bump_type == VersionBumpType.MAJOR

    def test_force_bump(self, promotion_service):
        """Test forced version bump."""
        new_version, bump_type = promotion_service.calculate_version(
            current_version="1.2.3",
            changes=[],
            force_bump=VersionBumpType.MINOR,
        )

        assert new_version == "1.3.0"
        assert bump_type == VersionBumpType.MINOR

    def test_parse_version_with_v_prefix(self, promotion_service):
        """Test parsing version with v prefix."""
        new_version, _ = promotion_service.calculate_version(
            current_version="v1.2.3",
            changes=[],
        )

        assert new_version == "1.2.4"

    def test_initial_version(self, promotion_service):
        """Test initial version bump."""
        new_version, _ = promotion_service.calculate_version(
            current_version="0.0.0",
            changes=[],
        )

        assert new_version == "0.0.1"

    def test_auto_version_disabled(self, promotion_service):
        """Test version bump when auto-version is disabled."""
        with patch.dict(os.environ, {"FF_AUTO_VERSION_BUMP": "false"}):
            changes = [{"type": "feature", "description": "New feature"}]

            new_version, bump_type = promotion_service.calculate_version(
                current_version="1.2.3",
                changes=changes,
            )

            # Should default to patch when disabled
            assert new_version == "1.2.4"
            assert bump_type == VersionBumpType.PATCH


# ============================================================================
# CHANGELOG GENERATION TESTS (AC-4)
# ============================================================================

class TestChangelogGeneration:
    """Tests for changelog generation."""

    def test_generate_changelog_basic(self, promotion_service, sample_changes):
        """Test basic changelog generation."""
        changelog = promotion_service.generate_changelog(
            template_id="tmpl-001",
            changes=sample_changes,
            new_version="1.3.0",
            author="test_user",
        )

        assert changelog.template_id == "tmpl-001"
        assert len(changelog.entries) == 2
        assert changelog.entries[0].version == "1.3.0"
        assert changelog.entries[0].author == "test_user"

    def test_generate_changelog_empty_changes(self, promotion_service):
        """Test changelog with empty changes."""
        changelog = promotion_service.generate_changelog(
            template_id="tmpl-001",
            changes=[],
            new_version="1.0.1",
            author="test_user",
        )

        assert len(changelog.entries) == 1
        assert "promoted" in changelog.entries[0].description.lower()

    def test_changelog_to_markdown(self, promotion_service, sample_changes):
        """Test changelog markdown generation."""
        changelog = promotion_service.generate_changelog(
            template_id="tmpl-001",
            changes=sample_changes,
            new_version="1.3.0",
            author="test_user",
        )

        markdown = changelog.to_markdown()
        assert "# Changelog" in markdown
        assert "[1.3.0]" in markdown
        assert "Added new function" in markdown

    def test_changelog_disabled(self, promotion_service, sample_changes):
        """Test changelog when feature is disabled."""
        with patch.dict(os.environ, {"FF_CHANGELOG_GENERATION": "false"}):
            changelog = promotion_service.generate_changelog(
                template_id="tmpl-001",
                changes=sample_changes,
                new_version="1.3.0",
                author="test_user",
            )

            assert len(changelog.entries) == 0

    def test_changelog_entry_to_dict(self):
        """Test changelog entry serialization."""
        entry = ChangelogEntry(
            version="1.0.0",
            date="2024-01-01",
            author="test",
            change_type="feature",
            description="New feature",
            commit_hash="abc123",
            breaking=False,
        )

        data = entry.to_dict()
        assert data["version"] == "1.0.0"
        assert data["change_type"] == "feature"
        assert data["commit_hash"] == "abc123"


# ============================================================================
# QUALITY FABRIC INTEGRATION TESTS (AC-5)
# ============================================================================

class TestQualityFabricIntegration:
    """Tests for Quality Fabric integration."""

    @pytest.mark.asyncio
    async def test_mock_validation(self, promotion_service, sample_template_content):
        """Test mock validation when QF not available."""
        result = await promotion_service.validate_with_quality_fabric(
            template_id="tmpl-001",
            template_content=sample_template_content,
        )

        assert "quality_score" in result
        assert "security_score" in result
        assert result["quality_score"] > 0
        assert result["security_score"] > 0

    @pytest.mark.asyncio
    async def test_mock_validation_scores(self, promotion_service):
        """Test mock validation scoring heuristics."""
        good_content = '''
"""Good module with docstrings."""

import logging
logger = logging.getLogger(__name__)

def good_function(value: int) -> int:
    """Good function."""
    try:
        return value * 2
    except Exception as e:
        logger.error(e)
        raise
'''

        result = await promotion_service.validate_with_quality_fabric(
            template_id="tmpl-001",
            template_content=good_content,
        )

        # Good code should have higher scores
        assert result["quality_score"] >= 85.0

    @pytest.mark.asyncio
    async def test_mock_validation_security_penalty(self, promotion_service):
        """Test mock validation security penalties."""
        bad_content = '''
# Bad code with security issues
result = eval(user_input)
exec(command)
'''

        result = await promotion_service.validate_with_quality_fabric(
            template_id="tmpl-001",
            template_content=bad_content,
        )

        # Should have lower security score due to eval/exec
        assert result["security_score"] < 90.0


# ============================================================================
# FULL PROMOTION FLOW TESTS
# ============================================================================

class TestPromotionFlow:
    """Tests for full promotion flow."""

    @pytest.mark.asyncio
    async def test_successful_promotion(self, promotion_service, sample_template_content, sample_metadata):
        """Test successful template promotion."""
        result = await promotion_service.promote_template(
            template_id="tmpl-001",
            template_content=sample_template_content,
            source_environment=PromotionEnvironment.STAGING,
            target_environment=PromotionEnvironment.PRODUCTION,
            existing_metadata=sample_metadata,
            promoted_by="test_user",
        )

        assert result.status == PromotionStatus.PROMOTED
        assert result.template_id == "tmpl-001"
        assert result.previous_version == "1.2.3"
        assert result.new_version != result.previous_version
        assert result.metadata is not None
        assert result.changelog is not None
        assert result.criteria.passed is True

    @pytest.mark.asyncio
    async def test_promotion_blocked_feature_disabled(self, promotion_service, sample_template_content):
        """Test promotion blocked when feature disabled."""
        with patch.dict(os.environ, {"FF_TEMPLATE_PROMOTION_ENABLED": "false"}):
            result = await promotion_service.promote_template(
                template_id="tmpl-001",
                template_content=sample_template_content,
                source_environment=PromotionEnvironment.STAGING,
                target_environment=PromotionEnvironment.PRODUCTION,
            )

            assert result.status == PromotionStatus.BLOCKED
            assert result.failure_reason == PromotionFailureReason.FEATURE_DISABLED

    @pytest.mark.asyncio
    async def test_promotion_blocked_low_quality(self, promotion_service):
        """Test promotion blocked for low quality."""
        # Create service with high thresholds
        service = TemplatePromotionService(
            thresholds=PromotionThresholds(quality_score=99.0)
        )

        bad_content = "x = 1"  # Minimal content, low quality

        result = await service.promote_template(
            template_id="tmpl-001",
            template_content=bad_content,
            source_environment=PromotionEnvironment.STAGING,
            target_environment=PromotionEnvironment.PRODUCTION,
        )

        assert result.status == PromotionStatus.BLOCKED
        assert result.failure_reason == PromotionFailureReason.QUALITY_SCORE_LOW

    @pytest.mark.asyncio
    async def test_promotion_with_changes(self, promotion_service, sample_template_content, sample_changes):
        """Test promotion with version changes."""
        result = await promotion_service.promote_template(
            template_id="tmpl-001",
            template_content=sample_template_content,
            source_environment=PromotionEnvironment.STAGING,
            target_environment=PromotionEnvironment.PRODUCTION,
            changes=sample_changes,
            existing_metadata={"version": "1.0.0"},
        )

        assert result.status == PromotionStatus.PROMOTED
        # Feature change should cause minor bump
        assert result.version_bump_type == VersionBumpType.MINOR
        assert result.new_version == "1.1.0"

    @pytest.mark.asyncio
    async def test_promotion_result_to_dict(self, promotion_service, sample_template_content):
        """Test promotion result serialization."""
        result = await promotion_service.promote_template(
            template_id="tmpl-001",
            template_content=sample_template_content,
            source_environment=PromotionEnvironment.STAGING,
            target_environment=PromotionEnvironment.PRODUCTION,
        )

        data = result.to_dict()
        assert data["template_id"] == "tmpl-001"
        assert data["status"] == "promoted"
        assert "criteria" in data
        assert "changelog" in data


# ============================================================================
# SERVICE UTILITY TESTS
# ============================================================================

class TestServiceUtilities:
    """Tests for service utility methods."""

    def test_get_config(self, promotion_service):
        """Test getting service configuration."""
        config = promotion_service.get_config()

        assert "thresholds" in config
        assert "feature_flags" in config
        assert "quality_fabric_url" in config
        assert config["thresholds"]["quality_score"] == 85.0

    def test_update_thresholds(self, promotion_service, custom_thresholds):
        """Test updating thresholds."""
        promotion_service.update_thresholds(custom_thresholds)

        config = promotion_service.get_config()
        assert config["thresholds"]["quality_score"] == 90.0

    @pytest.mark.asyncio
    async def test_get_promotion_result(self, promotion_service, sample_template_content):
        """Test getting cached promotion result."""
        result = await promotion_service.promote_template(
            template_id="tmpl-001",
            template_content=sample_template_content,
            source_environment=PromotionEnvironment.STAGING,
            target_environment=PromotionEnvironment.PRODUCTION,
        )

        cached = promotion_service.get_promotion_result(result.promotion_id)
        assert cached is not None
        assert cached.promotion_id == result.promotion_id

    def test_singleton_service(self):
        """Test singleton pattern."""
        service1 = get_template_promotion_service()
        service2 = get_template_promotion_service()
        assert service1 is service2


# ============================================================================
# DATA CLASS TESTS
# ============================================================================

class TestPromotionThresholds:
    """Tests for PromotionThresholds dataclass."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = PromotionThresholds()

        assert thresholds.quality_score == 85.0
        assert thresholds.security_score == 80.0
        assert thresholds.test_coverage == 70.0
        assert thresholds.test_pass_rate == 100.0

    def test_from_dict(self):
        """Test creating thresholds from dict."""
        data = {"quality_score": 90.0, "security_score": 85.0}
        thresholds = PromotionThresholds.from_dict(data)

        assert thresholds.quality_score == 90.0
        assert thresholds.security_score == 85.0

    def test_to_dict(self):
        """Test serializing thresholds to dict."""
        thresholds = PromotionThresholds(quality_score=90.0)
        data = thresholds.to_dict()

        assert data["quality_score"] == 90.0


class TestTemplateMetadata:
    """Tests for TemplateMetadata dataclass."""

    def test_default_metadata(self):
        """Test default metadata values."""
        metadata = TemplateMetadata(
            template_id="tmpl-001",
            name="test",
            version="1.0.0",
        )

        assert metadata.template_id == "tmpl-001"
        assert metadata.tags == []
        assert metadata.quality_score == 0.0

    def test_from_dict(self):
        """Test creating metadata from dict."""
        data = {
            "template_id": "tmpl-001",
            "name": "test",
            "version": "1.0.0",
            "author": "test_author",
        }
        metadata = TemplateMetadata.from_dict(data)

        assert metadata.template_id == "tmpl-001"
        assert metadata.author == "test_author"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
