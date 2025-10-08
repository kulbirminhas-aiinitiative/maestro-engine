#!/usr/bin/env python3
"""
Test RAG-Enhanced Workflow

This script runs a complete workflow with RAG integration enabled
to verify end-to-end functionality.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import logging

from orchestration.autonomous_sdlc_engine_v3_resumable import AutonomousSDLCEngineV3Resumable

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def run_rag_test_workflow():
    """Run a simple workflow with RAG integration enabled"""

    print("=" * 80)
    print("RAG-ENHANCED WORKFLOW TEST")
    print("=" * 80)
    print("\n📋 Test Configuration:")
    print("   - Requirement: Build a simple REST API with CRUD operations")
    print("   - Persona: backend_developer")
    print("   - RAG Integration: ENABLED")
    print("   - Output: /tmp/rag_test_workflow")
    print("\n" + "=" * 80)

    # Enable RAG integration
    os.environ["RAG_INTEGRATION_ENABLED"] = "true"
    os.environ["RAG_READER_URL"] = "http://localhost:9801"
    os.environ["RAG_WRITER_URL"] = "http://localhost:9802"

    try:
        # Ensure personas are loaded first
        from personas.adapter import get_adapter

        adapter = get_adapter()
        await adapter.ensure_loaded()

        # Create engine with RAG enabled
        engine = AutonomousSDLCEngineV3Resumable(
            selected_personas=["backend_developer"],
            output_dir="/tmp/rag_test_workflow",
            enable_rag=True,  # Enable RAG integration
        )

        print("\n🚀 Starting workflow execution...")
        print("   Watch for RAG integration messages:\n")
        print("   ✅ '📚 RAG Guidance for backend_developer' - RAG query before execution")
        print("   ✅ '📥 Workflow indexed to RAG Writer' - RAG indexing after execution")
        print("\n" + "=" * 80 + "\n")

        # Execute workflow
        result = await engine.execute(
            requirement="""
Build a simple REST API with the following requirements:
1. A FastAPI application with CRUD endpoints for a 'Product' resource
2. Include basic validation using Pydantic models
3. Add a health check endpoint
4. Use proper HTTP status codes
5. Keep it simple and focused - just the core API structure
            """.strip(),
            session_id="rag_test_001",
        )

        # Display results
        print("\n" + "=" * 80)
        print("📊 WORKFLOW EXECUTION RESULTS")
        print("=" * 80)
        print(f"✅ Success: {result['success']}")
        print(f"🆔 Session ID: {result['session_id']}")
        print(f"👥 Personas: {', '.join(result['executed_personas'])}")
        print(f"📁 Files Created: {result['file_count']}")
        print(f"⏱️  Duration: {result['total_duration']:.2f}s")
        print(f"📂 Output Directory: {result['project_dir']}")

        # RAG-specific results
        if result.get("rag_indexed"):
            print("\n" + "=" * 80)
            print("🔗 RAG INTEGRATION RESULTS")
            print("=" * 80)
            print(f"✅ RAG Indexed: {result['rag_indexed']}")
            print(f"🎯 Quality Score: {result.get('quality_score', 0):.2f}")
            print(f"📋 Task ID: {result.get('rag_task_id', 'N/A')}")
        else:
            print(
                "\n⚠️  RAG Integration: Not indexed (quality score may be too low or RAG disabled)"
            )

        # List generated files
        if result["file_count"] > 0:
            print("\n" + "=" * 80)
            print("📄 GENERATED FILES")
            print("=" * 80)
            for file_path in result["files"][:10]:  # Show first 10 files
                print(f"   - {file_path}")
            if result["file_count"] > 10:
                print(f"   ... and {result['file_count'] - 10} more files")

        print("\n" + "=" * 80)
        print("🎉 TEST COMPLETED SUCCESSFULLY!")
        print("=" * 80)

        return result

    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ TEST FAILED")
        print("=" * 80)
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("\n🔍 Pre-flight checks...")

    # Check if RAG services are running
    import requests

    try:
        reader_health = requests.get("http://localhost:9801/health", timeout=2)
        print("✅ RAG Reader is running")
    except:
        print("❌ RAG Reader is NOT running on port 9801")
        print("   Start it: poetry run python src/rag_reader/rag_reader_service.py")
        sys.exit(1)

    try:
        writer_health = requests.get("http://localhost:9802/health", timeout=2)
        print("✅ RAG Writer is running")
    except:
        print("❌ RAG Writer is NOT running on port 9802")
        print("   Start it: poetry run python src/rag_writer/rag_writer_service.py")
        sys.exit(1)

    print("✅ All services ready!\n")

    # Run the test workflow
    result = asyncio.run(run_rag_test_workflow())

    sys.exit(0 if result and result.get("success") else 1)
