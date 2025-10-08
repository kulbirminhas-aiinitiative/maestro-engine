#!/usr/bin/env python3
"""
Example: Using MAESTRO Persona System with Autonomous Executor

This script demonstrates how to use the new JSON-based persona system
with the existing autonomous_sdlc_engine_v3_resumable.py executor.

Usage:
    python3.11 example_persona_usage.py
"""

import asyncio
import sys
from pathlib import Path

# Add maestro-engine to path
sys.path.insert(0, str(Path(__file__).parent))

from src.personas import MaestroPersonaAdapter, PersonaCategory, PersonaRegistry, get_adapter


async def example_1_load_all_personas():
    """Example 1: Load all personas and display information"""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Load All Personas")
    print("=" * 80)

    adapter = MaestroPersonaAdapter()
    await adapter.load_personas()

    personas = adapter.get_all_personas()

    print(f"\n✅ Loaded {len(personas)} personas in legacy format\n")

    for persona_id, persona in personas.items():
        print(f"🤖 {persona['name']}")
        print(f"   ID: {persona['id']}")
        print(f"   Phase: {persona['phase']}")
        print(f"   Role: {persona['role_id']}")
        print(f"   Expertise Areas: {len(persona['expertise'])}")
        print()


async def example_2_get_execution_order():
    """Example 2: Get optimal execution order based on dependencies"""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Dependency-Based Execution Order")
    print("=" * 80)

    adapter = MaestroPersonaAdapter()
    await adapter.load_personas()

    # User selects personas in random order
    selected = [
        "frontend_developer",
        "qa_engineer",
        "backend_developer",
        "ui_ux_designer",
        "requirement_analyst",
        "solution_architect",
    ]

    print(f"\n📝 User selected (unordered): {', '.join(selected)}\n")

    # Adapter determines correct execution order
    ordered = adapter.get_execution_order(selected)

    print(f"✅ Optimal execution order:\n")
    for i, persona_id in enumerate(ordered, 1):
        persona = adapter.get_persona(persona_id)
        print(f"   {i}. {persona['name']} ({persona_id})")

    print(f"\n💡 Order based on dependency graph from persona definitions")


async def example_3_category_based_selection():
    """Example 3: Select personas by category"""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Category-Based Persona Selection")
    print("=" * 80)

    registry = PersonaRegistry()
    await registry.load_all()

    categories = [
        PersonaCategory.ANALYSIS_DESIGN,
        PersonaCategory.DEVELOPMENT,
        PersonaCategory.OPERATIONS,
        PersonaCategory.QUALITY_SECURITY,
        PersonaCategory.DOCUMENTATION,
    ]

    for category in categories:
        personas = registry.get_by_category(category)
        print(f"\n📂 {category.value.upper()} ({len(personas)} personas):")
        for persona in personas:
            print(f"   - {persona.display_name} (priority: {persona.execution.priority})")


async def example_4_prepare_for_executor():
    """Example 4: Prepare personas for autonomous executor"""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Prepare for Autonomous Executor")
    print("=" * 80)

    adapter = MaestroPersonaAdapter()
    await adapter.load_personas()

    # Simulate user requirement
    requirement = "Build a task management application with user authentication"

    # Select personas for this requirement
    selected_personas = [
        "requirement_analyst",
        "solution_architect",
        "ui_ux_designer",
        "frontend_developer",
        "backend_developer",
        "qa_engineer",
    ]

    print(f"\n📋 Requirement: {requirement}")
    print(f"\n👥 Selected Personas: {len(selected_personas)}")

    # Get execution order
    execution_order = adapter.get_execution_order(selected_personas)

    print(f"\n✅ Execution Plan:\n")
    for i, persona_id in enumerate(execution_order, 1):
        legacy_persona = adapter.get_persona(persona_id)
        print(f"   {i}. {legacy_persona['name']}")
        print(f"      Phase: {legacy_persona['phase']}")
        print(f"      Collaboration: {legacy_persona['collaboration_style']}")
        print()

    # Show how this integrates with executor
    print("💡 Integration with Autonomous Executor:\n")
    print("   from maestro_engine.personas import get_adapter")
    print("   from autonomous_sdlc_engine_v3_resumable import AutonomousSDLCEngineV3Resumable")
    print()
    print("   adapter = get_adapter()")
    print("   engine = AutonomousSDLCEngineV3Resumable(")
    print(f"       selected_personas={execution_order},")
    print("       output_dir='./generated_project'")
    print("   )")
    print("   result = await engine.execute(")
    print(f"       requirement='{requirement}',")
    print("       session_id='task_mgmt_v1'")
    print("   )")


async def example_5_persona_details():
    """Example 5: Inspect detailed persona configuration"""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Detailed Persona Configuration")
    print("=" * 80)

    registry = PersonaRegistry()
    await registry.load_all()

    persona_id = "requirement_analyst"
    persona = registry.get(persona_id)

    print(f"\n🔍 Inspecting: {persona.display_name}\n")
    print(f"Version: {persona.version} (Schema: {persona.schema_version})")
    print(f"Category: {persona.metadata.category}")
    print(f"Status: {persona.metadata.status}")
    print(f"Author: {persona.metadata.author}")
    print(f"Created: {persona.metadata.created_at}")
    print()

    print("🎯 Role:")
    print(f"  Primary: {persona.role.primary_role}")
    print(f"  Experience: {persona.role.experience_level}/10")
    print(f"  Autonomy: {persona.role.autonomy_level}/10")
    print(f"  Specializations: {', '.join(persona.role.specializations[:3])}")
    print()

    print("⚙️ Execution:")
    print(f"  Priority: {persona.execution.priority}")
    print(f"  Timeout: {persona.execution.timeout_seconds}s")
    print(f"  Max Retries: {persona.execution.max_retries}")
    print(f"  Parallel Capable: {persona.execution.parallel_capable}")
    print()

    print("🔗 Dependencies:")
    print(f"  Depends on: {', '.join(persona.dependencies.depends_on) or 'None'}")
    print(f"  Required by: {', '.join(persona.dependencies.required_by[:3]) or 'None'}")
    print()

    print("📦 Capabilities:")
    for cap in persona.capabilities.core[:5]:
        print(f"  - {cap}")
    print()

    if persona.intelligence and persona.intelligence.domains:
        print("🧠 Intelligence (Domain-Specific):")
        for domain_name, domain_info in list(persona.intelligence.domains.items())[:2]:
            print(f"  {domain_name}:")
            print(f"    Platforms: {', '.join(domain_info.platforms[:3])}")
            print(f"    Complexity Weight: {domain_info.complexity_weight}")


async def main():
    """Run all examples"""
    print("\n" + "=" * 80)
    print("MAESTRO Persona System - Usage Examples")
    print("=" * 80)

    await example_1_load_all_personas()
    await example_2_get_execution_order()
    await example_3_category_based_selection()
    await example_4_prepare_for_executor()
    await example_5_persona_details()

    print("\n" + "=" * 80)
    print("✅ All Examples Completed Successfully!")
    print("=" * 80)
    print()
    print("📚 Next Steps:")
    print("   1. Review PERSONA_INTEGRATION_GUIDE.md for integration details")
    print("   2. Test with autonomous_sdlc_engine_v3_resumable.py")
    print("   3. Customize personas in src/personas/definitions/")
    print()


if __name__ == "__main__":
    asyncio.run(main())
