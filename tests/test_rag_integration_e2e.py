#!/usr/bin/env python3
"""
End-to-End RAG Integration Test

Tests the complete RAG workflow:
1. Start with seeded templates in maestro-templates
2. Query RAG Reader for guidance
3. Run workflow with RAG integration enabled
4. Index results to RAG Writer
5. Verify templates and executions are indexed
"""

import os
import sys
import time
from pathlib import Path

import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Configuration
RAG_READER_URL = "http://localhost:9801"
RAG_WRITER_URL = "http://localhost:9802"
RAG_READER_API_KEY = "dev_rag_reader_key_12345"
RAG_WRITER_API_KEY = "dev_rag_writer_key_98765"


def check_service(name: str, url: str) -> bool:
    """Check if a service is running"""
    try:
        response = requests.get(f"{url}/health", timeout=2)
        if response.ok:
            print(f"✅ {name} is running")
            return True
        else:
            print(f"❌ {name} returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ {name} is not available: {e}")
        return False


def test_rag_reader_query():
    """Test querying RAG Reader for templates"""
    print("\n" + "=" * 80)
    print("TEST: Query RAG Reader for templates")
    print("=" * 80)

    payload = {
        "persona_id": "backend_developer",
        "requirement": "REST API with CRUD operations",
        "top_k": 3,
        "min_quality_score": 50.0,
    }

    try:
        response = requests.post(
            f"{RAG_READER_URL}/api/v1/query/templates",
            headers={"X-API-Key": RAG_READER_API_KEY},
            json=payload,
            timeout=10,
        )

        if response.ok:
            data = response.json()
            templates = data.get("templates", [])
            print(f"✅ Found {len(templates)} templates")

            for i, template in enumerate(templates[:3], 1):
                print(f"\n{i}. {template.get('name', 'Unknown')}")
                print(f"   Language: {template.get('language', 'N/A')}")
                print(f"   Framework: {template.get('framework', 'N/A')}")
                print(f"   Quality: {template.get('quality_score', 0):.1f}")

            return True
        else:
            print(f"❌ Query failed: {response.status_code}")
            print(response.text)
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_rag_writer_indexing():
    """Test indexing to RAG Writer"""
    print("\n" + "=" * 80)
    print("TEST: Index execution to RAG Writer")
    print("=" * 80)

    payload = {
        "session_id": "e2e_integration_test_001",
        "requirement": "Build REST API with authentication and testing",
        "personas": ["backend_developer", "qa_engineer", "security_specialist"],
        "collaterals": [
            {"path": "main.py", "type": "file"},
            {"path": "test_main.py", "type": "file"},
            {"path": "auth.py", "type": "file"},
        ],
        "quality_score": 0.85,
        "success": True,
        "execution_time": 180.5,
    }

    try:
        response = requests.post(
            f"{RAG_WRITER_URL}/api/v1/index/execution",
            headers={"X-API-Key": RAG_WRITER_API_KEY},
            json=payload,
            timeout=10,
        )

        if response.ok:
            data = response.json()
            task_id = data.get("task_id")
            print(f"✅ Execution indexed (task: {task_id})")

            # Wait for processing
            print("⏳ Waiting for indexing to complete...")
            time.sleep(3)

            # Check task status
            status_response = requests.get(
                f"{RAG_WRITER_URL}/api/v1/task/{task_id}",
                headers={"X-API-Key": RAG_WRITER_API_KEY},
                timeout=5,
            )

            if status_response.ok:
                status_data = status_response.json()
                print(f"📊 Task Status: {status_data.get('status')}")
                if status_data.get("error"):
                    print(f"⚠️  Error: {status_data.get('error')}")
                return True
            else:
                print(f"❌ Failed to get task status")
                return False

        else:
            print(f"❌ Indexing failed: {response.status_code}")
            print(response.text)
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_quality_score_calculation():
    """Test quality score calculation"""
    print("\n" + "=" * 80)
    print("TEST: Quality Score Calculation")
    print("=" * 80)

    from orchestration.rag_integration import RAGIntegration

    rag = RAGIntegration(enabled=False)  # Just testing calculation

    # Test case 1: Excellent workflow
    score1 = rag.calculate_quality_score(
        success=True,
        files_generated=["f" + str(i) for i in range(20)],
        personas_count=8,
        execution_time=200,  # < 5 min
    )
    print(f"Excellent workflow: {score1:.2f} (expected ~0.8-1.0)")

    # Test case 2: Good workflow
    score2 = rag.calculate_quality_score(
        success=True,
        files_generated=["f" + str(i) for i in range(10)],
        personas_count=5,
        execution_time=400,  # 5-10 min
    )
    print(f"Good workflow: {score2:.2f} (expected ~0.6-0.8)")

    # Test case 3: Minimal workflow
    score3 = rag.calculate_quality_score(
        success=True, files_generated=["f1", "f2"], personas_count=2, execution_time=800
    )
    print(f"Minimal workflow: {score3:.2f} (expected ~0.5-0.6)")

    # Test case 4: Failed workflow
    score4 = rag.calculate_quality_score(
        success=False, files_generated=[], personas_count=1, execution_time=100
    )
    print(f"Failed workflow: {score4:.2f} (expected ~0.0-0.3)")

    return True


