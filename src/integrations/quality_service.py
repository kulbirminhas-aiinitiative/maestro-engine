"""
Quality Fabric Service Integration

Uses API Gateway to communicate with quality-fabric service.
Replaces direct HTTP calls to http://localhost:8000

Usage:
    from src.integrations.quality_service import quality_service

    # Validate code
    result = await quality_service.validate_code(code="def test(): pass", language="python")

    # Run tests
    test_results = await quality_service.run_tests(code="...", test_cases=[...])
"""

import logging
from typing import Dict, List, Optional

from src.gateway_client import gateway_client

logger = logging.getLogger(__name__)


class QualityService:
    """
    Interface to quality-fabric service via API Gateway

    Replaces QualityFabricClient and direct HTTP calls
    """

    def __init__(self):
        self.gateway = gateway_client

    async def validate_code(
        self, code: str, language: str = "python", checks: Optional[List[str]] = None
    ) -> Dict:
        """
        Validate code with quality-fabric

        Args:
            code: Source code to validate
            language: Programming language
            checks: List of checks to run (e.g., ["syntax", "security", "best_practices"])

        Returns:
            Validation results
        """
        try:
            # Use actual quality-fabric endpoint: /api/execute
            response = await self.gateway.call(
                service="quality",
                path="/api/execute",
                method="POST",
                json={
                    "code": code,
                    "language": language,
                    "checks": checks or ["syntax", "security", "best_practices"],
                },
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Code validation failed: {response.status_code}")
                return {"valid": False, "errors": [f"Validation failed: {response.status_code}"]}

        except Exception as e:
            logger.error(f"Code validation error: {e}")
            return {"valid": False, "errors": [str(e)]}

    async def run_tests(self, code: str, test_cases: List[Dict], auto_heal: bool = False) -> Dict:
        """
        Run tests on code

        Args:
            code: Source code to test
            test_cases: Test cases to run
            auto_heal: Whether to attempt auto-healing

        Returns:
            Test results
        """
        try:
            # Use actual quality-fabric endpoint: /api/execute for test execution
            response = await self.gateway.call(
                service="quality",
                path="/api/execute",
                method="POST",
                json={"code": code, "test_cases": test_cases, "auto_heal": auto_heal},
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Test execution failed: {response.status_code}")
                return {"passed": False, "results": []}

        except Exception as e:
            logger.error(f"Test execution error: {e}")
            return {"passed": False, "results": [], "error": str(e)}

    async def get_quality_score(self, project_id: str) -> Optional[float]:
        """
        Get quality score for a project

        Args:
            project_id: Project ID

        Returns:
            Quality score (0.0-1.0) or None if not available
        """
        try:
            # Use actual quality-fabric endpoint: /api/results
            response = await self.gateway.call(
                service="quality", path=f"/api/results/{project_id}", method="GET"
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("quality_score", result.get("score", 0.0))
            else:
                return None

        except Exception as e:
            logger.error(f"Quality score fetch error: {e}")
            return None

    async def analyze_code_coverage(self, code: str, tests: str) -> Dict:
        """
        Analyze code coverage

        Args:
            code: Source code
            tests: Test code

        Returns:
            Coverage analysis results
        """
        try:
            response = await self.gateway.call(
                service="quality",
                path="/api/coverage",
                method="POST",
                json={"code": code, "tests": tests},
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {"coverage": 0.0, "details": {}}

        except Exception as e:
            logger.error(f"Coverage analysis error: {e}")
            return {"coverage": 0.0, "details": {}, "error": str(e)}

    def validate_code_sync(self, code: str, language: str = "python") -> Dict:
        """Synchronous version of validate_code"""
        try:
            response = self.gateway.call_sync(
                service="quality",
                path="/api/execute",
                method="POST",
                json={"code": code, "language": language},
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {"valid": False, "errors": [f"Validation failed: {response.status_code}"]}

        except Exception as e:
            logger.error(f"Code validation error: {e}")
            return {"valid": False, "errors": [str(e)]}


# Singleton instance
quality_service = QualityService()
