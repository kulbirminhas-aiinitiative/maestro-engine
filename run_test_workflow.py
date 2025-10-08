#!/usr/bin/env python3
"""
Sample Workflow: Using New MAESTRO Personas with Autonomous Executor

This script demonstrates running a complete SDLC workflow using the new
Schema v3.0 personas with the autonomous executor.

Usage:
    # Run single persona
    python3.11 run_test_workflow.py requirement_analyst

    # Run multiple personas
    python3.11 run_test_workflow.py requirement_analyst solution_architect

    # Resume existing session
    python3.11 run_test_workflow.py --resume simple_app_v1

    # List all sessions
    python3.11 run_test_workflow.py --list-sessions
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path("/home/ec2-user/projects/shared/claude_team_sdk/examples/sdlc_team")))

# Import executor components
from autonomous_sdlc_engine_v3_resumable import AutonomousSDLCEngineV3Resumable, list_sessions
from session_manager import SessionManager

# Shared folder personas.py now references maestro-engine JSON definitions
# No mock needed - it loads from centralized persona system
from personas import SDLCPersonas  # Validates that shared folder personas work

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def run_workflow(
    personas: list[str],
    requirement: str,
    session_id: str = None,
    resume_session_id: str = None,
    output_dir: str = None,
):
    """
    Run SDLC workflow with new personas

    Args:
        personas: List of persona IDs to execute
        requirement: User requirement text
        session_id: Session ID for new session
        resume_session_id: Session ID to resume
        output_dir: Output directory
    """

    print("\n" + "=" * 80)
    print("🚀 MAESTRO SDLC Workflow")
    print("Using Schema v3.0 Personas")
    print("=" * 80)

    # Validate personas
    all_personas = SDLCPersonas.get_all_personas()
    invalid = [p for p in personas if p not in all_personas]
    if invalid:
        print(f"❌ Invalid personas: {invalid}")
        print(f"✅ Available: {', '.join(all_personas.keys())}")
        return

    print(f"\n📋 Requirement: {requirement if requirement else '[Resume session]'}")
    print(f"👥 Personas: {', '.join(personas)}")

    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = Path("./generated_maestro_test")

    print(f"📁 Output: {output_path}")

    # Create engine
    session_manager = SessionManager()
    engine = AutonomousSDLCEngineV3Resumable(
        selected_personas=personas, output_dir=str(output_path), session_manager=session_manager
    )

    try:
        # Execute workflow
        result = await engine.execute(
            requirement=requirement or "",
            session_id=session_id,
            resume_session_id=resume_session_id,
        )

        # Display results
        print("\n" + "=" * 80)
        print("📊 WORKFLOW RESULTS")
        print("=" * 80)
        print(f"✅ Success: {result['success']}")
        print(f"🆔 Session: {result['session_id']}")
        print(f"👥 Executed: {len(result.get('executed_personas', []))} personas")
        print(f"📁 Files: {result['file_count']}")
        print(f"⏱️  Duration: {result['total_duration']:.2f}s")
        print(f"📂 Output: {result['project_dir']}")

        if result.get("resumable"):
            print(f"\n💡 Resume command:")
            print(f"   python3.11 run_test_workflow.py --resume {result['session_id']}")

        print("=" * 80)

    except Exception as e:
        logger.exception("❌ Workflow failed")
        print(f"\n❌ Error: {e}")
        raise


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run MAESTRO SDLC workflow with new personas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("personas", nargs="*", help="Personas to execute")
    parser.add_argument("--requirement", help="Project requirement (for new sessions)")
    parser.add_argument("--session-id", help="Session ID for new session")
    parser.add_argument("--resume", help="Resume existing session by ID")
    parser.add_argument("--list-sessions", action="store_true", help="List all sessions")
    parser.add_argument("--output-dir", help="Output directory")

    # Sample requirements
    parser.add_argument(
        "--example", choices=["simple", "webapp", "api"], help="Use example requirement"
    )

    args = parser.parse_args()

    # List sessions
    if args.list_sessions:
        session_manager = SessionManager()
        list_sessions(session_manager)
        return

    # Example requirements
    examples = {
        "simple": "Create a simple TODO list application with basic CRUD operations",
        "webapp": "Build a blog platform with user authentication and markdown support",
        "api": "Design a REST API for a bookstore with inventory management",
    }

    # Determine requirement
    requirement = args.requirement
    if args.example:
        requirement = examples[args.example]
        print(f"📝 Using example: {args.example}")

    # Resume session
    if args.resume:
        if not args.personas:
            # Resume with remaining personas
            session_manager = SessionManager()
            session = session_manager.load_session(args.resume)

            if not session:
                print(f"❌ Session not found: {args.resume}")
                return

            all_available = list(SDLCPersonas.get_all_personas().keys())
            remaining = [p for p in all_available if p not in session.completed_personas]

            if not remaining:
                print(f"✅ All personas already completed in session {args.resume}")
                return

            print(f"🔄 Resuming with {len(remaining)} remaining personas")
            args.personas = remaining

        await run_workflow(
            personas=args.personas,
            requirement="",  # Will be loaded from session
            resume_session_id=args.resume,
            output_dir=args.output_dir,
        )

    # New session
    else:
        if not args.personas:
            print("❌ Error: Specify personas to execute")
            print("\nExample usage:")
            print("  python3.11 run_test_workflow.py requirement_analyst --example simple")
            print(
                "  python3.11 run_test_workflow.py requirement_analyst solution_architect --example webapp"
            )
            parser.print_help()
            return

        if not requirement:
            print("❌ Error: --requirement or --example required for new sessions")
            parser.print_help()
            return

        await run_workflow(
            personas=args.personas,
            requirement=requirement,
            session_id=args.session_id,
            output_dir=args.output_dir,
        )


if __name__ == "__main__":
    print(
        """
╔══════════════════════════════════════════════════════════════════════════════╗
║                     MAESTRO SDLC Workflow Runner                             ║
║                        Schema v3.0 Personas                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    )

    asyncio.run(main())
