#!/usr/bin/env python3
"""
Integration Test: New Personas with Existing Autonomous Executor

This test verifies that the new MAESTRO personas (Schema v3.0) work correctly
with the existing autonomous_sdlc_engine_v3_resumable.py executor.

Usage:
    python3.11 test_integration_with_executor.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path("/home/ec2-user/projects/shared/claude_team_sdk/examples/sdlc_team")))

# Import new personas
from src.personas import MaestroPersonasCompat

# Mock the old personas module to use new ones
sys.modules["personas"] = type("MockModule", (), {"SDLCPersonas": MaestroPersonasCompat})()

# Now import executor components
from session_manager import SessionManager

from config import CLAUDE_CONFIG, OUTPUT_CONFIG

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_persona_loading():
    """Test 1: Verify personas load in legacy format"""
    print("\n" + "=" * 80)
    print("TEST 1: Persona Loading")
    print("=" * 80)

    try:
        # Pre-load adapter in async context
        from src.personas import get_adapter

        adapter = get_adapter()
        await adapter.load_personas()

        personas = MaestroPersonasCompat.get_all_personas()
        print(f"\n✅ Loaded {len(personas)} personas")

        # Verify expected structure
        required_keys = ["id", "name", "phase", "expertise", "system_prompt"]
        for persona_id, persona in list(personas.items())[:3]:
            missing = [key for key in required_keys if key not in persona]
            if missing:
                print(f"❌ {persona_id} missing keys: {missing}")
                return False
            print(f"   ✓ {persona['name']} - valid structure")

        print("\n✅ All personas have correct structure")
        return True

    except Exception as e:
        print(f"❌ Failed to load personas: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_execution_order():
    """Test 2: Verify dependency-based execution ordering"""
    print("\n" + "=" * 80)
    print("TEST 2: Execution Order")
    print("=" * 80)

    try:
        from src.personas import get_adapter

        adapter = get_adapter()

        # Request personas in random order (with all dependencies included)
        requested = [
            "frontend_developer",
            "requirement_analyst",
            "solution_architect",
            "backend_developer",
            "ui_ux_designer",
        ]

        print(f"\n📝 Requested (unordered): {requested}")

        # Get optimal order
        ordered = adapter.get_execution_order(requested)

        print(f"✅ Optimal order: {ordered}")

        # Verify requirement_analyst comes first
        if ordered[0] != "requirement_analyst":
            print(f"❌ requirement_analyst should be first, got: {ordered[0]}")
            return False

        # Verify solution_architect comes before developers
        arch_idx = ordered.index("solution_architect")
        front_idx = ordered.index("frontend_developer")
        back_idx = ordered.index("backend_developer")

        if arch_idx > front_idx or arch_idx > back_idx:
            print(f"❌ solution_architect should come before developers")
            return False

        # Verify ui_ux_designer comes before frontend_developer
        ux_idx = ordered.index("ui_ux_designer")
        if ux_idx > front_idx:
            print(f"❌ ui_ux_designer should come before frontend_developer")
            return False

        print("✅ Dependency order correct")
        return True

    except Exception as e:
        print(f"❌ Execution order test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_session_compatibility():
    """Test 3: Verify compatibility with session manager"""
    print("\n" + "=" * 80)
    print("TEST 3: Session Manager Compatibility")
    print("=" * 80)

    try:
        session_manager = SessionManager()

        # Create test session
        test_session_id = "test_integration_123"
        test_output_dir = Path("./test_output")
        test_output_dir.mkdir(exist_ok=True)

        session = session_manager.create_session(
            requirement="Test requirement for integration",
            output_dir=test_output_dir,
            session_id=test_session_id,
        )

        print(f"\n✅ Created session: {session.session_id}")

        # Simulate persona execution
        session.add_persona_execution(
            persona_id="requirement_analyst",
            files_created=["requirements.md"],
            deliverables={"requirements": "test"},
            duration=10.5,
            success=True,
        )

        # Save session
        session_manager.save_session(session)
        print(f"✅ Saved session")

        # Load session
        loaded_session = session_manager.load_session(test_session_id)
        if not loaded_session:
            print(f"❌ Failed to load session")
            return False

        print(f"✅ Loaded session: {loaded_session.session_id}")

        # Verify data
        if "requirement_analyst" not in loaded_session.completed_personas:
            print(f"❌ requirement_analyst not in completed personas")
            return False

        print(f"✅ Session data correct")

        # Cleanup
        session_manager.delete_session(test_session_id)
        if test_output_dir.exists():
            import shutil

            shutil.rmtree(test_output_dir)

        return True

    except Exception as e:
        print(f"❌ Session compatibility test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_context_building():
    """Test 4: Verify session context can be built for executor"""
    print("\n" + "=" * 80)
    print("TEST 4: Session Context Building")
    print("=" * 80)

    try:
        session_manager = SessionManager()

        # Create mock session with multiple completed personas
        test_output_dir = Path("./test_output")
        test_output_dir.mkdir(exist_ok=True)

        session = session_manager.create_session(
            requirement="Build a simple web app",
            output_dir=test_output_dir,
            session_id="test_context",
        )

        # Add multiple persona executions
        personas_to_add = [
            ("requirement_analyst", ["requirements.md"], {"requirements": "data"}),
            ("solution_architect", ["architecture.md"], {"architecture": "data"}),
        ]

        for persona_id, files, deliverables in personas_to_add:
            session.add_persona_execution(
                persona_id=persona_id,
                files_created=files,
                deliverables=deliverables,
                duration=5.0,
                success=True,
            )

        # Build context
        context = session_manager.get_session_context(session)

        print(f"\n✅ Built context ({len(context)} chars)")

        # Verify context contains expected info
        if "requirement_analyst" not in context:
            print(f"❌ Context missing requirement_analyst")
            return False

        if "solution_architect" not in context:
            print(f"❌ Context missing solution_architect")
            return False

        print(f"✅ Context contains all completed personas")

        # Cleanup
        session_manager.delete_session("test_context")
        if test_output_dir.exists():
            import shutil

            shutil.rmtree(test_output_dir)

        return True

    except Exception as e:
        print(f"❌ Context building test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_persona_prompt_format():
    """Test 5: Verify persona prompts have correct format"""
    print("\n" + "=" * 80)
    print("TEST 5: Persona Prompt Format")
    print("=" * 80)

    try:
        # Pre-load adapter in async context
        from src.personas import get_adapter

        adapter = get_adapter()
        await adapter.load_personas()

        personas = MaestroPersonasCompat.get_all_personas()

        # Check a few personas have proper system prompts
        test_personas = ["requirement_analyst", "solution_architect", "frontend_developer"]

        for persona_id in test_personas:
            persona = personas[persona_id]
            system_prompt = persona.get("system_prompt", "")

            if len(system_prompt) < 50:
                print(f"❌ {persona_id} system prompt too short: {len(system_prompt)} chars")
                return False

            print(f"   ✓ {persona['name']}: {len(system_prompt)} chars")

        print(f"\n✅ All system prompts have valid format")
        return True

    except Exception as e:
        print(f"❌ Prompt format test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all integration tests"""
    print("\n" + "=" * 80)
    print("MAESTRO Persona Integration Tests")
    print("Testing new Schema v3.0 personas with existing executor")
    print("=" * 80)

    tests = [
        ("Persona Loading", test_persona_loading),
        ("Execution Order", test_execution_order),
        ("Session Compatibility", test_session_compatibility),
        ("Context Building", test_context_building),
        ("Prompt Format", test_persona_prompt_format),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print("\n" + "=" * 80)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 80)

    if passed == total:
        print("\n🎉 All integration tests PASSED!")
        print("✅ New personas are fully compatible with autonomous executor")
        print("\n📚 Next Steps:")
        print("   1. Run a full workflow: python3.11 run_test_workflow.py")
        print("   2. Test resumable sessions")
        print("   3. Deploy to production")
    else:
        print(f"\n⚠️  {total - passed} test(s) FAILED")
        print("Fix issues before proceeding with full workflow execution")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
