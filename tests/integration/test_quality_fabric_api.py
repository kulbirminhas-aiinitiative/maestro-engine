"""
Quality Fabric API Integration Tests
Epic MD-1876: API Validation Layer Phase 2 - Hardening
Task MD-1729: Write Integration Tests

End-to-end tests for Quality Fabric API endpoints at localhost:8000
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Tuple

# Test configuration
BASE_URL = "http://localhost:8000"
TEST_RESULTS: List[Dict[str, Any]] = []


def run_test(test_id: str, test_name: str, test_fn) -> Dict[str, Any]:
    """Run a test and track results"""
    start_time = time.time()
    status = "passed"
    error = None
    details = None

    try:
        details = test_fn()
    except Exception as e:
        status = "failed"
        error = str(e)

    duration = (time.time() - start_time) * 1000  # ms

    result = {
        "id": test_id,
        "name": test_name,
        "status": status,
        "duration": f"{duration:.2f}ms",
        "error": error,
        "details": details
    }

    TEST_RESULTS.append(result)
    icon = "✅" if status == "passed" else "❌"
    print(f"{icon} [{status.upper()}] {test_id}: {test_name}")
    if error:
        print(f"   Error: {error}")

    return result


# ============================================================================
# TC-QF-01: Health Check Tests
# ============================================================================

def test_health_check():
    """Test quality fabric health endpoint"""
    def _test():
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Expected healthy status"
        return data

    return run_test("TC-QF-01-01", "Health check returns healthy status", _test)


def test_api_health():
    """Test API health endpoint"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        return response.json()

    return run_test("TC-QF-01-02", "API health endpoint responds", _test)


# ============================================================================
# TC-QF-02: Categories and Templates Tests
# ============================================================================

def test_get_categories():
    """Test fetching test categories"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/categories", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, (list, dict)), "Expected list or dict response"
        return data

    return run_test("TC-QF-02-01", "Get test categories", _test)


def test_get_templates():
    """Test fetching test templates"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/templates", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        return data

    return run_test("TC-QF-02-02", "Get test templates", _test)


# ============================================================================
# TC-QF-03: Execution Tests
# ============================================================================

def test_execute_endpoint_exists():
    """Test that execute endpoint exists"""
    def _test():
        # Test with empty body to verify endpoint exists
        response = requests.post(
            f"{BASE_URL}/api/execute",
            json={},
            timeout=5
        )
        # 400 or 422 means endpoint exists but validation failed (expected)
        # 404 would mean endpoint doesn't exist
        assert response.status_code in [200, 400, 422], f"Expected 200/400/422, got {response.status_code}"
        return {"status_code": response.status_code}

    return run_test("TC-QF-03-01", "Execute endpoint exists", _test)


def test_execute_with_valid_request():
    """Test execution with valid request structure"""
    def _test():
        payload = {
            "test_type": "unit",
            "target": "sample",
            "options": {}
        }
        response = requests.post(
            f"{BASE_URL}/api/execute",
            json=payload,
            timeout=10
        )
        # Accept success or validation error
        assert response.status_code in [200, 201, 400, 422], f"Expected 200/201/400/422, got {response.status_code}"
        return response.json() if response.text else {"status": "no_content"}

    return run_test("TC-QF-03-02", "Execute with valid request structure", _test)


def test_get_executions():
    """Test fetching executions list"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/executions", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        return response.json()

    return run_test("TC-QF-03-03", "Get executions list", _test)


# ============================================================================
# TC-QF-04: Policy API Tests
# ============================================================================

def test_policy_health():
    """Test policy API health"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/v1/policy/health", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        return response.json()

    return run_test("TC-QF-04-01", "Policy API health check", _test)


