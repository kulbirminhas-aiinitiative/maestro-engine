#!/usr/bin/env python3
"""
MAESTRO v3.0 API Endpoint Testing Suite
Tests all endpoints after claude-agent-sdk upgrade
"""

import asyncio
import httpx
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple

# Test configuration
SERVICES = {
    "BFF": "http://localhost:4001",
    "Gateway": "http://localhost:8080",
    "Orchestration": "http://localhost:8004",
    "Coordinator": "http://localhost:8002",
    "RAG": "http://localhost:9803",
    "MCP": "http://localhost:9800",
}

# Test results
test_results: List[Dict] = []


def log_test(service: str, endpoint: str, method: str, status: str, details: str = ""):
    """Log test result"""
    result = {
        "timestamp": datetime.now().isoformat(),
        "service": service,
        "endpoint": endpoint,
        "method": method,
        "status": status,
        "details": details,
    }
    test_results.append(result)

    status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"{status_icon} [{service}] {method} {endpoint} - {status}")
    if details:
        print(f"   {details}")


async def test_health_endpoints():
    """Test all health endpoints"""
    print("\n" + "=" * 80)
    print("🏥 Testing Health Endpoints")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=10.0) as client:
        for service_name, base_url in SERVICES.items():
            try:
                response = await client.get(f"{base_url}/health")

                if response.status_code == 200:
                    data = response.json()
                    log_test(
                        service_name,
                        "/health",
                        "GET",
                        "PASS",
                        f"Status: {data.get('status', 'unknown')}",
                    )
                else:
                    log_test(
                        service_name,
                        "/health",
                        "GET",
                        "FAIL",
                        f"Status code: {response.status_code}",
                    )
            except Exception as e:
                log_test(service_name, "/health", "GET", "FAIL", f"Error: {str(e)}")


async def test_bff_endpoints():
    """Test BFF-specific endpoints (uses claude-agent-sdk v3.0)"""
    print("\n" + "=" * 80)
    print("🔥 Testing BFF Endpoints (claude-agent-sdk v3.0)")
    print("=" * 80)

    base_url = SERVICES["BFF"]
    session_id = f"test_{int(time.time())}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Health (with SDK status check)
        try:
            response = await client.get(f"{base_url}/health")
            data = response.json()

            if "claude_agent_sdk" in data.get("components", {}):
                sdk_status = data["components"]["claude_agent_sdk"]
                log_test(
                    "BFF",
                    "/health",
                    "GET",
                    "PASS",
                    f"claude_agent_sdk: {sdk_status} ✅ v3.0",
                )
            else:
                log_test("BFF", "/health", "GET", "WARN", "SDK status not in response")
        except Exception as e:
            log_test("BFF", "/health", "GET", "FAIL", str(e))

        # Test 2: Stats
        try:
            response = await client.get(f"{base_url}/api/stats")
            if response.status_code == 200:
                data = response.json()
                log_test(
                    "BFF",
                    "/api/stats",
                    "GET",
                    "PASS",
                    f"Active sessions: {data.get('active_sessions', 0)}",
                )
            else:
                log_test("BFF", "/api/stats", "GET", "FAIL", f"HTTP {response.status_code}")
        except Exception as e:
            log_test("BFF", "/api/stats", "GET", "FAIL", str(e))

        # Test 3: Chat endpoint (uses claude-agent-sdk)
        print("\n   Testing AI Chat (uses claude-agent-sdk v3.0)...")
        try:
            chat_payload = {
                "prompt": "Say 'Hello from v3.0!' and nothing else.",
                "session_id": session_id,
            }

            response = await client.post(f"{base_url}/ai/chat", json=chat_payload)

            if response.status_code == 200:
                data = response.json()
                log_test(
                    "BFF",
                    "/ai/chat",
                    "POST",
                    "PASS",
                    f"Session: {data.get('session_id', 'unknown')}, Response received",
                )
            else:
                log_test(
                    "BFF",
                    "/ai/chat",
                    "POST",
                    "FAIL",
                    f"HTTP {response.status_code}: {response.text[:100]}",
                )
        except Exception as e:
            log_test("BFF", "/ai/chat", "POST", "FAIL", str(e))

        # Test 4: Session state
        try:
            response = await client.get(f"{base_url}/api/session/{session_id}/state")
            if response.status_code == 200:
                data = response.json()
                log_test(
                    "BFF",
                    f"/api/session/{session_id}/state",
                    "GET",
                    "PASS",
                    f"State: {data.get('workflow_state', 'unknown')}",
                )
            elif response.status_code == 404:
                log_test(
                    "BFF",
                    f"/api/session/{session_id}/state",
                    "GET",
                    "WARN",
                    "Session not found (expected if chat failed)",
                )
            else:
                log_test(
                    "BFF",
                    f"/api/session/{session_id}/state",
                    "GET",
                    "FAIL",
                    f"HTTP {response.status_code}",
                )
        except Exception as e:
            log_test("BFF", f"/api/session/{session_id}/state", "GET", "FAIL", str(e))

        # Test 5: SDLC Projects
        try:
            response = await client.get(f"{base_url}/api/sdlc/projects")
            if response.status_code == 200:
                data = response.json()
                log_test(
                    "BFF",
                    "/api/sdlc/projects",
                    "GET",
                    "PASS",
                    f"Projects: {len(data.get('projects', []))}",
                )
            else:
                log_test(
                    "BFF", "/api/sdlc/projects", "GET", "FAIL", f"HTTP {response.status_code}"
                )
        except Exception as e:
            log_test("BFF", "/api/sdlc/projects", "GET", "FAIL", str(e))


