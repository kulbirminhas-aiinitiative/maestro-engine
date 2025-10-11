"""
Persona Adapter - Bridges new JSON-based personas with legacy executor

This adapter converts our clean Pydantic persona models into the dictionary
format expected by autonomous_sdlc_engine_v3_resumable.py, ensuring backward
compatibility while using the new persona system.

Usage:
    from maestro_engine.personas.adapter import MaestroPersonaAdapter

    adapter = MaestroPersonaAdapter()
    legacy_personas = adapter.get_all_personas()  # Compatible with old executor
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

# Add maestro-engine to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import directly from submodules to avoid circular import
from .models import PersonaCategory, PersonaDefinition
from .registry import PersonaRegistry


class MaestroPersonaAdapter:
    """
    Adapter that converts new Pydantic persona models to legacy dictionary format
    """

    def __init__(self, definitions_dir: Path = None):
        """
        Initialize adapter with persona registry

        Args:
            definitions_dir: Path to persona JSON definitions (optional)
        """
        self.registry = PersonaRegistry(definitions_dir)
        self._loaded = False

    async def load_personas(self):
        """Load all persona definitions from JSON files"""
        if not self._loaded:
            await self.registry.load_all()
            self._loaded = True

    def _convert_persona_to_legacy(self, persona: PersonaDefinition) -> Dict[str, Any]:
        """
        Convert new Pydantic PersonaDefinition to legacy dictionary format

        Args:
            persona: PersonaDefinition model

        Returns:
            Dictionary in legacy format compatible with autonomous_sdlc_engine_v3_resumable.py
        """
        # Map new categories to legacy phase names
        category_to_phase = {
            PersonaCategory.ANALYSIS_DESIGN: (
                "requirements" if persona.persona_id == "requirement_analyst" else "design"
            ),
            PersonaCategory.DEVELOPMENT: "implementation",
            PersonaCategory.OPERATIONS: "deployment",
            PersonaCategory.QUALITY_SECURITY: (
                "testing" if persona.persona_id == "qa_engineer" else "security"
            ),
            PersonaCategory.DOCUMENTATION: "documentation",
        }

        # Map new categories to legacy role_id
        category_to_role = {
            PersonaCategory.ANALYSIS_DESIGN: (
                "analyst" if persona.persona_id == "requirement_analyst" else "architect"
            ),
            PersonaCategory.DEVELOPMENT: "developer",
            PersonaCategory.OPERATIONS: (
                "devops" if persona.persona_id == "devops_engineer" else "deployment"
            ),
            PersonaCategory.QUALITY_SECURITY: (
                "tester" if persona.persona_id == "qa_engineer" else "security"
            ),
            PersonaCategory.DOCUMENTATION: "writer",
        }

        # Build expertise list from capabilities and specializations
        expertise = (
            persona.capabilities.core[:8]  # Limit to 8 items like legacy
            + persona.role.specializations[:3]
        )

        # Build responsibilities from capabilities (simplified mapping)
        responsibilities = [
            f"Deliver {cap.replace('_', ' ')}" for cap in persona.capabilities.core[:8]
        ]

        # Legacy format
        legacy_persona = {
            "id": persona.persona_id,
            "name": persona.display_name,
            "role_id": category_to_role.get(persona.metadata.category, "other"),
            "phase": category_to_phase.get(persona.metadata.category, "implementation"),
            "expertise": expertise,
            "responsibilities": responsibilities,
            "tools_allowed": [
                "post_message",
                "get_messages",
                "share_knowledge",
                "get_knowledge",
                "create_task",
                "claim_task",
                "complete_task",
                "fail_task",
                "propose_decision",
                "vote_decision",
                "store_artifact",
                "get_artifacts",
                "update_status",
            ],
            "system_prompt": persona.prompts.system_prompt,
            "key_metrics": [
                f"{metric}: {threshold}"
                for metric, threshold in (
                    persona.quality_metrics.expected_output_quality
                    if persona.quality_metrics
                    else {}
                ).items()
            ]
            or ["quality", "completeness", "accuracy"],
            "collaboration_style": self._infer_collaboration_style(persona),
        }

        return legacy_persona

    def _infer_collaboration_style(self, persona: PersonaDefinition) -> str:
        """Infer collaboration style from persona attributes"""
        styles = {
            "requirement_analyst": "Facilitator - bridges business and technical teams",
            "solution_architect": "Strategic - sets technical direction",
            "ui_ux_designer": "Creator - designs user experience",
            "frontend_developer": "Implementer - builds what's designed",
            "backend_developer": "Implementer - builds core business logic",
            "database_administrator": "Specialist - manages data integrity",
            "devops_engineer": "Enabler - makes deployment smooth and reliable",
            "deployment_specialist": "Orchestrator - coordinates release process",
            "qa_engineer": "Quality guardian - ensures standards are met",
            "security_specialist": "Guardian - protects system from threats",
            "technical_writer": "Documenter - makes knowledge accessible",
        }
        return styles.get(persona.persona_id, "Contributor")

    def get_all_personas(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all personas in legacy dictionary format

        This method signature matches SDLCPersonas.get_all_personas() from
        the shared/claude_team_sdk/examples/sdlc_team/personas.py file.

        Returns:
            Dictionary mapping persona_id to legacy persona dict
        """
        if not self._loaded:
            raise RuntimeError("Personas not loaded. Call await adapter.ensure_loaded() first.")

        legacy_personas = {}
        for persona_id, persona in self.registry.personas.items():
            legacy_personas[persona_id] = self._convert_persona_to_legacy(persona)

        return legacy_personas

    async def ensure_loaded(self):
        """Ensure personas are loaded (async-safe)"""
        if not self._loaded:
            await self.load_personas()

    def get_persona(self, persona_id: str) -> Dict[str, Any]:
        """
        Get a single persona in legacy format

        Args:
            persona_id: Persona identifier

        Returns:
            Legacy persona dictionary or None
        """
        if not self._loaded:
            raise RuntimeError("Personas not loaded. Call await adapter.ensure_loaded() first.")

        persona = self.registry.get(persona_id)
        if persona:
            return self._convert_persona_to_legacy(persona)
        return None

    def get_execution_order(self, persona_ids: List[str]) -> List[str]:
        """
        Get optimal execution order for given personas

        Uses dependency resolution from registry, but can fall back
        to priority-based ordering for compatibility.

        Args:
            persona_ids: List of persona IDs to execute

        Returns:
            Ordered list of persona IDs
        """
        if not self._loaded:
            import asyncio

            asyncio.run(self.load_personas())

        # Use registry's topological sort
        return self.registry.get_execution_order(persona_ids)