def test_get_policy_rules():
    """Test fetching policy rules"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/v1/policy/rules", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        return response.json()

    return run_test("TC-QF-04-02", "Get policy rules", _test)


def test_policy_route():
    """Test policy routing endpoint"""
    def _test():
        payload = {
            "task_type": "code_review",
            "complexity": "medium",
            "context": {}
        }
        response = requests.post(
            f"{BASE_URL}/api/v1/policy/route",
            json=payload,
            timeout=5
        )
        # Accept success or validation error
        assert response.status_code in [200, 400, 422], f"Expected 200/400/422, got {response.status_code}"
        return response.json() if response.text else {}

    return run_test("TC-QF-04-03", "Policy route endpoint", _test)


# ============================================================================
# TC-QF-05: Adapters Tests
# ============================================================================

def test_get_adapters():
    """Test fetching available adapters"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/adapters", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        return response.json()

    return run_test("TC-QF-05-01", "Get available adapters", _test)


# ============================================================================
# TC-QF-06: AI Endpoints Tests
# ============================================================================

def test_ai_generate_tests():
    """Test AI test generation endpoint exists"""
    def _test():
        payload = {"code": "def hello(): return 'world'"}
        response = requests.post(
            f"{BASE_URL}/api/ai/generate-tests",
            json=payload,
            timeout=10
        )
        # Accept any non-5xx response
        assert response.status_code < 500, f"Server error: {response.status_code}"
        return {"status_code": response.status_code}

    return run_test("TC-QF-06-01", "AI generate tests endpoint", _test)


def test_ai_predict_failures():
    """Test AI failure prediction endpoint"""
    def _test():
        payload = {"test_history": []}
        response = requests.post(
            f"{BASE_URL}/api/ai/predict/failures",
            json=payload,
            timeout=5
        )
        assert response.status_code < 500, f"Server error: {response.status_code}"
        return {"status_code": response.status_code}

    return run_test("TC-QF-06-02", "AI predict failures endpoint", _test)


# ============================================================================
# TC-QF-07: Predictive Analytics Tests
# ============================================================================

def test_predictive_flaky_tests():
    """Test flaky tests detection endpoint"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/predictive/flaky-tests", timeout=5)
        # May require instance_id, so accept 400/422
        assert response.status_code in [200, 400, 422], f"Expected 200/400/422, got {response.status_code}"
        return {"status_code": response.status_code}

    return run_test("TC-QF-07-01", "Predictive flaky tests endpoint", _test)


def test_predictive_critical_modules():
    """Test critical modules detection endpoint"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/predictive/critical-modules", timeout=5)
        assert response.status_code in [200, 400, 422], f"Expected 200/400/422, got {response.status_code}"
        return {"status_code": response.status_code}

    return run_test("TC-QF-07-02", "Predictive critical modules endpoint", _test)


# ============================================================================
# TC-QF-08: Automation Tests
# ============================================================================

def test_automation_health():
    """Test automation service health"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/automation/health", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        return response.json()

    return run_test("TC-QF-08-01", "Automation service health", _test)


def test_automation_status():
    """Test automation status endpoint"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/automation/status", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        return response.json()

    return run_test("TC-QF-08-02", "Automation status endpoint", _test)


def test_automation_statistics():
    """Test automation statistics endpoint"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/automation/statistics", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        return response.json()

    return run_test("TC-QF-08-03", "Automation statistics endpoint", _test)


# ============================================================================
# TC-QF-09: Metrics Tests
# ============================================================================

def test_aggregated_metrics():
    """Test aggregated metrics endpoint"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/metrics/aggregated", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        return response.json()

    return run_test("TC-QF-09-01", "Aggregated metrics endpoint", _test)


def test_insights_endpoint():
    """Test insights endpoint"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/insights", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        return response.json()

    return run_test("TC-QF-09-02", "Insights endpoint", _test)


# ============================================================================
# TC-QF-10: Test Plans Tests
# ============================================================================

def test_get_test_plans():
    """Test fetching test plans"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/test-plans", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        return response.json()

    return run_test("TC-QF-10-01", "Get test plans", _test)


# ============================================================================
# TC-QF-11: Error Handling Tests
# ============================================================================

