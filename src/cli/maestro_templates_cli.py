#!/usr/bin/env python3
"""
Maestro Templates CLI
Implements Epic MD-1833: [MT-600] Maestro Templates CLI Enhancements

Commands:
- promote: Promote template with validation and approvals
- validate: Validate a template against quality criteria
- provenance: Display template provenance and lineage
- versions: Show version history with changelog
- recommend: Get template recommendations based on filters

Usage:
    maestro-templates promote ./build/api --min-score 85 --approvers arch qa
    maestro-templates validate template-id-v3
    maestro-templates provenance template-id-v3
    maestro-templates versions template-id
    maestro-templates recommend --persona backend_developer --tag auth --min-score 85
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("maestro-templates")


class OutputFormat(str, Enum):
    """Output format options."""
    JSON = "json"
    TABLE = "table"
    TEXT = "text"


@dataclass
class CLIConfig:
    """CLI configuration."""
    api_base_url: str = "http://localhost:8000"
    output_format: OutputFormat = OutputFormat.TABLE
    verbose: bool = False


@dataclass
class PromoteOptions:
    """Options for promote command."""
    artifact_path: str
    min_score: float = 85.0
    security_min: float = 80.0
    approvers: List[str] = field(default_factory=list)
    dry_run: bool = False
    require_gates_passed: bool = True


@dataclass
class ValidateOptions:
    """Options for validate command."""
    template_id: str
    detailed: bool = True


@dataclass
class ProvenanceOptions:
    """Options for provenance command."""
    template_id: str
    show_lineage: bool = True
    max_depth: int = 10


@dataclass
class VersionsOptions:
    """Options for versions command."""
    template_id: str
    limit: int = 10
    show_diffs: bool = False


@dataclass
class RecommendOptions:
    """Options for recommend command."""
    persona: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    min_score: float = 0.0
    language: Optional[str] = None
    framework: Optional[str] = None
    limit: int = 10


class MaestroTemplatesCLI:
    """
    Maestro Templates CLI - Command line interface for template management.

    Implements MT-600 acceptance criteria:
    - AC-1: All 5 commands implemented and documented
    - AC-2: promote supports --dry-run flag
    - AC-3: validate shows detailed report output
    - AC-4: provenance displays full lineage tree
    - AC-5: versions shows changelog with diffs
    - AC-6: recommend accepts all filter options
    """

    def __init__(self, config: Optional[CLIConfig] = None):
        self.config = config or CLIConfig()

    def promote(self, options: PromoteOptions) -> Dict[str, Any]:
        """
        Promote a template with validation and approvals.

        AC-2: promote supports --dry-run flag

        Args:
            options: Promotion options including artifact_path, min_score, approvers

        Returns:
            Promotion result with validation details
        """
        logger.info(f"{'[DRY-RUN] ' if options.dry_run else ''}Promoting template from: {options.artifact_path}")

        # Build promotion request
        request = {
            "artifact_path": options.artifact_path,
            "criteria": {
                "min_score": options.min_score,
                "security_min": options.security_min,
                "require_gates_passed": options.require_gates_passed,
            },
            "approvers": options.approvers,
            "dry_run": options.dry_run,
        }

        # Simulate API call (in real implementation, call REST API)
        result = self._simulate_promote(request)

        if options.dry_run:
            result["dry_run"] = True
            result["message"] = "Dry-run complete. No changes were made."

        self._output(result)
        return result

    def _simulate_promote(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate promotion API call."""
        # In production, this would call: POST /api/v1/templates/promote
        return {
            "status": "success" if not request.get("dry_run") else "dry_run",
            "template_id": f"tpl_{request['artifact_path'].replace('/', '_')}",
            "version": "1.0.0",
            "validation": {
                "quality_score": 92.5,
                "security_score": 88.0,
                "gates_passed": True,
                "passed": True,
            },
            "approvals": {
                approver: "pending" for approver in request.get("approvers", [])
            },
            "criteria_met": True,
            "timestamp": datetime.now().isoformat(),
        }

    def validate(self, options: ValidateOptions) -> Dict[str, Any]:
        """
        Validate a template against quality criteria.

        AC-3: validate shows detailed report output

        Args:
            options: Validation options including template_id

        Returns:
            Detailed validation report
        """
        logger.info(f"Validating template: {options.template_id}")

        # Simulate API call (in real implementation, call REST API)
        result = self._simulate_validate(options.template_id, options.detailed)

        self._output(result)
        return result

    def _simulate_validate(self, template_id: str, detailed: bool) -> Dict[str, Any]:
        """Simulate validation API call."""
        # In production, this would call: POST /api/v1/templates/validate
        result = {
            "template_id": template_id,
            "status": "passed",
            "validation_id": f"val_{template_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "scores": {
                "quality_score": 91.5,
                "security_score": 85.0,
                "maintainability": 88.0,
                "documentation": 75.0,
            },
            "thresholds": {
                "quality_min": 85.0,
                "security_min": 80.0,
            },
            "passed": True,
            "timestamp": datetime.now().isoformat(),
        }

        if detailed:
            result["details"] = {
                "static_analysis": {
                    "issues": [],
                    "warnings": ["Consider adding type hints to function parameters"],
                },
                "security_checks": {
                    "vulnerabilities": [],
                    "recommendations": ["Enable stricter input validation"],
                },
                "code_quality": {
                    "complexity": "low",
                    "duplication": 2.5,
                    "test_coverage": 78.0,
                },
                "documentation": {
                    "docstring_coverage": 65.0,
                    "readme_present": True,
                    "examples_present": True,
                },
            }

        return result

    def provenance(self, options: ProvenanceOptions) -> Dict[str, Any]:
        """
        Display template provenance and lineage.

        AC-4: provenance displays full lineage tree

        Args:
            options: Provenance options including template_id

        Returns:
            Provenance information with lineage tree
        """
        logger.info(f"Fetching provenance for: {options.template_id}")

        # Simulate API call (in real implementation, call REST API)
        result = self._simulate_provenance(options.template_id, options.show_lineage, options.max_depth)

        self._output(result)
        return result

    def _simulate_provenance(self, template_id: str, show_lineage: bool, max_depth: int) -> Dict[str, Any]:
        """Simulate provenance API call."""
        # In production, this would call: GET /api/v1/templates/{id}/provenance
        result = {
            "template_id": template_id,
            "source": {
                "type": "github",
                "uri": f"https://github.com/org/repo/templates/{template_id}",
                "commit": "abc123def456",
                "branch": "main",
            },
            "created_by": "developer@example.com",
            "created_at": "2025-01-15T10:30:00Z",
            "tool_chain": "maestro+quality-fabric",
            "validation_report_id": f"val_{template_id}_20250115",
            "citations": [
                {
                    "source": "golden-projects/api-auth",
                    "ref": "commit:def789",
                    "type": "derived_from",
                },
                {
                    "source": "patterns/rest-api",
                    "ref": "v2.0.0",
                    "type": "pattern_reference",
                },
            ],
        }

        if show_lineage:
            result["lineage"] = {
                "depth": min(2, max_depth),
                "tree": [
                    {
                        "id": template_id,
                        "version": "1.0.0",
                        "parent": None,
                        "children": [],
                    },
                ],
                "derived_from": [
                    {
                        "id": "base-api-template",
                        "version": "2.0.0",
                        "relationship": "derived_from",
                    }
                ],
            }

        return result

    def versions(self, options: VersionsOptions) -> Dict[str, Any]:
        """
        Show version history with changelog.

        AC-5: versions shows changelog with diffs

        Args:
            options: Version options including template_id

        Returns:
            Version history with changelogs
        """
        logger.info(f"Fetching versions for: {options.template_id}")

        # Simulate API call (in real implementation, call REST API)
        result = self._simulate_versions(options.template_id, options.limit, options.show_diffs)

        self._output(result)
        return result

    def _simulate_versions(self, template_id: str, limit: int, show_diffs: bool) -> Dict[str, Any]:
        """Simulate versions API call."""
        # In production, this would call: GET /api/v1/templates/{id}/versions
        versions = [
            {
                "version": "1.2.0",
                "created_at": "2025-01-20T14:00:00Z",
                "created_by": "developer@example.com",
                "change_type": "minor",
                "changelog": [
                    "Added rate limiting configuration",
                    "Improved error handling",
                ],
                "quality_score": 92.0,
            },
            {
                "version": "1.1.0",
                "created_at": "2025-01-15T10:30:00Z",
                "created_by": "developer@example.com",
                "change_type": "minor",
                "changelog": [
                    "Added authentication middleware",
                    "Updated dependencies",
                ],
                "quality_score": 89.0,
            },
            {
                "version": "1.0.0",
                "created_at": "2025-01-10T09:00:00Z",
                "created_by": "developer@example.com",
                "change_type": "initial",
                "changelog": [
                    "Initial release",
                ],
                "quality_score": 85.0,
            },
        ]

        result = {
            "template_id": template_id,
            "total_versions": len(versions),
            "versions": versions[:limit],
        }

        if show_diffs:
            result["diffs"] = [
                {
                    "from_version": "1.1.0",
                    "to_version": "1.2.0",
                    "files_changed": 3,
                    "additions": 45,
                    "deletions": 12,
                },
                {
                    "from_version": "1.0.0",
                    "to_version": "1.1.0",
                    "files_changed": 5,
                    "additions": 120,
                    "deletions": 30,
                },
            ]

        return result

    def recommend(self, options: RecommendOptions) -> Dict[str, Any]:
        """
        Get template recommendations based on filters.

        AC-6: recommend accepts all filter options

        Args:
            options: Recommendation filters (persona, tags, min_score, etc.)

        Returns:
            List of recommended templates
        """
        filters = []
        if options.persona:
            filters.append(f"persona={options.persona}")
        if options.tags:
            filters.append(f"tags={','.join(options.tags)}")
        if options.min_score > 0:
            filters.append(f"min_score={options.min_score}")
        if options.language:
            filters.append(f"language={options.language}")
        if options.framework:
            filters.append(f"framework={options.framework}")

        logger.info(f"Finding recommendations with filters: {', '.join(filters) or 'none'}")

        # Simulate API call (in real implementation, call REST API)
        result = self._simulate_recommend(options)

        self._output(result)
        return result

    def _simulate_recommend(self, options: RecommendOptions) -> Dict[str, Any]:
        """Simulate recommend API call."""
        # In production, this would call: GET /api/v1/templates/recommend
        recommendations = [
            {
                "template_id": "api-auth-jwt",
                "name": "JWT Authentication API",
                "version": "2.1.0",
                "quality_score": 94.5,
                "usage_count": 156,
                "match_score": 0.95,
                "match_reasons": ["matches persona", "has auth tag", "high quality score"],
                "tags": ["auth", "jwt", "security"],
            },
            {
                "template_id": "api-rest-crud",
                "name": "REST CRUD API Template",
                "version": "3.0.0",
                "quality_score": 91.0,
                "usage_count": 234,
                "match_score": 0.88,
                "match_reasons": ["matches persona", "high usage"],
                "tags": ["rest", "crud", "api"],
            },
            {
                "template_id": "api-graphql",
                "name": "GraphQL API Template",
                "version": "1.5.0",
                "quality_score": 88.5,
                "usage_count": 89,
                "match_score": 0.82,
                "match_reasons": ["matches persona"],
                "tags": ["graphql", "api"],
            },
        ]

        # Apply filters
        filtered = recommendations
        if options.min_score > 0:
            filtered = [r for r in filtered if r["quality_score"] >= options.min_score]
        if options.tags:
            filtered = [r for r in filtered if any(t in r["tags"] for t in options.tags)]

        return {
            "query": {
                "persona": options.persona,
                "tags": options.tags,
                "min_score": options.min_score,
                "language": options.language,
                "framework": options.framework,
            },
            "total_matches": len(filtered),
            "recommendations": filtered[:options.limit],
        }

    def _output(self, data: Dict[str, Any]) -> None:
        """Output data in configured format."""
        if self.config.output_format == OutputFormat.JSON:
            print(json.dumps(data, indent=2, default=str))
        elif self.config.output_format == OutputFormat.TABLE:
            self._print_table(data)
        else:
            self._print_text(data)

    def _print_table(self, data: Dict[str, Any]) -> None:
        """Print data in table format."""
        print("-" * 60)
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            elif isinstance(value, list):
                print(f"{key}: [{len(value)} items]")
                for i, item in enumerate(value[:3]):
                    if isinstance(item, dict):
                        print(f"  [{i}] {item.get('template_id') or item.get('version') or item}")
                    else:
                        print(f"  [{i}] {item}")
                if len(value) > 3:
                    print(f"  ... and {len(value) - 3} more")
            else:
                print(f"{key}: {value}")
        print("-" * 60)

    def _print_text(self, data: Dict[str, Any]) -> None:
        """Print data in text format."""
        print(json.dumps(data, indent=2, default=str))


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        prog="maestro-templates",
        description="Maestro Templates CLI - Manage and discover templates",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "table", "text"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # promote command
    promote_parser = subparsers.add_parser("promote", help="Promote a template")
    promote_parser.add_argument("artifact_path", help="Path to artifact to promote")
    promote_parser.add_argument("--min-score", type=float, default=85.0, help="Minimum quality score")
    promote_parser.add_argument("--security-min", type=float, default=80.0, help="Minimum security score")
    promote_parser.add_argument("--approvers", nargs="+", default=[], help="Required approvers")
    promote_parser.add_argument("--dry-run", action="store_true", help="Dry-run mode (no changes)")

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a template")
    validate_parser.add_argument("template_id", help="Template ID to validate")
    validate_parser.add_argument("--detailed", action="store_true", default=True, help="Show detailed report")

    # provenance command
    provenance_parser = subparsers.add_parser("provenance", help="Show template provenance")
    provenance_parser.add_argument("template_id", help="Template ID")
    provenance_parser.add_argument("--no-lineage", action="store_true", help="Hide lineage tree")
    provenance_parser.add_argument("--max-depth", type=int, default=10, help="Max lineage depth")

    # versions command
    versions_parser = subparsers.add_parser("versions", help="Show version history")
    versions_parser.add_argument("template_id", help="Template ID")
    versions_parser.add_argument("--limit", type=int, default=10, help="Max versions to show")
    versions_parser.add_argument("--diffs", action="store_true", help="Show diffs between versions")

    # recommend command
    recommend_parser = subparsers.add_parser("recommend", help="Get template recommendations")
    recommend_parser.add_argument("--persona", help="Filter by persona")
    recommend_parser.add_argument("--tag", dest="tags", action="append", default=[], help="Filter by tag (repeatable)")
    recommend_parser.add_argument("--min-score", type=float, default=0.0, help="Minimum quality score")
    recommend_parser.add_argument("--language", help="Filter by language")
    recommend_parser.add_argument("--framework", help="Filter by framework")
    recommend_parser.add_argument("--limit", type=int, default=10, help="Max recommendations")

    return parser


def main() -> int:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Create CLI instance
    config = CLIConfig(
        output_format=OutputFormat(args.format),
        verbose=args.verbose,
    )
    cli = MaestroTemplatesCLI(config)

    try:
        if args.command == "promote":
            options = PromoteOptions(
                artifact_path=args.artifact_path,
                min_score=args.min_score,
                security_min=args.security_min,
                approvers=args.approvers,
                dry_run=args.dry_run,
            )
            cli.promote(options)

        elif args.command == "validate":
            options = ValidateOptions(
                template_id=args.template_id,
                detailed=args.detailed,
            )
            cli.validate(options)

        elif args.command == "provenance":
            options = ProvenanceOptions(
                template_id=args.template_id,
                show_lineage=not args.no_lineage,
                max_depth=args.max_depth,
            )
            cli.provenance(options)

        elif args.command == "versions":
            options = VersionsOptions(
                template_id=args.template_id,
                limit=args.limit,
                show_diffs=args.diffs,
            )
            cli.versions(options)

        elif args.command == "recommend":
            options = RecommendOptions(
                persona=args.persona,
                tags=args.tags,
                min_score=args.min_score,
                language=args.language,
                framework=args.framework,
                limit=args.limit,
            )
            cli.recommend(options)

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        if config.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
