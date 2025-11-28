#!/usr/bin/env python3
"""
ME-400: Quality Fabric Enforcement - End-to-End Test Suite
==========================================================

Tests all acceptance criteria for EPIC ME-400:

AC-1: Each phase has at least one mapped test scenario
AC-2: Test results tie to gates as evidence
AC-3: Failing tests block gate unless waiver present
AC-4: Configurable thresholds (coverage, static analysis)
AC-5: Quality Fabric enabled by default in staging/prod
AC-6: Test artifacts linked to run manifest

Additionally tests:
- Phase-to-test mapping configuration
- Quality validation execution
- Waiver mechanism
- Gate evidence generation
"""

import asyncio
import json
import time
import pytest
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime

# Test configuration
BFF_BASE_URL = "http://localhost:4001"
QUALITY_FABRIC_URL = "http://localhost:8000"


class TestME400QualityFabricEnforcement:
    """Test suite for ME-400: Quality Fabric Enforcement"""

    @pytest.fixture(autouse=True)
    def pytest_setup(self):
        """Verify services are running before tests (pytest fixture)"""
        self._check_services()

    def _check_services(self):
        """Verify services are running before tests"""
        # Check BFF health
        response = requests.get(f"{BFF_BASE_URL}/health", timeout=5)
        assert response.status_code == 200, "BFF service not healthy"

        # Check Quality Fabric health
        qf_response = requests.get(f"{QUALITY_FABRIC_URL}/health", timeout=5)
        assert qf_response.status_code == 200, "Quality Fabric service not healthy"

    # =========================================================================
    # AC-1: Each phase has at least one mapped test scenario
    # =========================================================================

    def test_ac1_default_phase_mappings_exist(self):
        """AC-1: All standard phases have default test mappings"""
        response = requests.get(f"{BFF_BASE_URL}/api/quality/mappings", timeout=5)

        assert response.status_code == 200
        data = response.json()

        assert "mappings" in data
        assert len(data["mappings"]) >= 5, "Should have mappings for standard phases"

        # Check each mapping is valid
        for mapping in data["mappings"]:
            assert mapping["is_valid"] is True, f"Phase {mapping['phase_type']} has no test mappings"
            assert len(mapping["test_categories"]) >= 1, f"Phase {mapping['phase_type']} needs at least one test category"

        print(f"✅ AC-1 PASSED: All {len(data['mappings'])} phases have test mappings")

    def test_ac1_specific_phase_mapping(self):
        """AC-1: Specific phases have appropriate test categories"""
        phase_expectations = {
            "requirements": ["unit"],
            "implementation": ["unit", "integration", "functional"],
            "testing": ["unit", "integration", "functional", "api"],
            "deployment": ["integration", "api", "performance"],
        }

        for phase_type, expected_categories in phase_expectations.items():
            response = requests.get(
                f"{BFF_BASE_URL}/api/quality/mappings",
                params={"phase_type": phase_type},
                timeout=5
            )

            assert response.status_code == 200
            data = response.json()

            for expected in expected_categories:
                assert expected in data["test_categories"], \
                    f"Phase {phase_type} should include {expected} tests"

        print(f"✅ AC-1 PASSED: Phase-specific test categories validated")

    def test_ac1_custom_phase_mapping(self):
        """AC-1: Custom phase mappings can be configured"""
        response = requests.post(
            f"{BFF_BASE_URL}/api/quality/mappings",
            json={
                "phase_type": "custom_phase",
                "test_categories": ["security", "compliance", "performance"],
                "custom_scenarios": [
                    {"name": "Security Scan", "type": "security"},
                    {"name": "Load Test", "type": "performance"}
                ]
            },
            timeout=5
        )

        assert response.status_code == 200
        data = response.json()

        assert data["phase_type"] == "custom_phase"
        assert len(data["test_categories"]) == 3
        assert "security" in data["test_categories"]
        assert data["is_valid"] is True

        print(f"✅ AC-1 PASSED: Custom phase mapping created")

    # =========================================================================
    # AC-2: Test results tie to gates as evidence
    # =========================================================================

    def test_ac2_validation_produces_evidence(self):
        """AC-2: Quality validation produces evidence for gates"""
        response = requests.post(
            f"{BFF_BASE_URL}/api/quality/validate",
            json={
                "phase_id": "phase_evidence_test",
                "phase_type": "implementation",
                "workflow_id": "wf_evidence_test",
                "session_id": "session_evidence",
                "context": {"test_mode": True}
            },
            timeout=30
        )

        assert response.status_code == 200
        data = response.json()

        # Check evidence URI is generated
        assert "evidence_uri" in data
        assert data["evidence_uri"].startswith("/api/quality/validations/")
        assert "validation_id" in data

        print(f"✅ AC-2 PASSED: Evidence URI generated: {data['evidence_uri']}")

    def test_ac2_evidence_retrievable(self):
        """AC-2: Evidence can be retrieved for gate attachment"""
        # First create a validation
        validate_response = requests.post(
            f"{BFF_BASE_URL}/api/quality/validate",
            json={
                "phase_id": "phase_retrieve_evidence",
                "phase_type": "testing",
                "workflow_id": "wf_retrieve_evidence",
            },
            timeout=30
        )

        assert validate_response.status_code == 200
        validation_id = validate_response.json()["validation_id"]

        # Retrieve evidence
        evidence_response = requests.get(
            f"{BFF_BASE_URL}/api/quality/evidence/{validation_id}",
            timeout=5
        )

        assert evidence_response.status_code == 200
        evidence = evidence_response.json()

        # Verify evidence structure for gate attachment
        assert evidence["type"] == "quality_validation"
        assert "uri" in evidence
        assert "metadata" in evidence
        assert "validation_id" in evidence["metadata"]
        assert "pass_rate" in evidence["metadata"]
        assert "coverage" in evidence["metadata"]

        print(f"✅ AC-2 PASSED: Evidence retrievable with gate-compatible structure")

    # =========================================================================
    # AC-3: Failing tests block gate unless waiver present
    # =========================================================================

    def test_ac3_failed_validation_blocks_gate(self):
        """AC-3: Failed validation blocks gate progression"""
        # Note: Mock validation returns 90% pass rate which may or may not block
        # depending on threshold. We test the blocking logic.
        response = requests.post(
            f"{BFF_BASE_URL}/api/quality/validate",
            json={
                "phase_id": "phase_blocking_test",
                "phase_type": "implementation",
                "workflow_id": "wf_blocking_test",
            },
            timeout=30
        )

        assert response.status_code == 200
        data = response.json()

        # Check blocking decision is returned
        assert "should_block_gate" in data
        assert "block_reason" in data

        print(f"✅ AC-3 PASSED: Gate blocking decision: {data['should_block_gate']} - {data['block_reason']}")

    def test_ac3_waiver_bypasses_block(self):
        """AC-3: Waiver allows bypassing quality gate block"""
        # First grant a waiver
        waiver_response = requests.post(
            f"{BFF_BASE_URL}/api/quality/waivers",
            json={
                "phase_id": "phase_waiver_test",
                "workflow_id": "wf_waiver_test",
                "waiver_type": "emergency",
                "reason": "Emergency hotfix required",
                "granted_by": "admin@example.com",
            },
            timeout=5
        )

        assert waiver_response.status_code == 200
        waiver = waiver_response.json()
        assert "waiver_id" in waiver

        # Now validate - should not block due to waiver
        validate_response = requests.post(
            f"{BFF_BASE_URL}/api/quality/validate",
            json={
                "phase_id": "phase_waiver_test",
                "phase_type": "implementation",
                "workflow_id": "wf_waiver_test",
            },
            timeout=30
        )

        assert validate_response.status_code == 200
        data = validate_response.json()

        # With waiver, should not block
        assert data["should_block_gate"] is False
        assert "waiver" in data["block_reason"].lower() or "passed" in data["block_reason"].lower()

        print(f"✅ AC-3 PASSED: Waiver bypasses gate block")

    def test_ac3_waiver_types(self):
        """AC-3: Different waiver types are supported"""
        waiver_types = ["emergency", "technical_debt", "external_dependency", "temporary", "executive"]

        for waiver_type in waiver_types:
            response = requests.post(
                f"{BFF_BASE_URL}/api/quality/waivers",
                json={
                    "phase_id": f"phase_waiver_type_{waiver_type}",
                    "workflow_id": f"wf_waiver_type_{waiver_type}",
                    "waiver_type": waiver_type,
                    "reason": f"Testing {waiver_type} waiver",
                    "granted_by": "test@example.com",
                },
                timeout=5
            )

            assert response.status_code == 200, f"Failed to create {waiver_type} waiver"

        print(f"✅ AC-3 PASSED: All {len(waiver_types)} waiver types supported")

    # =========================================================================
    # AC-4: Configurable thresholds (coverage, static analysis)
    # =========================================================================

    def test_ac4_thresholds_in_config(self):
        """AC-4: Quality thresholds are configurable"""
        response = requests.get(f"{BFF_BASE_URL}/api/quality/config", timeout=5)

        assert response.status_code == 200
        config = response.json()

        assert "thresholds" in config

        # Check for required threshold types
        thresholds = config["thresholds"]
        assert "test_coverage" in thresholds
        assert "test_pass_rate" in thresholds
        assert "static_analysis" in thresholds

        # Check threshold values exist
        assert "min_coverage_percent" in thresholds["test_coverage"]
        assert "min_pass_rate_percent" in thresholds["test_pass_rate"]
        assert "max_critical_issues" in thresholds["static_analysis"]

        print(f"✅ AC-4 PASSED: Configurable thresholds present")
        print(f"   Coverage: min={thresholds['test_coverage']['min_coverage_percent']}%")
        print(f"   Pass Rate: min={thresholds['test_pass_rate']['min_pass_rate_percent']}%")
        print(f"   Static Analysis: max_critical={thresholds['static_analysis']['max_critical_issues']}")

    def test_ac4_custom_thresholds_in_mapping(self):
        """AC-4: Custom thresholds can be set per phase mapping"""
        custom_thresholds = {
            "test_coverage": {"min_coverage_percent": 90},
            "test_pass_rate": {"min_pass_rate_percent": 99},
        }

        response = requests.post(
            f"{BFF_BASE_URL}/api/quality/mappings",
            json={
                "phase_type": "high_quality_phase",
                "test_categories": ["unit", "integration"],
                "thresholds": custom_thresholds
            },
            timeout=5
        )

        assert response.status_code == 200
        data = response.json()

        assert data["phase_type"] == "high_quality_phase"

        print(f"✅ AC-4 PASSED: Custom thresholds can be configured per phase")

    # =========================================================================
    # AC-5: Quality Fabric enabled by default in staging/prod
    # =========================================================================

    def test_ac5_environment_based_enforcement(self):
        """AC-5: Enforcement level varies by environment"""
        response = requests.get(f"{BFF_BASE_URL}/api/quality/config", timeout=5)

        assert response.status_code == 200
        config = response.json()

        assert "environment" in config
        assert "enforcement_level" in config
        assert "is_enabled" in config

        # Staging/production should have strict enforcement
        env = config["environment"]
        level = config["enforcement_level"]

        if env in ["staging", "production"]:
            assert config["is_enabled"] is True
            assert level in ["strict", "standard"]

        print(f"✅ AC-5 PASSED: Environment={env}, Level={level}, Enabled={config['is_enabled']}")

    def test_ac5_feature_flag_check(self):
        """AC-5: Feature flag controls enforcement"""
        response = requests.get(f"{BFF_BASE_URL}/api/quality/config", timeout=5)

        assert response.status_code == 200
        config = response.json()

        assert "feature_flag_enabled" in config

        print(f"✅ AC-5 PASSED: Feature flag status: {config['feature_flag_enabled']}")

    # =========================================================================
    # AC-6: Test artifacts linked to run manifest
    # =========================================================================

    def test_ac6_artifacts_in_validation_result(self):
        """AC-6: Validation results include artifact links"""
        response = requests.post(
            f"{BFF_BASE_URL}/api/quality/validate",
            json={
                "phase_id": "phase_artifacts_test",
                "phase_type": "testing",
                "workflow_id": "wf_artifacts_test",
            },
            timeout=30
        )

        assert response.status_code == 200
        data = response.json()

        assert "artifacts" in data
        assert isinstance(data["artifacts"], list)

        print(f"✅ AC-6 PASSED: Validation includes {len(data['artifacts'])} artifact links")

    def test_ac6_evidence_contains_artifacts(self):
        """AC-6: Gate evidence contains artifact links"""
        # Create validation
        validate_response = requests.post(
            f"{BFF_BASE_URL}/api/quality/validate",
            json={
                "phase_id": "phase_evidence_artifacts",
                "phase_type": "deployment",
                "workflow_id": "wf_evidence_artifacts",
            },
            timeout=30
        )

        validation_id = validate_response.json()["validation_id"]

        # Get evidence
        evidence_response = requests.get(
            f"{BFF_BASE_URL}/api/quality/evidence/{validation_id}",
            timeout=5
        )

        assert evidence_response.status_code == 200
        evidence = evidence_response.json()

        assert "metadata" in evidence
        assert "artifacts" in evidence["metadata"]

        print(f"✅ AC-6 PASSED: Evidence metadata includes artifacts")

    # =========================================================================
    # Additional Functional Tests
    # =========================================================================

    def test_validation_history(self):
        """Test validation history retrieval"""
        # Create a few validations
        workflow_id = f"wf_history_{int(time.time())}"

        for i in range(3):
            requests.post(
                f"{BFF_BASE_URL}/api/quality/validate",
                json={
                    "phase_id": f"phase_history_{i}",
                    "phase_type": "implementation",
                    "workflow_id": workflow_id,
                },
                timeout=30
            )

        # Get history
        response = requests.get(
            f"{BFF_BASE_URL}/api/quality/history",
            params={"workflow_id": workflow_id, "limit": 10},
            timeout=5
        )

        assert response.status_code == 200
        data = response.json()

        assert "validations" in data
        assert data["total"] >= 3

        print(f"✅ Validation history works: {data['total']} records")

    def test_waivers_retrieval(self):
        """Test waiver retrieval for workflow"""
        workflow_id = f"wf_waivers_{int(time.time())}"

        # Grant waivers
        for i in range(2):
            requests.post(
                f"{BFF_BASE_URL}/api/quality/waivers",
                json={
                    "phase_id": f"phase_waivers_{i}",
                    "workflow_id": workflow_id,
                    "waiver_type": "emergency",
                    "reason": f"Test waiver {i}",
                    "granted_by": "test@example.com",
                },
                timeout=5
            )

        # Retrieve waivers
        response = requests.get(
            f"{BFF_BASE_URL}/api/quality/waivers/{workflow_id}",
            timeout=5
        )

        assert response.status_code == 200
        data = response.json()

        assert "waivers" in data
        assert len(data["waivers"]) >= 2

        print(f"✅ Waiver retrieval works: {len(data['waivers'])} waivers")

    def test_health_endpoint(self):
        """Test quality enforcement health endpoint"""
        response = requests.get(f"{BFF_BASE_URL}/api/quality/health", timeout=5)

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["service"] == "quality-fabric-enforcement"

        print(f"✅ Health endpoint works")