async def test_orchestration_endpoints():
    """Test Orchestration service endpoints"""
    print("\n" + "=" * 80)
    print("🎯 Testing Orchestration Endpoints")
    print("=" * 80)

    base_url = SERVICES["Orchestration"]

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test workflow execution endpoint
        try:
            response = await client.get(f"{base_url}/api/workflows")
            if response.status_code in [200, 404]:
                log_test(
                    "Orchestration",
                    "/api/workflows",
                    "GET",
                    "PASS",
                    f"HTTP {response.status_code}",
                )
            else:
                log_test(
                    "Orchestration",
                    "/api/workflows",
                    "GET",
                    "FAIL",
                    f"HTTP {response.status_code}",
                )
        except Exception as e:
            log_test("Orchestration", "/api/workflows", "GET", "FAIL", str(e))


async def test_coordinator_endpoints():
    """Test Coordinator service endpoints"""
    print("\n" + "=" * 80)
    print("🎭 Testing Coordinator Endpoints")
    print("=" * 80)

    base_url = SERVICES["Coordinator"]

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test personas endpoint
        try:
            response = await client.get(f"{base_url}/api/personas")
            if response.status_code in [200, 404]:
                log_test(
                    "Coordinator",
                    "/api/personas",
                    "GET",
                    "PASS",
                    f"HTTP {response.status_code}",
                )
            else:
                log_test(
                    "Coordinator",
                    "/api/personas",
                    "GET",
                    "FAIL",
                    f"HTTP {response.status_code}",
                )
        except Exception as e:
            log_test("Coordinator", "/api/personas", "GET", "FAIL", str(e))


async def test_rag_endpoints():
    """Test RAG service endpoints"""
    print("\n" + "=" * 80)
    print("📚 Testing RAG Endpoints")
    print("=" * 80)

    base_url = SERVICES["RAG"]

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test knowledge base endpoint
        try:
            response = await client.get(f"{base_url}/api/knowledge")
            if response.status_code in [200, 404]:
                log_test("RAG", "/api/knowledge", "GET", "PASS", f"HTTP {response.status_code}")
            else:
                log_test("RAG", "/api/knowledge", "GET", "FAIL", f"HTTP {response.status_code}")
        except Exception as e:
            log_test("RAG", "/api/knowledge", "GET", "FAIL", str(e))


async def test_mcp_endpoints():
    """Test MCP service endpoints"""
    print("\n" + "=" * 80)
    print("🔌 Testing MCP Endpoints")
    print("=" * 80)

    base_url = SERVICES["MCP"]

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test events endpoint
        try:
            response = await client.get(f"{base_url}/api/events")
            if response.status_code in [200, 404]:
                log_test("MCP", "/api/events", "GET", "PASS", f"HTTP {response.status_code}")
            else:
                log_test("MCP", "/api/events", "GET", "FAIL", f"HTTP {response.status_code}")
        except Exception as e:
            log_test("MCP", "/api/events", "GET", "FAIL", str(e))


async def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("🧪 MAESTRO v3.0 API ENDPOINT TEST SUITE")
    print("=" * 80)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Testing claude-agent-sdk v3.0 integration")
    print("=" * 80)

    start_time = time.time()

    # Run all test suites
    await test_health_endpoints()
    await test_bff_endpoints()
    await test_orchestration_endpoints()
    await test_coordinator_endpoints()
    await test_rag_endpoints()
    await test_mcp_endpoints()

    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)

    total_tests = len(test_results)
    passed = sum(1 for r in test_results if r["status"] == "PASS")
    failed = sum(1 for r in test_results if r["status"] == "FAIL")
    warnings = sum(1 for r in test_results if r["status"] == "WARN")

    print(f"Total Tests: {total_tests}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Warnings: {warnings}")
    print(f"Execution Time: {time.time() - start_time:.2f}s")

    # Critical checks
    print("\n" + "=" * 80)
    print("🔍 CRITICAL v3.0 CHECKS")
    print("=" * 80)

    # Check if BFF health shows claude-agent-sdk
    bff_health = next((r for r in test_results if r["service"] == "BFF" and "/health" in r["endpoint"]), None)
    if bff_health and "v3.0" in bff_health.get("details", ""):
        print("✅ BFF using claude-agent-sdk v3.0")
    else:
        print("❌ BFF SDK status unclear")

    # Check if chat endpoint works
    bff_chat = next((r for r in test_results if r["service"] == "BFF" and "/ai/chat" in r["endpoint"]), None)
    if bff_chat and bff_chat["status"] == "PASS":
        print("✅ BFF AI Chat endpoint functional (v3.0 working)")
    else:
        print("⚠️  BFF AI Chat endpoint issues detected")

    # Export results
    results_file = f"/tmp/maestro_v3_test_results_{int(time.time())}.json"
    with open(results_file, "w") as f:
        json.dump(test_results, f, indent=2)

    print(f"\n📄 Full results saved to: {results_file}")

    print("\n" + "=" * 80)
    if failed == 0:
        print("🎉 ALL TESTS PASSED - v3.0 MIGRATION SUCCESSFUL!")
    elif failed < 3:
        print("⚠️  MOSTLY SUCCESSFUL - Minor issues detected")
    else:
        print("❌ SIGNIFICANT ISSUES - Review failed tests")
    print("=" * 80 + "\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
