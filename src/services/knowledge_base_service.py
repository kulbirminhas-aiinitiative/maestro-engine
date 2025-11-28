#!/usr/bin/env python3
"""
Knowledge Base Service

Provides access to the MAESTRO knowledge base stored in PostgreSQL.
Replaces the hardcoded dag_knowledge_base.py dictionaries with database queries.
"""

import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from utils.postgres_manager import PostgresManager

logger = logging.getLogger(__name__)


@dataclass
class TechnicalComponent:
    """Technical component definition"""
    component_id: str
    name: str
    description: str
    complexity: str
    estimated_duration: str
    typical_phases: List[str]
    tech_options: Dict[str, str]
    dependencies: List[str]


@dataclass
class WorkflowTemplate:
    """Workflow template definition"""
    template_id: str
    name: str
    description: str
    complexity: str
    typical_duration: str
    required_phases: List[str]
    typical_components: List[str]
    parallel_opportunities: List[str]
    use_cases: List[str]


@dataclass
class TechStack:
    """Technology stack definition"""
    stack_id: str
    name: str
    frontend_tech: List[str]
    backend_tech: List[str]
    database_tech: List[str]
    deployment_tech: List[str]
    use_case: str


@dataclass
class AgentPersonaMapping:
    """Agent persona mapping"""
    knowledge_base_role: str
    agent_persona_id: str
    display_name: str
    best_for: List[str]
    skills: List[str]


