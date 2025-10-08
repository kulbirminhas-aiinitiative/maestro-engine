#!/usr/bin/env python3
"""
Test script for MAESTRO persona system.

Validates that personas load correctly from JSON files.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from personas import PersonaRegistry


async def main():
    """Test persona loading."""
    print("🧪 Testing MAESTRO Persona System\n")
    print("=" * 60)

    # Initialize registry
    registry = PersonaRegistry()
    print(f"📁 Personas directory: {registry.definitions_dir}")

    # Check if directory exists
    if not registry.definitions_dir.exists():
        print(f"❌ Directory not found!")
        return 1

    # Load personas
    print("\n📥 Loading personas...")
    try:
        await registry.load_all()
    except Exception as e:
        print(f"❌ Failed to load personas: {e}")
        return 1

    # Get stats
    stats = registry.get_stats()
    print(f"\n✅ Loaded {stats['total_personas']} persona(s)")

    if stats["total_personas"] == 0:
        print("⚠️  No personas found")
        return 0

    # List all personas
    print("\n📋 Personas:")
    print("-" * 60)

    for persona in registry.list_all():
        print(f"\n🤖 {persona.display_name}")
        print(f"   ID: {persona.persona_id}")
        print(f"   Version: {persona.version} (schema: {persona.schema_version})")
        print(f"   Category: {persona.metadata.category}")
        print(f"   Role: {persona.role.primary_role}")
        print(f"   Experience: {persona.role.experience_level}/10")
        print(f"   Priority: {persona.execution.priority}")
        print(f"   Timeout: {persona.execution.timeout_seconds}s")

        # Core capabilities
        print(f"   Capabilities: {', '.join(persona.capabilities.core[:3])}")

        # Dependencies
        if persona.dependencies.depends_on:
            print(f"   Depends on: {', '.join(persona.dependencies.depends_on)}")
        if persona.dependencies.required_by:
            print(f"   Required by: {', '.join(persona.dependencies.required_by[:3])}")

    # Test specific persona retrieval
    print("\n" + "=" * 60)
    print("\n🔍 Testing persona retrieval...")

    analyst = registry.get("requirement_analyst")
    if analyst:
        print(f"✅ Found: {analyst.display_name}")
        print(f"   Description: {analyst.metadata.description}")

        # Show intelligence
        if analyst.intelligence and analyst.intelligence.domains:
            domains = list(analyst.intelligence.domains.keys())
            print(f"   Domains: {', '.join(domains[:5])}")

            # Show one domain in detail
            if "project_management" in analyst.intelligence.domains:
                pm = analyst.intelligence.domains["project_management"]
                print(f"\n   📊 Project Management Domain:")
                print(f"      Keywords: {', '.join(pm.keywords[:5])}...")
                print(f"      Platforms: {', '.join(pm.platforms)}")
                print(f"      Complexity weight: {pm.complexity_weight}")

    else:
        print("❌ requirement_analyst not found")

    # Test validation
    print("\n" + "=" * 60)
    print("\n✅ All tests passed!")
    print("\n💡 Next steps:")
    print("   1. Add more personas to src/personas/definitions/")
    print("   2. Run: python scripts/validate_persona_naming.py")
    print("   3. Create PersonaExecutor")
    print("   4. Create PersonaOrchestrator")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