# Singleton instance for backward compatibility
_adapter_instance = None


def get_adapter() -> MaestroPersonaAdapter:
    """Get singleton adapter instance"""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = MaestroPersonaAdapter()
    return _adapter_instance


# Compatibility class that mimics SDLCPersonas from legacy system
class MaestroPersonasCompat:
    """
    Drop-in replacement for SDLCPersonas from legacy system

    Usage in autonomous_sdlc_engine_v3_resumable.py:
        # Old: from personas import SDLCPersonas
        # New: from maestro_engine.personas.adapter import MaestroPersonasCompat as SDLCPersonas
    """

    @staticmethod
    def get_all_personas() -> Dict[str, Dict[str, Any]]:
        """Get all personas in legacy format"""
        adapter = get_adapter()
        return adapter.get_all_personas()


if __name__ == "__main__":
    """Test the adapter"""
    import asyncio

    async def test_adapter():
        print("🧪 Testing Persona Adapter\n")
        print("=" * 80)

        adapter = MaestroPersonaAdapter()
        await adapter.load_personas()

        legacy_personas = adapter.get_all_personas()

        print(f"✅ Loaded {len(legacy_personas)} personas in legacy format\n")

        # Test a few personas
        for persona_id in ["requirement_analyst", "solution_architect", "frontend_developer"]:
            persona = legacy_personas.get(persona_id)
            if persona:
                print(f"\n🤖 {persona['name']} ({persona_id})")
                print(f"   Phase: {persona['phase']}")
                print(f"   Role ID: {persona['role_id']}")
                print(f"   Expertise: {len(persona['expertise'])} areas")
                print(f"   System Prompt: {len(persona['system_prompt'])} chars")
                print(f"   Collaboration: {persona['collaboration_style']}")

        print("\n" + "=" * 80)
        print("✅ Adapter test completed successfully!")

    asyncio.run(test_adapter())
