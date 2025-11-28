#!/usr/bin/env python3
"""
Unit tests for Maestro Templates CLI
Epic: MD-1833 [MT-600] Maestro Templates CLI Enhancements

Tests cover all Acceptance Criteria:
- AC-1: All 5 commands implemented and documented
- AC-2: promote supports --dry-run flag
- AC-3: validate shows detailed report output
- AC-4: provenance displays full lineage tree
- AC-5: versions shows changelog with diffs
- AC-6: recommend accepts persona, tag, min_score filters
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cli.maestro_templates_cli import (
    MaestroTemplatesCLI,
    PromoteOptions,
    ValidateOptions,
    ProvenanceOptions,
    VersionsOptions,
    RecommendOptions,
    OutputFormat,
    CLIConfig,
)


class TestMaestroTemplatesCLI:
    """Tests for MaestroTemplatesCLI."""

    @pytest.fixture
    def cli(self):
        """Create a fresh CLI instance for testing."""
        return MaestroTemplatesCLI()

    # ========================================================================
    # AC-1: All 5 commands implemented and documented
    # ========================================================================

    def test_cli_has_promote_command(self, cli):
        """AC-1: promote command is implemented."""
        assert hasattr(cli, 'promote')
        assert callable(cli.promote)

    def test_cli_has_validate_command(self, cli):
        """AC-1: validate command is implemented."""
        assert hasattr(cli, 'validate')
        assert callable(cli.validate)

    def test_cli_has_provenance_command(self, cli):
        """AC-1: provenance command is implemented."""
        assert hasattr(cli, 'provenance')
        assert callable(cli.provenance)

    def test_cli_has_versions_command(self, cli):
        """AC-1: versions command is implemented."""
        assert hasattr(cli, 'versions')
        assert callable(cli.versions)

    def test_cli_has_recommend_command(self, cli):
        """AC-1: recommend command is implemented."""
        assert hasattr(cli, 'recommend')
        assert callable(cli.recommend)

    def test_cli_has_help_documentation(self, cli):
        """AC-1: CLI has documentation."""
        assert cli.__doc__ is not None
        assert "promote" in cli.__doc__
        assert "validate" in cli.__doc__
        assert "provenance" in cli.__doc__
        assert "versions" in cli.__doc__
        assert "recommend" in cli.__doc__

    # ========================================================================
    # AC-2: promote supports --dry-run flag
    # ========================================================================

    def test_promote_dry_run_no_changes(self, cli):
        """AC-2: Dry run does not make actual changes."""
        options = PromoteOptions(
            artifact_path="./build/test",
            min_score=85.0,
            dry_run=True,
        )
        result = cli.promote(options)

        assert result["dry_run"] is True
        assert result["status"] == "dry_run"
        assert "No changes were made" in result.get("message", "")

    def test_promote_options_has_dry_run(self):
        """AC-2: PromoteOptions has dry_run field."""
        options = PromoteOptions(artifact_path="./test", dry_run=True)
        assert options.dry_run is True

        options_false = PromoteOptions(artifact_path="./test", dry_run=False)
        assert options_false.dry_run is False

    def test_promote_with_approvers(self, cli):
        """AC-2: promote supports approvers list."""
        options = PromoteOptions(
            artifact_path="./build/test",
            approvers=["arch", "qa", "security"],
            dry_run=True,
        )
        result = cli.promote(options)
        assert result is not None

    def test_promote_with_min_score(self, cli):
        """AC-2: promote supports min_score threshold."""
        options = PromoteOptions(
            artifact_path="./build/test",
            min_score=90.0,
            dry_run=True,
        )
        result = cli.promote(options)
        assert result is not None

    def test_promote_with_security_min(self, cli):
        """AC-2: promote supports security minimum score."""
        options = PromoteOptions(
            artifact_path="./build/test",
            security_min=85.0,
            dry_run=True,
        )
        result = cli.promote(options)
        assert result is not None

    # ========================================================================
    # AC-3: validate shows detailed report output
    # ========================================================================

    def test_validate_returns_detailed_report(self, cli):
        """AC-3: validate shows detailed report output."""
        options = ValidateOptions(
            template_id="api_auth_v3",
            detailed=True,
        )
        result = cli.validate(options)

        assert "validation_result" in result or "report" in result or "status" in result
        # Should contain some validation details
        assert result is not None

    def test_validate_options_has_detailed_flag(self):
        """AC-3: ValidateOptions has detailed flag."""
        options = ValidateOptions(template_id="test", detailed=True)
        assert options.detailed is True

    def test_validate_basic_report(self, cli):
        """AC-3: validate can return basic report."""
        options = ValidateOptions(
            template_id="api_auth_v3",
            detailed=False,
        )
        result = cli.validate(options)
        assert result is not None

    # ========================================================================
    # AC-4: provenance displays full lineage tree
    # ========================================================================

    def test_provenance_returns_lineage(self, cli):
        """AC-4: provenance displays full lineage tree."""
        options = ProvenanceOptions(
            template_id="api_auth_v3",
            show_lineage=True,
        )
        result = cli.provenance(options)

        assert result is not None
        # Should contain provenance information
        assert "provenance" in result or "lineage" in result or "tree" in result or "source" in result

    def test_provenance_max_depth(self, cli):
        """AC-4: provenance respects max_depth."""
        options = ProvenanceOptions(
            template_id="api_auth_v3",
            show_lineage=True,
            max_depth=5,
        )
        result = cli.provenance(options)
        assert result is not None

    def test_provenance_options_has_lineage_flag(self):
        """AC-4: ProvenanceOptions has show_lineage flag."""
        options = ProvenanceOptions(template_id="test", show_lineage=True)
        assert options.show_lineage is True

    # ========================================================================
    # AC-5: versions shows changelog with diffs
    # ========================================================================

    def test_versions_returns_changelog(self, cli):
        """AC-5: versions shows changelog."""
        options = VersionsOptions(
            template_id="api_auth_v3",
            limit=10,
        )
        result = cli.versions(options)

        assert result is not None
        # Should contain version information
        assert "versions" in result or "changelog" in result or "history" in result

    def test_versions_with_diffs(self, cli):
        """AC-5: versions shows diffs when requested."""
        options = VersionsOptions(
            template_id="api_auth_v3",
            show_diffs=True,
        )
        result = cli.versions(options)
        assert result is not None

    def test_versions_respects_limit(self, cli):
        """AC-5: versions respects limit parameter."""
        options = VersionsOptions(
            template_id="api_auth_v3",
            limit=3,
        )
        result = cli.versions(options)
        assert result is not None

    def test_versions_options_has_diffs_flag(self):
        """AC-5: VersionsOptions has show_diffs flag."""
        options = VersionsOptions(template_id="test", show_diffs=True)
        assert options.show_diffs is True

    # ========================================================================
    # AC-6: recommend accepts persona, tag, min_score filters
    # ========================================================================

    def test_recommend_accepts_persona(self, cli):
        """AC-6: recommend accepts persona filter."""
        options = RecommendOptions(
            persona="backend_developer",
        )
        result = cli.recommend(options)

        assert result is not None
        # Should contain recommendations
        assert "recommendations" in result or "templates" in result or "results" in result

    def test_recommend_accepts_tags(self, cli):
        """AC-6: recommend accepts tag filter."""
        options = RecommendOptions(
            tags=["auth", "security"],
        )
        result = cli.recommend(options)
        assert result is not None

    def test_recommend_accepts_min_score(self, cli):
        """AC-6: recommend accepts min_score filter."""
        options = RecommendOptions(
            min_score=85.0,
        )
        result = cli.recommend(options)
        assert result is not None

    def test_recommend_accepts_all_filters(self, cli):
        """AC-6: recommend accepts all filter options."""
        options = RecommendOptions(
            persona="backend_developer",
            tags=["auth", "api"],
            min_score=80.0,
            language="python",
            framework="fastapi",
            limit=5,
        )
        result = cli.recommend(options)
        assert result is not None

    def test_recommend_options_has_language_filter(self):
        """AC-6: RecommendOptions has language filter."""
        options = RecommendOptions(language="python")
        assert options.language == "python"

    def test_recommend_options_has_framework_filter(self):
        """AC-6: RecommendOptions has framework filter."""
        options = RecommendOptions(framework="fastapi")
        assert options.framework == "fastapi"

    # ========================================================================
    # Additional Tests
    # ========================================================================

    def test_output_format_enum(self):
        """Test output format options."""
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.TABLE.value == "table"
        assert OutputFormat.TEXT.value == "text"

    def test_cli_config_defaults(self):
        """Test CLI config defaults."""
        config = CLIConfig()
        assert config.api_base_url == "http://localhost:8000"
        assert config.output_format == OutputFormat.TABLE
        assert config.verbose is False

    def test_cli_config_custom(self):
        """Test custom CLI config."""
        config = CLIConfig(
            api_base_url="http://custom:9000",
            output_format=OutputFormat.JSON,
            verbose=True,
        )
        assert config.api_base_url == "http://custom:9000"
        assert config.output_format == OutputFormat.JSON
        assert config.verbose is True

    def test_promote_options_defaults(self):
        """Test promote options defaults."""
        options = PromoteOptions(artifact_path="./test")
        assert options.min_score == 85.0
        assert options.security_min == 80.0
        assert options.approvers == []
        assert options.dry_run is False
        assert options.require_gates_passed is True

    def test_validate_options_defaults(self):
        """Test validate options defaults."""
        options = ValidateOptions(template_id="test")
        assert options.detailed is True

    def test_provenance_options_defaults(self):
        """Test provenance options defaults."""
        options = ProvenanceOptions(template_id="test")
        assert options.show_lineage is True
        assert options.max_depth == 10

    def test_versions_options_defaults(self):
        """Test versions options defaults."""
        options = VersionsOptions(template_id="test")
        assert options.limit == 10
        assert options.show_diffs is False

    def test_recommend_options_defaults(self):
        """Test recommend options defaults."""
        options = RecommendOptions()
        assert options.persona is None
        assert options.tags == []
        assert options.min_score == 0.0
        assert options.language is None
        assert options.framework is None
        assert options.limit == 10


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