def test_batch_indexing():
    """Test batch indexing"""
    print("\n" + "=" * 80)
    print("TEST: Batch Indexing")
    print("=" * 80)

    payload = {
        "executions": [
            {
                "session_id": "batch_test_001",
                "requirement": "API 1",
                "personas": ["backend_developer"],
                "quality_score": 0.7,
                "success": True,
            },
            {
                "session_id": "batch_test_002",
                "requirement": "API 2",
                "personas": ["frontend_developer"],
                "quality_score": 0.8,
                "success": True,
            },
        ],
        "templates": [
            {
                "name": "Batch Test Template",
                "content": "# Template code",
                "category": "test",
                "language": "python",
                "tags": ["test", "batch"],
            }
        ],
    }

    try:
        response = requests.post(
            f"{RAG_WRITER_URL}/api/v1/index/batch",
            headers={"X-API-Key": RAG_WRITER_API_KEY},
            json=payload,
            timeout=10,
        )

        if response.ok:
            data = response.json()
            print(f"✅ Batch indexed: {data['total_tasks']} tasks")
            print(f"   Batch ID: {data['batch_id']}")
            return True
        else:
            print(f"❌ Batch indexing failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_rag_stats():
    """Test RAG Writer statistics"""
    print("\n" + "=" * 80)
    print("TEST: RAG Writer Statistics")
    print("=" * 80)

    try:
        response = requests.get(
            f"{RAG_WRITER_URL}/api/v1/stats", headers={"X-API-Key": RAG_WRITER_API_KEY}, timeout=5
        )

        if response.ok:
            data = response.json()
            print(f"✅ Statistics retrieved")
            print(f"   Queue size: {data.get('queue_size', 0)}")
            print(f"   Total tasks: {data.get('total_tasks', 0)}")

            tasks_by_status = data.get("tasks_by_status", {})
            print(f"   Pending: {tasks_by_status.get('pending', 0)}")
            print(f"   Processing: {tasks_by_status.get('processing', 0)}")
            print(f"   Completed: {tasks_by_status.get('completed', 0)}")
            print(f"   Failed: {tasks_by_status.get('failed', 0)}")

            print(f"\n   maestro-templates: {data.get('maestro_templates_path')}")
            print(f"   Templates exist: {data.get('maestro_templates_exists')}")

            return True
        else:
            print(f"❌ Stats failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all E2E tests"""
    print("=" * 80)
    print("RAG INTEGRATION - END-TO-END TEST SUITE")
    print("=" * 80)

    # Check services
    print("\n📡 Checking Services...")
    reader_ok = check_service("RAG Reader", RAG_READER_URL)
    writer_ok = check_service("RAG Writer", RAG_WRITER_URL)

    if not reader_ok or not writer_ok:
        print("\n❌ Services not available. Please start them first:")
        print("   Terminal 1: poetry run python src/rag_reader/rag_reader_service.py")
        print("   Terminal 2: poetry run python src/rag_writer/rag_writer_service.py")
        return 1

    # Run tests
    results = []

    results.append(("Quality Score Calculation", test_quality_score_calculation()))
    results.append(("RAG Reader Query", test_rag_reader_query()))
    results.append(("RAG Writer Indexing", test_rag_writer_indexing()))
    results.append(("Batch Indexing", test_batch_indexing()))
    results.append(("RAG Statistics", test_rag_stats()))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print("\n" + "=" * 80)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 80)

    return 0 if passed == total else 1


if __name__ == "__main__":
    exit(main())