class KnowledgeBaseService:
    """
    Service for accessing MAESTRO knowledge base from PostgreSQL.

    Provides methods to query technical components, workflow templates,
    tech stacks, agent personas, and best practices.
    """

    def __init__(self, postgres_manager: Optional[PostgresManager] = None):
        """Initialize knowledge base service"""
        self.pg = postgres_manager or PostgresManager()
        logger.info("✅ KnowledgeBaseService initialized")

    async def get_technical_component(self, component_id: str) -> Optional[TechnicalComponent]:
        """
        Get a technical component by ID.

        Args:
            component_id: Component identifier

        Returns:
            TechnicalComponent or None
        """
        row = await self.pg.fetchrow(
            """
            SELECT component_id, name, description, complexity, estimated_duration,
                   typical_phases, tech_options
            FROM technical_components
            WHERE component_id = $1
            """,
            component_id
        )

        if not row:
            return None

        # Get dependencies
        deps = await self.pg.fetch(
            """
            SELECT depends_on_component_id
            FROM component_dependencies
            WHERE component_id = $1
            """,
            component_id
        )

        return TechnicalComponent(
            component_id=row['component_id'],
            name=row['name'],
            description=row['description'],
            complexity=row['complexity'],
            estimated_duration=row['estimated_duration'],
            typical_phases=json.loads(row['typical_phases']),
            tech_options=json.loads(row['tech_options']),
            dependencies=[d['depends_on_component_id'] for d in deps]
        )

    async def get_all_technical_components(self) -> List[TechnicalComponent]:
        """
        Get all technical components.

        Returns:
            List of TechnicalComponent
        """
        rows = await self.pg.fetch(
            """
            SELECT component_id
            FROM technical_components
            ORDER BY name
            """
        )

        components = []
        for row in rows:
            component = await self.get_technical_component(row['component_id'])
            if component:
                components.append(component)

        return components

    async def get_workflow_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """
        Get a workflow template by ID.

        Args:
            template_id: Template identifier

        Returns:
            WorkflowTemplate or None
        """
        row = await self.pg.fetchrow(
            """
            SELECT template_id, name, description, complexity, typical_duration,
                   required_phases, parallel_opportunities, use_cases
            FROM workflow_templates
            WHERE template_id = $1
            """,
            template_id
        )

        if not row:
            return None

        # Get typical components
        components = await self.pg.fetch(
            """
            SELECT component_id
            FROM template_components
            WHERE template_id = $1
            ORDER BY execution_order
            """,
            template_id
        )

        return WorkflowTemplate(
            template_id=row['template_id'],
            name=row['name'],
            description=row['description'],
            complexity=row['complexity'],
            typical_duration=row['typical_duration'],
            required_phases=json.loads(row['required_phases']),
            typical_components=[c['component_id'] for c in components],
            parallel_opportunities=json.loads(row['parallel_opportunities']),
            use_cases=json.loads(row['use_cases'])
        )

    async def get_all_workflow_templates(self) -> List[WorkflowTemplate]:
        """
        Get all workflow templates.

        Returns:
            List of WorkflowTemplate
        """
        rows = await self.pg.fetch(
            """
            SELECT template_id
            FROM workflow_templates
            ORDER BY name
            """
        )

        templates = []
        for row in rows:
            template = await self.get_workflow_template(row['template_id'])
            if template:
                templates.append(template)

        return templates

    async def get_tech_stack(self, stack_id: str) -> Optional[TechStack]:
        """
        Get a tech stack by ID.

        Args:
            stack_id: Stack identifier

        Returns:
            TechStack or None
        """
        row = await self.pg.fetchrow(
            """
            SELECT stack_id, name, frontend_tech, backend_tech, database_tech,
                   deployment_tech, use_case
            FROM tech_stacks
            WHERE stack_id = $1
            """,
            stack_id
        )

        if not row:
            return None

        return TechStack(
            stack_id=row['stack_id'],
            name=row['name'],
            frontend_tech=json.loads(row['frontend_tech']),
            backend_tech=json.loads(row['backend_tech']),
            database_tech=json.loads(row['database_tech']),
            deployment_tech=json.loads(row['deployment_tech']),
            use_case=row['use_case']
        )

    async def get_all_tech_stacks(self) -> List[TechStack]:
        """
        Get all tech stacks.

        Returns:
            List of TechStack
        """
        rows = await self.pg.fetch(
            """
            SELECT stack_id
            FROM tech_stacks
            ORDER BY name
            """
        )

        stacks = []
        for row in rows:
            stack = await self.get_tech_stack(row['stack_id'])
            if stack:
                stacks.append(stack)

        return stacks

    async def get_agent_persona_mapping(self, kb_role: str) -> Optional[AgentPersonaMapping]:
        """
        Get agent persona mapping by knowledge base role.

        Args:
            kb_role: Knowledge base role identifier

        Returns:
            AgentPersonaMapping or None
        """
        row = await self.pg.fetchrow(
            """
            SELECT knowledge_base_role, agent_persona_id, display_name, best_for, skills
            FROM agent_persona_mappings
            WHERE knowledge_base_role = $1
            """,
            kb_role
        )

        if not row:
            return None

        return AgentPersonaMapping(
            knowledge_base_role=row['knowledge_base_role'],
            agent_persona_id=row['agent_persona_id'],
            display_name=row['display_name'],
            best_for=json.loads(row['best_for']),
            skills=json.loads(row['skills'])
        )

    async def get_all_agent_persona_mappings(self) -> List[AgentPersonaMapping]:
        """
        Get all agent persona mappings.

        Returns:
            List of AgentPersonaMapping
        """
        rows = await self.pg.fetch(
            """
            SELECT knowledge_base_role, agent_persona_id, display_name, best_for, skills
            FROM agent_persona_mappings
            ORDER BY display_name
            """
        )

        mappings = []
        for row in rows:
            mappings.append(AgentPersonaMapping(
                knowledge_base_role=row['knowledge_base_role'],
                agent_persona_id=row['agent_persona_id'],
                display_name=row['display_name'],
                best_for=json.loads(row['best_for']),
                skills=json.loads(row['skills'])
            ))

        return mappings

    async def get_best_practices(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get best practices, optionally filtered by category.

        Args:
            category: Category filter (optional)

        Returns:
            List of best practice dictionaries
        """
        if category:
            rows = await self.pg.fetch(
                """
                SELECT category, rule_name, rule_description, rule_data, priority
                FROM best_practices
                WHERE category = $1
                ORDER BY priority, rule_name
                """,
                category
            )
        else:
            rows = await self.pg.fetch(
                """
                SELECT category, rule_name, rule_description, rule_data, priority
                FROM best_practices
                ORDER BY category, priority, rule_name
                """
            )

        practices = []
        for row in rows:
            practices.append({
                'category': row['category'],
                'rule_name': row['rule_name'],
                'description': row['rule_description'],
                'data': json.loads(row['rule_data']),
                'priority': row['priority']
            })

        return practices

    async def get_validation_rules(self, is_active: bool = True) -> List[Dict[str, Any]]:
        """
        Get validation rules.

        Args:
            is_active: Only return active rules (default True)

        Returns:
            List of validation rule dictionaries
        """
        query = """
            SELECT rule_name, rule_description, rule_type, rule_config, severity
            FROM validation_rules
            WHERE is_active = $1
            ORDER BY rule_type, rule_name
        """

        rows = await self.pg.fetch(query, is_active)

        rules = []
        for row in rows:
            rules.append({
                'rule_name': row['rule_name'],
                'description': row['rule_description'],
                'type': row['rule_type'],
                'config': json.loads(row['rule_config']),
                'severity': row['severity']
            })

        return rules

    async def find_templates_by_complexity(self, complexity: str) -> List[WorkflowTemplate]:
        """
        Find workflow templates by complexity level.

        Args:
            complexity: Complexity level (simple, medium, complex, enterprise)

        Returns:
            List of matching templates
        """
        rows = await self.pg.fetch(
            """
            SELECT template_id
            FROM workflow_templates
            WHERE complexity = $1
            ORDER BY name
            """,
            complexity
        )

        templates = []
        for row in rows:
            template = await self.get_workflow_template(row['template_id'])
            if template:
                templates.append(template)

        return templates

    async def find_components_by_complexity(self, complexity: str) -> List[TechnicalComponent]:
        """
        Find technical components by complexity level.

        Args:
            complexity: Complexity level (low, medium, high)

        Returns:
            List of matching components
        """
        rows = await self.pg.fetch(
            """
            SELECT component_id
            FROM technical_components
            WHERE complexity = $1
            ORDER BY name
            """,
            complexity
        )

        components = []
        for row in rows:
            component = await self.get_technical_component(row['component_id'])
            if component:
                components.append(component)

        return components

    async def get_stats(self) -> Dict[str, int]:
        """
        Get knowledge base statistics.

        Returns:
            Dictionary with counts
        """
        stats = {
            'technical_components': await self.pg.fetchval(
                "SELECT COUNT(*) FROM technical_components"
            ),
            'workflow_templates': await self.pg.fetchval(
                "SELECT COUNT(*) FROM workflow_templates"
            ),
            'tech_stacks': await self.pg.fetchval(
                "SELECT COUNT(*) FROM tech_stacks"
            ),
            'agent_persona_mappings': await self.pg.fetchval(
                "SELECT COUNT(*) FROM agent_persona_mappings"
            ),
            'best_practices': await self.pg.fetchval(
                "SELECT COUNT(*) FROM best_practices"
            ),
            'validation_rules': await self.pg.fetchval(
                "SELECT COUNT(*) FROM validation_rules WHERE is_active = TRUE"
            )
        }

        return stats


# Standalone test
async def test_knowledge_base_service():
    """Test knowledge base service"""
    logger.info("=" * 80)
    logger.info("TEST: Knowledge Base Service")
    logger.info("=" * 80)

    kb = KnowledgeBaseService()
    await kb.pg.connect()

    try:
        # Get stats
        logger.info("\n1. Getting knowledge base stats...")
        stats = await kb.get_stats()
        for key, value in stats.items():
            logger.info(f"   {key}: {value}")

        # Get all templates
        logger.info("\n2. Getting all workflow templates...")
        templates = await kb.get_all_workflow_templates()
        logger.info(f"   Found {len(templates)} templates")
        for t in templates[:3]:
            logger.info(f"     - {t.name} ({t.complexity})")

        # Get all components
        logger.info("\n3. Getting all technical components...")
        components = await kb.get_all_technical_components()
        logger.info(f"   Found {len(components)} components")
        for c in components[:3]:
            logger.info(f"     - {c.name} ({c.complexity})")

        # Get persona mappings
        logger.info("\n4. Getting agent persona mappings...")
        personas = await kb.get_all_agent_persona_mappings()
        logger.info(f"   Found {len(personas)} mappings")
        for p in personas[:3]:
            logger.info(f"     - {p.display_name} → {p.agent_persona_id}")

        logger.info("\n✅ All tests passed")

    finally:
        await kb.pg.close()


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_knowledge_base_service())