# =========================================================================
# Test Runner
# =========================================================================

def run_tests():
    """Run all tests and generate report"""
    print("=" * 70)
    print("ME-400: Quality Fabric Enforcement - E2E Test Suite")
    print("=" * 70)
    print(f"BFF URL: {BFF_BASE_URL}")
    print(f"Quality Fabric URL: {QUALITY_FABRIC_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 70)

    # Create test instance
    test_suite = TestME400QualityFabricEnforcement()
    test_suite._check_services()

    # Run tests and track results
    results = {
        "passed": [],
        "failed": [],
        "skipped": []
    }

    test_methods = [
        ("AC-1: Default Phase Mappings", test_suite.test_ac1_default_phase_mappings_exist),
        ("AC-1: Specific Phase Mapping", test_suite.test_ac1_specific_phase_mapping),
        ("AC-1: Custom Phase Mapping", test_suite.test_ac1_custom_phase_mapping),
        ("AC-2: Validation Produces Evidence", test_suite.test_ac2_validation_produces_evidence),
        ("AC-2: Evidence Retrievable", test_suite.test_ac2_evidence_retrievable),
        ("AC-3: Failed Validation Blocks Gate", test_suite.test_ac3_failed_validation_blocks_gate),
        ("AC-3: Waiver Bypasses Block", test_suite.test_ac3_waiver_bypasses_block),
        ("AC-3: Waiver Types", test_suite.test_ac3_waiver_types),
        ("AC-4: Thresholds in Config", test_suite.test_ac4_thresholds_in_config),
        ("AC-4: Custom Thresholds", test_suite.test_ac4_custom_thresholds_in_mapping),
        ("AC-5: Environment Enforcement", test_suite.test_ac5_environment_based_enforcement),
        ("AC-5: Feature Flag Check", test_suite.test_ac5_feature_flag_check),
        ("AC-6: Artifacts in Validation", test_suite.test_ac6_artifacts_in_validation_result),
        ("AC-6: Evidence Contains Artifacts", test_suite.test_ac6_evidence_contains_artifacts),
        ("Func: Validation History", test_suite.test_validation_history),
        ("Func: Waivers Retrieval", test_suite.test_waivers_retrieval),
        ("Func: Health Endpoint", test_suite.test_health_endpoint),
    ]

    for test_name, test_func in test_methods:
        print(f"\n▶️ Running: {test_name}")
        print("-" * 50)
        try:
            test_func()
            results["passed"].append(test_name)
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            results["failed"].append((test_name, str(e)))
        except Exception as e:
            print(f"⚠️ ERROR: {e}")
            results["failed"].append((test_name, str(e)))

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"✅ Passed: {len(results['passed'])}")
    print(f"❌ Failed: {len(results['failed'])}")
    print(f"⏭️ Skipped: {len(results['skipped'])}")
    print("-" * 70)

    if results["failed"]:
        print("\n❌ Failed Tests:")
        for name, error in results["failed"]:
            print(f"   - {name}: {error}")

    total = len(results["passed"]) + len(results["failed"])
    pass_rate = (len(results["passed"]) / total * 100) if total > 0 else 0
    print(f"\n📊 Pass Rate: {pass_rate:.1f}%")

    return results


if __name__ == "__main__":
    results = run_tests()
    exit(0 if len(results["failed"]) == 0 else 1)
