#!/usr/bin/env python3
"""
Test MAESTRO Backend API
"""

import asyncio
import json

import httpx


async def test_health():
    """Test health endpoint"""
    print("=" * 80)
    print("Testing Health Endpoint")
    print("=" * 80)

    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5000/health")
        print(f"Status Code: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        print()


async def test_status():
    """Test status endpoint"""
    print("=" * 80)
    print("Testing Status Endpoint")
    print("=" * 80)

    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5000/status")
        print(f"Status Code: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        print()


async def test_workflow_execution():
    """Test workflow execution endpoint"""
    print("=" * 80)
    print("Testing Workflow Execution Endpoint")
    print("=" * 80)

    payload = {
        "requirement": "Create a simple Python function to calculate fibonacci numbers",
        "enable_utcp": False,  # Use local execution for testing
        "enable_rag": True,
        "max_execution_time": 300,
    }

    print(f"Request Payload:\n{json.dumps(payload, indent=2)}\n")

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=300.0)) as client:
        print("Sending request...")
        response = await client.post("http://localhost:5000/api/workflow/execute", json=payload)

        print(f"Status Code: {response.status_code}\n")

        if response.status_code == 200:
            result = response.json()
            print("Success!")
            print(f"Session ID: {result.get('session_id')}")
            print(f"Execution Method: {result.get('execution_method')}")
            print(f"Files Generated: {len(result.get('files_generated', []))}")
            print(f"Execution Time: {result.get('total_execution_time')}s")
            print(f"Project Path: {result.get('project_path')}")

            if result.get("files_generated"):
                print(f"\nGenerated Files:")
                for file in result["files_generated"][:5]:  # Show first 5
                    print(f"  - {file}")
        else:
            print("Error:")
            print(json.dumps(response.json(), indent=2))


async def main():
    """Main test runner"""
    print("\n")
    print("🧪 MAESTRO Backend API Test Suite")
    print("\n")

    # Test 1: Health check
    await test_health()

    # Test 2: Status
    await test_status()

    # Test 3: Workflow execution
    await test_workflow_execution()

    print("=" * 80)
    print("✅ Test Suite Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
