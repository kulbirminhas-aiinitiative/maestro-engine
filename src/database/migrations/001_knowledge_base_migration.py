#!/usr/bin/env python3
"""
Knowledge Base Migration Script

Migrates data from dag_knowledge_base.py to PostgreSQL database.
"""

import sys
import json
import logging
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from knowledge.dag_knowledge_base import (
    TECHNICAL_COMPONENTS,
    WORKFLOW_TEMPLATES,
    TECH_STACK_COMBINATIONS,
    AGENT_PERSONAS,
    BEST_PRACTICES,
    VALIDATION_RULES
)
from utils.postgres_manager import PostgresManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeBaseMigration:
    """Migrate knowledge base data to PostgreSQL"""

    def __init__(self, postgres_manager: PostgresManager):
        self.pg = postgres_manager

    async def run_migration(self):
        """Execute complete migration"""
        logger.info("=" * 80)
        logger.info("KNOWLEDGE BASE MIGRATION")
        logger.info("=" * 80)

        try:
            # Step 1: Create schema
            logger.info("\n📋 Step 1: Creating database schema...")
            await self.create_schema()

            # Step 2: Migrate technical components
            logger.info("\n🔧 Step 2: Migrating technical components...")
            await self.migrate_technical_components()

            # Step 3: Migrate component dependencies
            logger.info("\n🔗 Step 3: Migrating component dependencies...")
            await self.migrate_component_dependencies()

            # Step 4: Migrate workflow templates
            logger.info("\n📝 Step 4: Migrating workflow templates...")
            await self.migrate_workflow_templates()

            # Step 5: Migrate template components
            logger.info("\n🗂️  Step 5: Migrating template-component mappings...")
            await self.migrate_template_components()

            # Step 6: Migrate tech stacks
            logger.info("\n💻 Step 6: Migrating tech stacks...")
            await self.migrate_tech_stacks()

            # Step 7: Migrate agent persona mappings
            logger.info("\n🤖 Step 7: Migrating agent persona mappings...")
            await self.migrate_agent_personas()

            # Step 8: Migrate best practices
            logger.info("\n✨ Step 8: Migrating best practices...")
            await self.migrate_best_practices()

            # Step 9: Migrate validation rules
            logger.info("\n✅ Step 9: Migrating validation rules...")
            await self.migrate_validation_rules()

            # Step 10: Verify migration
            logger.info("\n🔍 Step 10: Verifying migration...")
            await self.verify_migration()

            logger.info("\n" + "=" * 80)
            logger.info("✅ MIGRATION COMPLETE")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}", exc_info=True)
            raise

    async def create_schema(self):
        """Create database schema"""
        schema_file = Path(__file__).parent.parent / "schemas" / "knowledge_base_schema.sql"

        if not schema_file.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_file}")

        with open(schema_file) as f:
            schema_sql = f.read()

        await self.pg.execute(schema_sql)
        logger.info(f"✅ Schema created from {schema_file.name}")

    async def migrate_technical_components(self):
        """Migrate technical components"""
        count = 0

        for component_id, data in TECHNICAL_COMPONENTS.items():
            await self.pg.execute(
                """
                INSERT INTO technical_components
                (component_id, name, description, complexity, estimated_duration, typical_phases, tech_options)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (component_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    complexity = EXCLUDED.complexity,
                    estimated_duration = EXCLUDED.estimated_duration,
                    typical_phases = EXCLUDED.typical_phases,
                    tech_options = EXCLUDED.tech_options
                """,
                component_id,
                data['name'],
                data['description'],
                data['complexity'],
                data['estimated_duration'],
                json.dumps(data['typical_phases']),
                json.dumps(data['tech_options'])
            )
            count += 1

        logger.info(f"✅ Migrated {count} technical components")

    async def migrate_component_dependencies(self):
        """Migrate component dependencies"""
        count = 0

        for component_id, data in TECHNICAL_COMPONENTS.items():
            for dep_id in data.get('dependencies', []):
                if dep_id in TECHNICAL_COMPONENTS:
                    await self.pg.execute(
                        """
                        INSERT INTO component_dependencies
                        (component_id, depends_on_component_id, dependency_type)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (component_id, depends_on_component_id) DO NOTHING
                        """,
                        component_id,
                        dep_id,
                        'requires'
                    )
                    count += 1

        logger.info(f"✅ Migrated {count} component dependencies")

    async def migrate_workflow_templates(self):
        """Migrate workflow templates"""
        count = 0

        for template_id, data in WORKFLOW_TEMPLATES.items():
            await self.pg.execute(
                """
                INSERT INTO workflow_templates
                (template_id, name, description, complexity, typical_duration, required_phases, parallel_opportunities, use_cases)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (template_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    complexity = EXCLUDED.complexity,
                    typical_duration = EXCLUDED.typical_duration,
                    required_phases = EXCLUDED.required_phases,
                    parallel_opportunities = EXCLUDED.parallel_opportunities,
                    use_cases = EXCLUDED.use_cases
                """,
                template_id,
                data['name'],
                data['description'],
                data['complexity'],
                data['typical_duration'],
                json.dumps(data['required_phases']),
                json.dumps(data.get('parallel_opportunities', [])),
                json.dumps(data.get('use_cases', []))
            )
            count += 1

        logger.info(f"✅ Migrated {count} workflow templates")

    async def migrate_template_components(self):
        """Migrate template-component mappings"""
        count = 0

        for template_id, data in WORKFLOW_TEMPLATES.items():
            for order, component_id in enumerate(data.get('typical_components', []), 1):
                if component_id in TECHNICAL_COMPONENTS:
                    await self.pg.execute(
                        """
                        INSERT INTO template_components
                        (template_id, component_id, is_required, execution_order)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (template_id, component_id) DO UPDATE SET
                            execution_order = EXCLUDED.execution_order
                        """,
                        template_id,
                        component_id,
                        True,
                        order
                    )
                    count += 1

        logger.info(f"✅ Migrated {count} template-component mappings")

    async def migrate_tech_stacks(self):
        """Migrate tech stacks"""
        count = 0

        for stack_id, data in TECH_STACK_COMBINATIONS.items():
            await self.pg.execute(
                """
                INSERT INTO tech_stacks
                (stack_id, name, frontend_tech, backend_tech, database_tech, deployment_tech, use_case)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (stack_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    frontend_tech = EXCLUDED.frontend_tech,
                    backend_tech = EXCLUDED.backend_tech,
                    database_tech = EXCLUDED.database_tech,
                    deployment_tech = EXCLUDED.deployment_tech,
                    use_case = EXCLUDED.use_case
                """,
                stack_id,
                data['name'],
                json.dumps(data.get('frontend', [])),
                json.dumps(data.get('backend', [])),
                json.dumps(data.get('database', [])),
                json.dumps(data.get('deployment', [])),
                data.get('use_case', '')
            )
            count += 1

        logger.info(f"✅ Migrated {count} tech stacks")

    async def migrate_agent_personas(self):
        """Migrate agent persona mappings"""
        count = 0

        # Map knowledge base persona roles to actual persona IDs
        persona_mapping = {
            'requirements_analyst': 'requirement_analyst',
            'solutions_architect': 'solution_architect',
            'backend_developer': 'backend_developer',
            'frontend_developer': 'frontend_developer',
            'fullstack_developer': 'backend_developer',  # Map to backend for now
            'mobile_developer': 'frontend_developer',    # Map to frontend for now
            'qa_engineer': 'qa_engineer',
            'devops_engineer': 'devops_engineer',
            'security_engineer': 'security_specialist'
        }

        for kb_role, data in AGENT_PERSONAS.items():
            agent_id = persona_mapping.get(kb_role, kb_role)

            await self.pg.execute(
                """
                INSERT INTO agent_persona_mappings
                (knowledge_base_role, agent_persona_id, display_name, best_for, skills)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (knowledge_base_role) DO UPDATE SET
                    agent_persona_id = EXCLUDED.agent_persona_id,
                    display_name = EXCLUDED.display_name,
                    best_for = EXCLUDED.best_for,
                    skills = EXCLUDED.skills
                """,
                kb_role,
                agent_id,
                data['name'],
                json.dumps(data.get('best_for', [])),
                json.dumps(data.get('skills', []))
            )
            count += 1

        logger.info(f"✅ Migrated {count} agent persona mappings")

    async def migrate_best_practices(self):
        """Migrate best practices"""
        count = 0

        for category, rules in BEST_PRACTICES.items():
            if isinstance(rules, dict):
                for rule_name, rule_data in rules.items():
                    await self.pg.execute(
                        """
                        INSERT INTO best_practices
                        (category, rule_name, rule_description, rule_data, priority)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (category, rule_name) DO UPDATE SET
                            rule_description = EXCLUDED.rule_description,
                            rule_data = EXCLUDED.rule_data,
                            priority = EXCLUDED.priority
                        """,
                        category,
                        rule_name,
                        f"Best practice for {category}: {rule_name}",
                        json.dumps(rule_data if isinstance(rule_data, (dict, list)) else {'value': rule_data}),
                        5
                    )
                    count += 1

        logger.info(f"✅ Migrated {count} best practice rules")

    async def migrate_validation_rules(self):
        """Migrate validation rules"""
        count = 0

        for rule_name, value in VALIDATION_RULES.items():
            rule_type = 'structure'
            if 'phase' in rule_name:
                rule_type = 'content'
            elif 'dependencies' in rule_name or 'chain' in rule_name:
                rule_type = 'dependency'

            await self.pg.execute(
                """
                INSERT INTO validation_rules
                (rule_name, rule_description, rule_type, rule_config, is_active, severity)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (rule_name) DO UPDATE SET
                    rule_description = EXCLUDED.rule_description,
                    rule_type = EXCLUDED.rule_type,
                    rule_config = EXCLUDED.rule_config,
                    is_active = EXCLUDED.is_active,
                    severity = EXCLUDED.severity
                """,
                rule_name,
                f"Validation rule: {rule_name}",
                rule_type,
                json.dumps({'value': value}),
                True,
                'error'
            )
            count += 1

        logger.info(f"✅ Migrated {count} validation rules")

    async def verify_migration(self):
        """Verify migration completed successfully"""
        tables = [
            'technical_components',
            'component_dependencies',
            'workflow_templates',
            'template_components',
            'tech_stacks',
            'agent_persona_mappings',
            'best_practices',
            'validation_rules'
        ]

        logger.info("\nVerification Results:")
        for table in tables:
            result = await self.pg.fetchval(f"SELECT COUNT(*) FROM {table}")
            logger.info(f"  {table}: {result} rows")


# Standalone execution
async def main():
    """Run migration"""
    postgres_manager = PostgresManager()
    await postgres_manager.connect()

    try:
        migration = KnowledgeBaseMigration(postgres_manager)
        await migration.run_migration()
    finally:
        await postgres_manager.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
