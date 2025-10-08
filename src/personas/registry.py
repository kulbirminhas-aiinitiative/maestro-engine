"""
MAESTRO Persona Registry

Loads and manages all persona definitions from JSON files.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .models import PersonaCategory, PersonaDefinition

logger = logging.getLogger(__name__)


class PersonaRegistry:
    """
    Central registry for all MAESTRO personas.

    Loads persona definitions from JSON files and provides
    access methods for retrieving personas by ID, category, etc.
    """

    def __init__(self, definitions_dir: Optional[Path] = None):
        """
        Initialize persona registry.

        Args:
            definitions_dir: Path to persona JSON files
                           (default: src/personas/definitions/)
        """
        if definitions_dir is None:
            # Default to definitions/ directory next to this file
            definitions_dir = Path(__file__).parent / "definitions"

        self.definitions_dir = Path(definitions_dir)
        self.personas: Dict[str, PersonaDefinition] = {}
        self._loaded = False

    async def load_all(self) -> None:
        """Load all persona definitions from JSON files."""
        if self._loaded:
            logger.debug("Personas already loaded, skipping")
            return

        if not self.definitions_dir.exists():
            raise FileNotFoundError(f"Personas directory not found: {self.definitions_dir}")

        logger.info(f"Loading personas from {self.definitions_dir}")

        json_files = list(self.definitions_dir.glob("*.json"))

        if not json_files:
            logger.warning(f"No persona JSON files found in {self.definitions_dir}")
            return

        loaded_count = 0
        error_count = 0

        for json_file in json_files:
            try:
                persona = await self.load_persona(json_file)
                self.personas[persona.persona_id] = persona
                loaded_count += 1
                logger.debug(f"Loaded persona: {persona.persona_id}")
            except Exception as e:
                error_count += 1
                logger.error(f"Failed to load {json_file.name}: {e}")

        self._loaded = True

        logger.info(
            f"Loaded {loaded_count} personas " f"({error_count} errors) from {self.definitions_dir}"
        )

    async def load_persona(self, file_path: Path) -> PersonaDefinition:
        """
        Load and validate a single persona definition.

        Args:
            file_path: Path to persona JSON file

        Returns:
            PersonaDefinition instance

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If JSON is invalid
            ValidationError: If persona doesn't match schema
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Persona file not found: {file_path}")

        with open(file_path) as f:
            data = json.load(f)

        # Validate against Pydantic model
        persona = PersonaDefinition(**data)

        # Verify persona_id matches filename
        expected_id = file_path.stem
        if persona.persona_id != expected_id:
            raise ValueError(
                f"persona_id '{persona.persona_id}' must match " f"filename '{expected_id}'"
            )

        return persona

    def get(self, persona_id: str) -> Optional[PersonaDefinition]:
        """
        Get persona by ID.

        Args:
            persona_id: Persona identifier

        Returns:
            PersonaDefinition or None if not found
        """
        if not self._loaded:
            raise RuntimeError("Registry not loaded. Call await registry.load_all() first")

        return self.personas.get(persona_id)

    def get_by_category(self, category: PersonaCategory) -> List[PersonaDefinition]:
        """
        Get all personas in a category.

        Args:
            category: PersonaCategory enum value

        Returns:
            List of personas in the category
        """
        if not self._loaded:
            raise RuntimeError("Registry not loaded. Call await registry.load_all() first")

        return [
            persona for persona in self.personas.values() if persona.metadata.category == category
        ]

    def get_by_priority(self, ascending: bool = True) -> List[PersonaDefinition]:
        """
        Get all personas sorted by execution priority.

        Args:
            ascending: If True, sort 1→10 (high→low priority)
                      If False, sort 10→1 (low→high priority)

        Returns:
            List of personas sorted by priority
        """
        if not self._loaded:
            raise RuntimeError("Registry not loaded. Call await registry.load_all() first")

        return sorted(
            self.personas.values(), key=lambda p: p.execution.priority, reverse=not ascending
        )

    def list_all(self) -> List[PersonaDefinition]:
        """
        Get all loaded personas.

        Returns:
            List of all personas
        """
        if not self._loaded:
            raise RuntimeError("Registry not loaded. Call await registry.load_all() first")

        return list(self.personas.values())

    def get_dependencies(self, persona_id: str) -> List[str]:
        """
        Get persona dependencies (personas that must run before this one).

        Args:
            persona_id: Persona identifier

        Returns:
            List of persona IDs that this persona depends on
        """
        persona = self.get(persona_id)
        if not persona:
            raise ValueError(f"Persona not found: {persona_id}")

        return persona.dependencies.depends_on

    def get_dependents(self, persona_id: str) -> List[str]:
        """
        Get personas that depend on this persona.

        Args:
            persona_id: Persona identifier

        Returns:
            List of persona IDs that depend on this persona
        """
        persona = self.get(persona_id)
        if not persona:
            raise ValueError(f"Persona not found: {persona_id}")

        return persona.dependencies.required_by

    def validate_persona_selection(self, persona_ids: List[str]) -> bool:
        """
        Validate that all dependencies are satisfied for selected personas.

        Args:
            persona_ids: List of persona IDs to execute

        Returns:
            True if all dependencies satisfied

        Raises:
            ValueError: If dependencies are missing
        """
        selected_set = set(persona_ids)

        for persona_id in persona_ids:
            deps = self.get_dependencies(persona_id)
            missing_deps = set(deps) - selected_set

            if missing_deps:
                raise ValueError(
                    f"Persona '{persona_id}' has missing dependencies: "
                    f"{', '.join(missing_deps)}"
                )

        return True

    def get_execution_order(self, persona_ids: List[str]) -> List[str]:
        """
        Get correct execution order based on dependencies.

        Args:
            persona_ids: List of persona IDs to execute

        Returns:
            List of persona IDs in dependency order

        Raises:
            ValueError: If circular dependencies detected
        """
        # Validate first
        self.validate_persona_selection(persona_ids)

        # Simple topological sort
        ordered = []
        remaining = set(persona_ids)

        while remaining:
            # Find personas with no unmet dependencies
            ready = [
                p_id
                for p_id in remaining
                if all(
                    dep in ordered or dep not in persona_ids for dep in self.get_dependencies(p_id)
                )
            ]

            if not ready:
                raise ValueError(f"Circular dependency detected among: {remaining}")

            # Add ready personas in priority order
            ready_personas = [self.get(p_id) for p_id in ready]
            ready_sorted = sorted(ready_personas, key=lambda p: p.execution.priority)

            for persona in ready_sorted:
                ordered.append(persona.persona_id)
                remaining.remove(persona.persona_id)

        return ordered

    def get_stats(self) -> Dict:
        """
        Get registry statistics.

        Returns:
            Dictionary with stats
        """
        if not self._loaded:
            return {"loaded": False, "total_personas": 0}

        category_counts = {}
        for persona in self.personas.values():
            category = persona.metadata.category
            category_counts[category] = category_counts.get(category, 0) + 1

        return {
            "loaded": True,
            "total_personas": len(self.personas),
            "by_category": category_counts,
            "persona_ids": sorted(self.personas.keys()),
        }

    def __repr__(self) -> str:
        """String representation."""
        if not self._loaded:
            return f"<PersonaRegistry (not loaded)>"

        return (
            f"<PersonaRegistry "
            f"({len(self.personas)} personas loaded from {self.definitions_dir})>"
        )


# Global registry instance
_registry: Optional[PersonaRegistry] = None


async def get_registry() -> PersonaRegistry:
    """
    Get global persona registry instance.

    Loads personas on first call.

    Returns:
        PersonaRegistry instance
    """
    global _registry

    if _registry is None:
        _registry = PersonaRegistry()
        await _registry.load_all()

    return _registry
