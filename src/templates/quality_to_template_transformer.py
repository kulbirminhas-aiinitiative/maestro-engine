#!/usr/bin/env python3
"""
Quality-Fabric to Template Transformer
Converts Quality-Fabric validation results into MAESTRO template format
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from quality_fabric_client import QualityValidationResult
from templates.enterprise_template_repository.template_manager import (
    ComplexityLevel,
    StorageTier,
    TemplateMetadata,
    TemplateStatus,
)

logger = logging.getLogger(__name__)


class QualityToTemplateTransformer:
    """Transform Quality-Fabric results into template metadata"""

    # Quality score thresholds for template creation
    MIN_QUALITY_SCORE = 80.0
    MIN_TEST_COVERAGE = 70.0
    MIN_SUCCESS_RATE = 0.90

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def should_create_template(self, quality_result: QualityValidationResult) -> bool:
        """
        Determine if code quality is high enough to warrant template creation

        Args:
            quality_result: Quality validation result from Quality-Fabric

        Returns:
            True if code meets quality thresholds for template creation
        """
        if not quality_result or not quality_result.success:
            return False

        # Check quality score
        if quality_result.quality_score < self.MIN_QUALITY_SCORE:
            self.logger.info(
                f"Quality score {quality_result.quality_score:.1f} below threshold {self.MIN_QUALITY_SCORE}"
            )
            return False

        # Check test coverage
        if quality_result.test_coverage < self.MIN_TEST_COVERAGE:
            self.logger.info(
                f"Test coverage {quality_result.test_coverage:.1f}% below threshold {self.MIN_TEST_COVERAGE}%"
            )
            return False

        # Check test success rate
        if quality_result.total_tests > 0:
            success_rate = quality_result.passed_tests / quality_result.total_tests
            if success_rate < self.MIN_SUCCESS_RATE:
                self.logger.info(
                    f"Test success rate {success_rate:.1%} below threshold {self.MIN_SUCCESS_RATE:.1%}"
                )
                return False

        self.logger.info(
            f"✅ Code quality sufficient for template creation: "
            f"Score {quality_result.quality_score:.1f}, "
            f"Coverage {quality_result.test_coverage:.1f}%"
        )
        return True

    def transform_to_template_metadata(
        self,
        quality_result: QualityValidationResult,
        workflow_result: Dict[str, Any],
        file_path: str,
    ) -> Optional[TemplateMetadata]:
        """
        Transform quality validation result into template metadata

        Args:
            quality_result: Quality validation result from Quality-Fabric
            workflow_result: Original workflow execution result
            file_path: Path to the template file

        Returns:
            TemplateMetadata object if successful, None otherwise
        """
        try:
            # Check if quality is sufficient
            if not self.should_create_template(quality_result):
                return None

            # Extract file metadata
            file_info = self._extract_file_info(file_path, workflow_result)

            # Determine complexity level
            complexity = self._determine_complexity(quality_result, workflow_result)

            # Generate tags
            tags = self._generate_tags(quality_result, workflow_result)

            # Create template metadata
            metadata = TemplateMetadata(
                name=file_info["name"],
                category=file_info["category"],
                language=file_info["language"],
                description=self._generate_description(workflow_result, quality_result),
                file_path=file_path,
                created_by="maestro_ai_orchestrator",
                version="1.0.0",
                framework=file_info.get("framework"),
                domain=file_info.get("domain"),
                pattern=self._extract_pattern_type(file_path, workflow_result),
                tags=tags,
                complexity=complexity,
                status=TemplateStatus.APPROVED,  # Auto-approve high-quality templates
                # Quality metrics from Quality-Fabric
                quality_score=quality_result.quality_score,
                security_score=int(quality_result.security_score),
                performance_score=int(quality_result.performance_score),
                maintainability_score=int(quality_result.maintainability_score),
                test_coverage=quality_result.test_coverage,
                # Initial usage metrics
                usage_count=0,
                success_rate=1.0,  # Initial assumption for high-quality code
                popularity="warm",  # Start as warm, will adjust based on usage
                maturity="stable",  # High quality code starts as stable
                # System fields
                created_at=datetime.now(),
                updated_at=datetime.now(),
                storage_tier=StorageTier.WARM,
            )

            self.logger.info(
                f"Created template metadata: {metadata.name} "
                f"(Quality: {metadata.quality_score:.1f})"
            )
            return metadata

        except Exception as e:
            self.logger.error(f"Failed to transform quality result to template: {e}")
            return None

    def _extract_file_info(self, file_path: str, workflow_result: Dict[str, Any]) -> Dict[str, str]:
        """Extract file information from path and workflow result"""
        path = Path(file_path)

        # Determine language from file extension
        ext_to_lang = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "c",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
        }
        language = ext_to_lang.get(path.suffix, "unknown")

        # Determine category from workflow context
        category = self._infer_category(file_path, workflow_result)

        # Detect framework
        framework = self._detect_framework(file_path, workflow_result)

        return {
            "name": path.stem,
            "language": language,
            "category": category,
            "framework": framework,
            "domain": self._infer_domain(workflow_result),
        }

    def _infer_category(self, file_path: str, workflow_result: Dict[str, Any]) -> str:
        """Infer template category from file path and context"""
        path_lower = file_path.lower()

        if "api" in path_lower or "endpoint" in path_lower:
            return "api"
        elif "test" in path_lower:
            return "testing"
        elif "service" in path_lower:
            return "service"
        elif "component" in path_lower or "ui" in path_lower:
            return "component"
        elif "model" in path_lower or "schema" in path_lower:
            return "data"
        elif "util" in path_lower or "helper" in path_lower:
            return "utility"
        elif "config" in path_lower:
            return "configuration"
        else:
            return "general"

    def _detect_framework(self, file_path: str, workflow_result: Dict[str, Any]) -> Optional[str]:
        """Detect framework from file path and workflow context"""
        files = workflow_result.get("files_generated", [])
        all_files = " ".join(str(f) for f in files).lower()

        # React
        if ".jsx" in file_path or ".tsx" in file_path or "react" in all_files:
            return "react"
        # FastAPI
        elif "fastapi" in all_files or "uvicorn" in all_files:
            return "fastapi"
        # Django
        elif "django" in all_files:
            return "django"
        # Flask
        elif "flask" in all_files:
            return "flask"
        # Express
        elif "express" in all_files:
            return "express"

        return None

    def _infer_domain(self, workflow_result: Dict[str, Any]) -> Optional[str]:
        """Infer domain from workflow requirement"""
        requirement = workflow_result.get("requirement", "").lower()

        if any(kw in requirement for kw in ["auth", "login", "user"]):
            return "authentication"
        elif any(kw in requirement for kw in ["payment", "billing", "invoice"]):
            return "payment"
        elif any(kw in requirement for kw in ["data", "database", "storage"]):
            return "data"
        elif any(kw in requirement for kw in ["api", "endpoint", "rest"]):
            return "api"
        elif any(kw in requirement for kw in ["ui", "frontend", "component"]):
            return "frontend"

        return None

    def _determine_complexity(
        self, quality_result: QualityValidationResult, workflow_result: Dict[str, Any]
    ) -> ComplexityLevel:
        """Determine template complexity based on various factors"""

        # Calculate complexity score
        complexity_score = 0

        # Factor 1: Number of files
        file_count = len(workflow_result.get("files_generated", []))
        if file_count > 10:
            complexity_score += 3
        elif file_count > 5:
            complexity_score += 2
        elif file_count > 2:
            complexity_score += 1

        # Factor 2: Test coverage (higher coverage often means more complex code)
        if quality_result.test_coverage > 90:
            complexity_score += 2
        elif quality_result.test_coverage > 70:
            complexity_score += 1

        # Factor 3: Maintainability (lower score = more complex)
        if quality_result.maintainability_score < 60:
            complexity_score += 2
        elif quality_result.maintainability_score < 75:
            complexity_score += 1

        # Map score to complexity level
        if complexity_score >= 6:
            return ComplexityLevel.EXPERT
        elif complexity_score >= 4:
            return ComplexityLevel.ADVANCED
        elif complexity_score >= 2:
            return ComplexityLevel.INTERMEDIATE
        else:
            return ComplexityLevel.SIMPLE

    def _generate_tags(
        self, quality_result: QualityValidationResult, workflow_result: Dict[str, Any]
    ) -> List[str]:
        """Generate relevant tags for the template"""
        tags = []

        # Quality-based tags
        if quality_result.quality_score >= 95:
            tags.append("high-quality")
        if quality_result.test_coverage >= 90:
            tags.append("well-tested")
        if quality_result.security_score >= 90:
            tags.append("secure")
        if quality_result.performance_score >= 90:
            tags.append("performant")

        # Extract keywords from requirement
        requirement = workflow_result.get("requirement", "").lower()
        keywords = ["api", "crud", "authentication", "database", "rest", "async", "microservice"]
        for keyword in keywords:
            if keyword in requirement:
                tags.append(keyword)

        # Add team member tags
        team_members = workflow_result.get("team_members", [])
        if team_members:
            tags.append("ai-generated")

        return list(set(tags))  # Remove duplicates

    def _extract_pattern_type(
        self, file_path: str, workflow_result: Dict[str, Any]
    ) -> Optional[str]:
        """Extract pattern type from file path and context"""
        path_lower = file_path.lower()

        if "controller" in path_lower or "handler" in path_lower:
            return "controller"
        elif "service" in path_lower:
            return "service"
        elif "repository" in path_lower or "dao" in path_lower:
            return "repository"
        elif "model" in path_lower or "entity" in path_lower:
            return "model"
        elif "component" in path_lower:
            return "component"
        elif "middleware" in path_lower:
            return "middleware"
        elif "util" in path_lower:
            return "utility"

        return None

    def _generate_description(
        self, workflow_result: Dict[str, Any], quality_result: QualityValidationResult
    ) -> str:
        """Generate template description"""
        requirement = workflow_result.get("requirement", "Unknown requirement")

        description = f"AI-generated template from: {requirement}. "
        description += f"Quality score: {quality_result.quality_score:.1f}, "
        description += f"Test coverage: {quality_result.test_coverage:.1f}%, "
        description += f"Tests: {quality_result.passed_tests}/{quality_result.total_tests} passed."

        if quality_result.recommendations:
            description += f" Validated with {len(quality_result.recommendations)} recommendations."

        return description


# Convenience function
def transform_quality_result(
    quality_result: QualityValidationResult, workflow_result: Dict[str, Any], file_path: str
) -> Optional[TemplateMetadata]:
    """
    Convenience function to transform quality result to template metadata

    Args:
        quality_result: Quality validation result from Quality-Fabric
        workflow_result: Original workflow execution result
        file_path: Path to the template file

    Returns:
        TemplateMetadata if quality is sufficient, None otherwise
    """
    transformer = QualityToTemplateTransformer()
    return transformer.transform_to_template_metadata(quality_result, workflow_result, file_path)
