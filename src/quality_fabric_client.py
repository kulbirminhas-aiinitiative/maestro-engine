#!/usr/bin/env python3
"""
Quality-Fabric Client for MAESTRO Integration
HTTP client wrapper for calling Quality-Fabric Testing as a Service
"""

import asyncio
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class QualityFabricConfig:
    """Configuration for Quality-Fabric client"""

    api_url: str = "http://localhost:8000"
    timeout_seconds: int = 300
    retry_count: int = 3
    retry_delay_seconds: int = 5


@dataclass
class QualityValidationResult:
    """Quality validation result from Quality-Fabric"""

    execution_id: str
    success: bool
    quality_score: float  # 0-100
    security_score: float  # 0-100
    performance_score: float  # 0-100
    maintainability_score: float  # 0-100
    test_coverage: float  # 0-100
    total_tests: int
    passed_tests: int
    failed_tests: int
    error_tests: int
    duration: float
    detailed_results: Dict[str, Any]
    recommendations: List[str]
    issues: List[Dict[str, Any]]
    timestamp: float


class QualityFabricClient:
    """
    Client for Quality-Fabric Testing as a Service
    Provides interface to validate code quality and extract metrics
    """

    def __init__(self, config: QualityFabricConfig = None):
        self.config = config or QualityFabricConfig()
        self.client = httpx.AsyncClient(timeout=self.config.timeout_seconds)
        logger.info(f"Quality-Fabric client initialized: {self.config.api_url}")

    async def check_health(self) -> bool:
        """Check if Quality-Fabric service is available"""
        try:
            response = await self.client.get(f"{self.config.api_url}/api/health")
            if response.status_code == 200:
                logger.info("✅ Quality-Fabric service is healthy")
                return True
            else:
                logger.warning(f"⚠️ Quality-Fabric health check failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Quality-Fabric health check error: {e}")
            return False

    async def validate_workflow_output(
        self, workflow_result: Dict[str, Any], project_path: str = None
    ) -> Optional[QualityValidationResult]:
        """
        Validate workflow output using Quality-Fabric

        Args:
            workflow_result: Result from MAESTRO workflow execution
            project_path: Path to project files for validation

        Returns:
            QualityValidationResult if successful, None otherwise
        """
        try:
            logger.info("🔍 Starting Quality-Fabric validation...")

            # Check if service is available
            if not await self.check_health():
                logger.warning("Quality-Fabric service unavailable, skipping validation")
                return None

            # Prepare validation request
            validation_request = self._prepare_validation_request(workflow_result, project_path)

            # Execute validation via Quality-Fabric API
            execution_id = await self._execute_validation(validation_request)

            if not execution_id:
                logger.error("Failed to start Quality-Fabric validation")
                return None

            # Poll for results
            result = await self._poll_validation_results(execution_id)

            if result:
                logger.info(f"✅ Quality validation complete: Score {result.quality_score:.1f}/100")

            return result

        except Exception as e:
            logger.error(f"Quality-Fabric validation failed: {e}")
            return None

    def _prepare_validation_request(
        self, workflow_result: Dict[str, Any], project_path: str = None
    ) -> Dict[str, Any]:
        """Prepare validation request for Quality-Fabric"""

        files_generated = workflow_result.get("files_generated", [])
        project_path = project_path or workflow_result.get("project_path", "")

        # Determine test categories based on generated files
        categories = self._determine_test_categories(files_generated)

        return {
            "name": f"MAESTRO Validation {workflow_result.get('session_id', 'unknown')}",
            "description": f"Quality validation for: {workflow_result.get('requirement', 'N/A')}",
            "categories": categories,
            "parallel_execution": True,
            "fail_fast": False,
            "timeout_minutes": 30,
            "retry_count": 1,
            "custom_config": {
                "project_path": project_path,
                "files": files_generated,
                "maestro_session_id": workflow_result.get("session_id"),
                "team_members": workflow_result.get("team_members", []),
            },
        }

    def _determine_test_categories(self, files: List[str]) -> List[str]:
        """Determine appropriate test categories based on generated files"""
        categories = ["unit", "integration"]  # Default categories

        # Add categories based on file types
        file_extensions = {Path(f).suffix for f in files if isinstance(f, str)}

        if any(ext in [".py", ".js", ".ts", ".java"] for ext in file_extensions):
            categories.append("functional")

        if any(".html" in str(f) or ".jsx" in str(f) for f in files):
            categories.append("frontend")

        if "api" in str(files).lower():
            categories.append("api")

        return categories

    async def _execute_validation(self, request: Dict[str, Any]) -> Optional[str]:
        """Execute validation request on Quality-Fabric"""
        try:
            response = await self.client.post(f"{self.config.api_url}/api/execute", json=request)

            if response.status_code == 200:
                result = response.json()
                execution_id = result.get("execution_id")
                logger.info(f"Quality validation started: {execution_id}")
                return execution_id
            else:
                logger.error(
                    f"Failed to start validation: {response.status_code} - {response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"Error executing validation: {e}")
            return None

    async def _poll_validation_results(
        self, execution_id: str, poll_interval: int = 5, max_polls: int = 60
    ) -> Optional[QualityValidationResult]:
        """Poll for validation results until completion"""

        for attempt in range(max_polls):
            try:
                response = await self.client.get(
                    f"{self.config.api_url}/api/execute/{execution_id}"
                )

                if response.status_code != 200:
                    logger.warning(f"Failed to get status: {response.status_code}")
                    await asyncio.sleep(poll_interval)
                    continue

                status_data = response.json()
                status = status_data.get("status")

                logger.info(f"Validation status [{attempt+1}/{max_polls}]: {status}")

                if status in ["completed", "failed", "error"]:
                    # Get detailed results
                    return await self._fetch_detailed_results(execution_id, status_data)

                await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Error polling results: {e}")
                await asyncio.sleep(poll_interval)

        logger.warning(f"Validation polling timeout after {max_polls} attempts")
        return None

    async def _fetch_detailed_results(
        self, execution_id: str, status_data: Dict[str, Any]
    ) -> Optional[QualityValidationResult]:
        """Fetch detailed validation results"""
        try:
            # Get full results
            response = await self.client.get(f"{self.config.api_url}/api/results/{execution_id}")

            if response.status_code != 200:
                logger.warning(f"Could not fetch detailed results: {response.status_code}")
                # Fallback to status data
                return self._create_result_from_status(execution_id, status_data)

            results_data = response.json()

            # Calculate quality scores
            quality_score = self._calculate_quality_score(status_data, results_data)

            return QualityValidationResult(
                execution_id=execution_id,
                success=status_data.get("status") == "completed",
                quality_score=quality_score,
                security_score=self._extract_security_score(results_data),
                performance_score=self._extract_performance_score(results_data),
                maintainability_score=self._extract_maintainability_score(results_data),
                test_coverage=self._extract_test_coverage(results_data),
                total_tests=status_data.get("total_tests", 0),
                passed_tests=status_data.get("passed_tests", 0),
                failed_tests=status_data.get("failed_tests", 0),
                error_tests=status_data.get("error_tests", 0),
                duration=status_data.get("duration", 0),
                detailed_results=results_data.get("results", {}),
                recommendations=results_data.get("recommendations", []),
                issues=self._extract_issues(results_data),
                timestamp=time.time(),
            )

        except Exception as e:
            logger.error(f"Error fetching detailed results: {e}")
            return self._create_result_from_status(execution_id, status_data)

    def _create_result_from_status(
        self, execution_id: str, status_data: Dict[str, Any]
    ) -> QualityValidationResult:
        """Create result from status data when detailed results unavailable"""
        success_rate = status_data.get("success_rate", 0)
        quality_score = success_rate * 100 if success_rate <= 1 else success_rate

        return QualityValidationResult(
            execution_id=execution_id,
            success=status_data.get("status") == "completed",
            quality_score=quality_score,
            security_score=0,
            performance_score=0,
            maintainability_score=0,
            test_coverage=0,
            total_tests=status_data.get("total_tests", 0),
            passed_tests=status_data.get("passed_tests", 0),
            failed_tests=status_data.get("failed_tests", 0),
            error_tests=status_data.get("error_tests", 0),
            duration=status_data.get("duration", 0),
            detailed_results={},
            recommendations=[],
            issues=[],
            timestamp=time.time(),
        )

    def _calculate_quality_score(
        self, status_data: Dict[str, Any], results_data: Dict[str, Any]
    ) -> float:
        """Calculate overall quality score from validation results"""
        success_rate = status_data.get("success_rate", 0)
        base_score = success_rate * 100 if success_rate <= 1 else success_rate

        # Adjust based on error count
        error_tests = status_data.get("error_tests", 0)
        total_tests = status_data.get("total_tests", 1)
        error_penalty = (error_tests / total_tests) * 20 if total_tests > 0 else 0

        return max(0, min(100, base_score - error_penalty))

    def _extract_security_score(self, results_data: Dict[str, Any]) -> float:
        """Extract security score from results"""
        # TODO: Implement when Quality-Fabric provides security metrics
        return 0

    def _extract_performance_score(self, results_data: Dict[str, Any]) -> float:
        """Extract performance score from results"""
        # TODO: Implement when Quality-Fabric provides performance metrics
        return 0

    def _extract_maintainability_score(self, results_data: Dict[str, Any]) -> float:
        """Extract maintainability score from results"""
        # TODO: Implement when Quality-Fabric provides maintainability metrics
        return 0

    def _extract_test_coverage(self, results_data: Dict[str, Any]) -> float:
        """Extract test coverage from results"""
        # TODO: Implement when Quality-Fabric provides coverage metrics
        return 0

    def _extract_issues(self, results_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract issues from validation results"""
        issues = []
        results = results_data.get("results", {})

        if isinstance(results, dict):
            for key, value in results.items():
                if isinstance(value, dict) and value.get("status") == "failed":
                    issues.append(
                        {
                            "component": key,
                            "severity": "high",
                            "message": value.get("error", "Test failed"),
                        }
                    )

        return issues

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
        logger.info("Quality-Fabric client closed")


async def validate_with_quality_fabric(
    workflow_result: Dict[str, Any], config: QualityFabricConfig = None
) -> Optional[QualityValidationResult]:
    """
    Convenience function to validate workflow output

    Usage:
        result = await validate_with_quality_fabric(workflow_result)
        if result and result.quality_score > 80:
            print("High quality code generated!")
    """
    client = QualityFabricClient(config)
    try:
        return await client.validate_workflow_output(workflow_result)
    finally:
        await client.close()


if __name__ == "__main__":
    # Test the client
    async def test_client():
        client = QualityFabricClient()

        # Test health check
        healthy = await client.check_health()
        print(f"Quality-Fabric healthy: {healthy}")

        # Test validation with mock data
        mock_result = {
            "session_id": "test_123",
            "requirement": "Test validation",
            "files_generated": ["test.py", "main.py"],
            "project_path": "/tmp/test_project",
        }

        validation = await client.validate_workflow_output(mock_result)
        if validation:
            print(f"Quality Score: {validation.quality_score}")
            print(f"Tests: {validation.passed_tests}/{validation.total_tests}")

        await client.close()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_client())