def test_404_handling():
    """Test 404 error handling"""
    def _test():
        response = requests.get(f"{BASE_URL}/api/nonexistent-endpoint", timeout=5)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        return {"status_code": response.status_code}

    return run_test("TC-QF-11-01", "404 error handling", _test)


def test_invalid_json_handling():
    """Test invalid JSON handling"""
    def _test():
        response = requests.post(
            f"{BASE_URL}/api/execute",
            data="not valid json",
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        # Should return 400 or 422 for invalid JSON
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        return {"status_code": response.status_code}

    return run_test("TC-QF-11-02", "Invalid JSON handling", _test)


def test_missing_required_fields():
    """Test missing required fields handling"""
    def _test():
        response = requests.post(
            f"{BASE_URL}/api/execute",
            json={},  # Empty payload, missing required fields
            timeout=5
        )
        # Should return 400 or 422 for missing fields
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        return {"status_code": response.status_code}

    return run_test("TC-QF-11-03", "Missing required fields handling", _test)


# ============================================================================
# Main Test Runner
# ============================================================================

def run_all_tests() -> Dict[str, Any]:
    """Run all quality fabric API tests"""
    print("═" * 60)
    print("   Quality Fabric API Integration Tests")
    print("   Epic: MD-1876 | Task: MD-1729")
    print("═" * 60)
    print()

    start_time = time.time()

    # Run all tests
    print("=== TC-QF-01: Health Check Tests ===\n")
    test_health_check()
    test_api_health()

    print("\n=== TC-QF-02: Categories and Templates Tests ===\n")
    test_get_categories()
    test_get_templates()

    print("\n=== TC-QF-03: Execution Tests ===\n")
    test_execute_endpoint_exists()
    test_execute_with_valid_request()
    test_get_executions()

    print("\n=== TC-QF-04: Policy API Tests ===\n")
    test_policy_health()
    test_get_policy_rules()
    test_policy_route()

    print("\n=== TC-QF-05: Adapters Tests ===\n")
    test_get_adapters()

    print("\n=== TC-QF-06: AI Endpoints Tests ===\n")
    test_ai_generate_tests()
    test_ai_predict_failures()

    print("\n=== TC-QF-07: Predictive Analytics Tests ===\n")
    test_predictive_flaky_tests()
    test_predictive_critical_modules()

    print("\n=== TC-QF-08: Automation Tests ===\n")
    test_automation_health()
    test_automation_status()
    test_automation_statistics()

    print("\n=== TC-QF-09: Metrics Tests ===\n")
    test_aggregated_metrics()
    test_insights_endpoint()

    print("\n=== TC-QF-10: Test Plans Tests ===\n")
    test_get_test_plans()

    print("\n=== TC-QF-11: Error Handling Tests ===\n")
    test_404_handling()
    test_invalid_json_handling()
    test_missing_required_fields()

    duration = (time.time() - start_time) * 1000

    passed = len([t for t in TEST_RESULTS if t["status"] == "passed"])
    failed = len([t for t in TEST_RESULTS if t["status"] == "failed"])
    total = len(TEST_RESULTS)

    print()
    print("═" * 60)
    print(f"   Results: {passed}/{total} passed, {failed} failed")
    print(f"   Duration: {duration:.2f}ms")
    print("═" * 60)

    report = {
        "epic": "MD-1876",
        "task": "MD-1729",
        "api": "quality-fabric",
        "base_url": BASE_URL,
        "executed_at": datetime.utcnow().isoformat() + "Z",
        "passed": passed,
        "failed": failed,
        "total": total,
        "pass_rate": f"{(passed/total)*100:.2f}%" if total > 0 else "0%",
        "duration": f"{duration:.2f}ms",
        "results": TEST_RESULTS
    }

    print("\n📊 Test Report:")
    print(json.dumps(report, indent=2))

    return report


if __name__ == "__main__":
    report = run_all_tests()
    exit(0 if report["failed"] == 0 else 1)
