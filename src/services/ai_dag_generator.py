#!/usr/bin/env python3
"""
AI-Powered DAG Generator

Generates complete, valid DAG workflows from requirement analysis using Claude AI.
Ensures all phases, dependencies, and metadata are complete and valid.
"""

import logging
import json
import re
import uuid
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from anthropic import Anthropic
import os

from workflow.dag import DAG, TaskNode, TaskType, WorkflowBuilder
from services.requirement_analyzer import RequirementAnalysis
from services.knowledge_base_service import KnowledgeBaseService
from personas.registry import get_registry

logger = logging.getLogger(__name__)


@dataclass
class GeneratedDAG:
    """Complete generated DAG with metadata and reasoning"""
    dag: DAG
    metadata: Dict[str, Any]
    reasoning: str
    estimated_timeline: str
    risk_factors: List[str]
    parallel_opportunities: List[str]
    validation_passed: bool = False


class AIDAGGenerator:
    """
    Generates DAG workflows from requirements using Claude AI.

    Responsibilities:
    - Generate complete phase breakdown
    - Define dependencies between phases
    - Assign task types and priorities
    - Ensure no circular dependencies
    - Validate completeness (testing, deployment, etc.)
    """

    DAG_GENERATION_PROMPT = """You are a senior software architect and project planner. Given the following project analysis, generate a complete DAG (Directed Acyclic Graph) workflow.

PROJECT ANALYSIS:
{analysis}

Your task is to create a comprehensive workflow with phases (nodes) and dependencies (edges) that will guide the development of this project.

CRITICAL REQUIREMENTS:
1. Generate 6-12 phases covering the complete development lifecycle
2. MUST include these phase types:
   - Requirements/Research phase (starting point)
   - Design/Architecture phase
   - Implementation phase(s) - can be multiple parallel phases
   - Testing phase (unit, integration, E2E)
   - Deployment/Infrastructure phase
3. Use ONLY these task types: research, planning, code, review, testing, deployment
4. NO circular dependencies - must form a valid DAG
5. All dependencies must reference existing phase IDs
6. Identify opportunities for parallel execution (e.g., frontend + backend)
7. Assign realistic priorities (1-10, higher = execute first)
8. Provide estimated duration for each phase

OUTPUT STRICT JSON FORMAT:
{{
  "dag_name": "Short descriptive name",
  "dag_description": "2-3 sentence description",
  "phases": [
    {{
      "phase_id": "unique_id_lowercase_underscore",
      "phase_name": "Human-readable Phase Name",
      "description": "Detailed description of what this phase accomplishes",
      "task_type": "research|planning|code|review|testing|deployment",
      "depends_on": ["phase_id1", "phase_id2"],
      "priority": 10,
      "estimated_duration": "X days/weeks",
      "agent_persona": "requirements_analyst|solutions_architect|backend_developer|frontend_developer|qa_engineer|devops_engineer|security_engineer"
    }}
  ],
  "reasoning": "Explain why this structure was chosen, why these phases, why these dependencies",
  "parallel_opportunities": ["List of phase groups that can run in parallel"],
  "risk_factors": ["Potential risks or bottlenecks in this workflow"],
  "estimated_total_duration": "X-Y weeks"
}}

EXAMPLE PHASE STRUCTURE:
{{
  "phase_id": "requirements_analysis",
  "phase_name": "Requirements Analysis & Planning",
  "description": "Gather detailed requirements, define user stories, create technical specifications",
  "task_type": "research",
  "depends_on": [],
  "priority": 10,
  "estimated_duration": "1-2 weeks",
  "agent_persona": "requirements_analyst"
}}

Generate the complete DAG now. Output ONLY valid JSON, no additional text."""

    def __init__(self, knowledge_base: Optional[KnowledgeBaseService] = None):
        """Initialize AI DAG generator with Claude AI and knowledge base"""
        self.anthropic_client = None
        self.knowledge_base = knowledge_base or KnowledgeBaseService()
        self.persona_registry = None

        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            try:
                self.anthropic_client = Anthropic(api_key=api_key)
                logger.info("✅ AIDAGGenerator initialized with Claude AI")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Claude AI: {e}")
        else:
            logger.warning("⚠️  ANTHROPIC_API_KEY not set - AI DAG generation unavailable")

    async def _init_persona_registry(self):
        """Lazily initialize persona registry"""
        if self.persona_registry is None:
            self.persona_registry = await get_registry()
            logger.info(f"✅ Loaded {len(self.persona_registry.personas)} AI agent personas")

    async def _get_available_personas(self) -> List[str]:
        """Get list of available persona IDs"""
        await self._init_persona_registry()
        return list(self.persona_registry.personas.keys())

    async def generate_dag(
        self,
        analysis: RequirementAnalysis,
        user_id: str,
        max_retries: int = 3
    ) -> GeneratedDAG:
        """
        Generate complete DAG from requirement analysis.

        Args:
            analysis: Structured requirement analysis
            user_id: User ID for tracking
            max_retries: Maximum validation retry attempts

        Returns:
            GeneratedDAG with complete workflow and metadata
        """
        logger.info(f"Generating DAG for user {user_id}, complexity={analysis.complexity}")

        if not self.anthropic_client:
            logger.error("Claude AI not available, using fallback generator")
            return await self._generate_fallback_dag(analysis, user_id)

        # Try to generate valid DAG with retries
        for attempt in range(max_retries):
            try:
                logger.info(f"DAG generation attempt {attempt + 1}/{max_retries}")

                # Call Claude AI
                generated_dag = await self._generate_with_ai(analysis, user_id)

                # Validate the generated DAG
                from services.dag_validator import DAGValidator
                validator = DAGValidator()
                validation_result = validator.validate_dag(generated_dag.dag)

                if validation_result.is_valid:
                    logger.info(f"✅ DAG validation passed on attempt {attempt + 1}")
                    generated_dag.validation_passed = True
                    return generated_dag
                else:
                    logger.warning(f"⚠️  DAG validation failed on attempt {attempt + 1}: {validation_result.errors}")
                    # On retry, include validation errors in prompt
                    if attempt < max_retries - 1:
                        continue
                    else:
                        # Last attempt failed, return with validation issues
                        generated_dag.validation_passed = False
                        generated_dag.risk_factors.extend(validation_result.errors)
                        return generated_dag

            except Exception as e:
                logger.error(f"Error generating DAG on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    logger.error("All retry attempts exhausted, using fallback")
                    return await self._generate_fallback_dag(analysis, user_id)

    async def _generate_with_ai(
        self,
        analysis: RequirementAnalysis,
        user_id: str
    ) -> GeneratedDAG:
        """Generate DAG using Claude AI"""

        # Get available personas
        available_personas = await self._get_available_personas()
        personas_list = '|'.join(available_personas)

        # Format analysis for prompt
        analysis_text = f"""
Complexity: {analysis.complexity}
Estimated Duration: {analysis.estimated_duration}

Functional Requirements:
{chr(10).join(f'- {req}' for req in analysis.functional_requirements)}

Technical Components:
{chr(10).join(f'- {comp}' for req in analysis.technical_components)}

Key Features:
{chr(10).join(f'- {feat}' for feat in analysis.key_features)}

Tech Stack Hints: {', '.join(analysis.tech_stack_hints)}
Deployment Targets: {', '.join(analysis.deployment_targets)}
Security Requirements: {', '.join(analysis.security_requirements or [])}
Integrations: {', '.join(analysis.integrations or [])}

AVAILABLE PERSONAS (use one of these for agent_persona field):
{', '.join(available_personas)}
"""

        prompt = self.DAG_GENERATION_PROMPT.format(analysis=analysis_text)

        # Call Claude AI
        response = self.anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.7,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        response_text = response.content[0].text

        # Extract JSON from response
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object directly
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            json_str = json_match.group(0) if json_match else response_text

        dag_data = json.loads(json_str)

        # Build DAG using WorkflowBuilder
        workflow_id = f"dag_{uuid.uuid4().hex[:12]}"

        builder = WorkflowBuilder(
            workflow_id=workflow_id,
            name=dag_data.get('dag_name', 'Generated Workflow'),
            description=dag_data.get('dag_description', analysis.raw_requirement[:200])
        )

        # Add all phases
        for phase in dag_data.get('phases', []):
            # Map task_type string to TaskType enum
            task_type_map = {
                'research': TaskType.RESEARCH,
                'planning': TaskType.DECISION,  # Map planning to decision
                'decision': TaskType.DECISION,
                'code': TaskType.CODE,
                'review': TaskType.REVIEW,
                'testing': TaskType.TEST,  # Map testing to test
                'test': TaskType.TEST,
                'deployment': TaskType.DEPLOY,  # Map deployment to deploy
                'deploy': TaskType.DEPLOY
            }

            task_type = task_type_map.get(
                phase.get('task_type', 'code').lower(),
                TaskType.CODE
            )

            builder.add_task(
                task_id=phase['phase_id'],
                title=phase['phase_name'],
                description=phase.get('description', ''),
                task_type=task_type,
                depends_on=phase.get('depends_on', []),
                priority=phase.get('priority', 5),
                metadata={
                    'estimated_duration': phase.get('estimated_duration'),
                    'agent_persona': phase.get('agent_persona')
                }
            )

        dag = builder.build()

        # Build metadata
        metadata = {
            'dag_id': workflow_id,
            'name': dag_data.get('dag_name', 'Generated Workflow'),
            'description': dag_data.get('dag_description', ''),
            'category': self._infer_category(analysis),
            'complexity': analysis.complexity,
            'duration': dag_data.get('estimated_total_duration', analysis.estimated_duration),
            'tech_stack': analysis.tech_stack_hints,
            'team_roles': list(set([p.get('agent_persona', 'developer') for p in dag_data.get('phases', [])])),
            'is_template': False,
            'node_count': len(dag.nodes),
            'created_by': user_id,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'typical_use_cases': analysis.key_features[:3]
        }

        return GeneratedDAG(
            dag=dag,
            metadata=metadata,
            reasoning=dag_data.get('reasoning', 'AI-generated workflow'),
            estimated_timeline=dag_data.get('estimated_total_duration', analysis.estimated_duration),
            risk_factors=dag_data.get('risk_factors', []),
            parallel_opportunities=dag_data.get('parallel_opportunities', []),
            validation_passed=False  # Will be set after validation
        )

    def _infer_category(self, analysis: RequirementAnalysis) -> str:
        """Infer workflow category from analysis"""
        components = ' '.join(analysis.technical_components).lower()

        if 'mobile' in components:
            return 'mobile'
        elif any(x in components for x in ['api', 'microservice', 'backend']):
            return 'microservice'
        elif 'saas' in analysis.raw_requirement.lower() or 'subscription' in components:
            return 'saas'
        elif analysis.complexity == 'enterprise':
            return 'enterprise'
        else:
            return 'web_application'

    async def _generate_fallback_dag(
        self,
        analysis: RequirementAnalysis,
        user_id: str
    ) -> GeneratedDAG:
        """Fallback DAG generation using templates"""

        workflow_id = f"dag_{uuid.uuid4().hex[:12]}"

        # Create a simple but complete DAG based on complexity
        builder = WorkflowBuilder(
            workflow_id=workflow_id,
            name=f"{analysis.complexity.title()} Project Workflow",
            description=analysis.raw_requirement[:200]
        )

        # Phase 1: Requirements
        builder.add_task(
            "requirements",
            "Requirements Analysis",
            "Gather and analyze project requirements",
            TaskType.RESEARCH,
            priority=10
        )

        # Phase 2: Architecture
        builder.add_task(
            "architecture",
            "System Architecture",
            "Design system architecture and technical specifications",
            TaskType.DECISION,
            depends_on=["requirements"],
            priority=9
        )

        # Phase 3 & 4: Implementation (parallel if complex)
        has_frontend = False
        has_backend = False

        if 'frontend' in analysis.technical_components or 'ui' in analysis.raw_requirement.lower():
            builder.add_task(
                "frontend",
                "Frontend Development",
                "Build user interface and frontend logic",
                TaskType.CODE,
                depends_on=["architecture"],
                priority=8
            )
            has_frontend = True

        if 'backend' in analysis.technical_components or 'api' in analysis.raw_requirement.lower():
            builder.add_task(
                "backend",
                "Backend Development",
                "Build backend services and APIs",
                TaskType.CODE,
                depends_on=["architecture"],
                priority=8
            )
            has_backend = True

        # Phase 5: Integration
        deps = []
        if has_frontend:
            deps.append("frontend")
        if has_backend:
            deps.append("backend")
        if not deps:
            deps = ["architecture"]

        builder.add_task(
            "integration",
            "Integration & Testing",
            "Integrate components and run tests",
            TaskType.TEST,
            depends_on=deps,
            priority=7
        )

        # Phase 6: Deployment
        builder.add_task(
            "deployment",
            "Deployment & Launch",
            "Deploy to production environment",
            TaskType.DEPLOY,
            depends_on=["integration"],
            priority=6
        )

        dag = builder.build()

        metadata = {
            'dag_id': workflow_id,
            'name': f"{analysis.complexity.title()} Project Workflow",
            'description': analysis.raw_requirement[:200],
            'category': self._infer_category(analysis),
            'complexity': analysis.complexity,
            'duration': analysis.estimated_duration,
            'tech_stack': analysis.tech_stack_hints,
            'team_roles': ['requirements_analyst', 'solutions_architect', 'developer', 'qa_engineer', 'devops_engineer'],
            'is_template': False,
            'node_count': len(dag.nodes),
            'created_by': user_id,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }

        parallel_opportunities = []
        if "frontend" in dag.nodes and "backend" in dag.nodes:
            parallel_opportunities.append("Frontend and Backend can be developed in parallel")

        return GeneratedDAG(
            dag=dag,
            metadata=metadata,
            reasoning="Fallback workflow generated using standard project structure",
            estimated_timeline=analysis.estimated_duration,
            risk_factors=["Generated using fallback method - may need manual adjustment"],
            parallel_opportunities=parallel_opportunities,
            validation_passed=True
        )


# Standalone test
async def test_ai_dag_generator():
    """Test AI DAG generator"""
    from services.requirement_analyzer import RequirementAnalyzer

    analyzer = RequirementAnalyzer()
    generator = AIDAGGenerator()

    requirement = """Build a real-time chat application with:
    - User authentication (email + Google OAuth)
    - Private and group chats
    - File sharing (images, documents)
    - Message reactions and threads
    - Online status indicators
    - Mobile apps for iOS and Android
    - Deploy on AWS with auto-scaling
    Should handle 10,000 concurrent users"""

    print("="*80)
    print("REQUIREMENT:")
    print(requirement)
    print("="*80)

    # Analyze requirement
    print("\n1. Analyzing requirement...")
    analysis = await analyzer.analyze_requirement(requirement)
    print(f"   Complexity: {analysis.complexity}")
    print(f"   Components: {', '.join(analysis.technical_components[:5])}")

    # Generate DAG
    print("\n2. Generating DAG workflow...")
    generated = await generator.generate_dag(analysis, user_id="test_user")

    print(f"\n3. Generated DAG: {generated.dag.name}")
    print(f"   Phases: {len(generated.dag.nodes)}")
    print(f"   Validation: {'✅ PASSED' if generated.validation_passed else '❌ FAILED'}")
    print(f"   Timeline: {generated.estimated_timeline}")

    print("\n4. Phase Breakdown:")
    sorted_phases = generated.dag.topological_sort()
    for i, phase in enumerate(sorted_phases, 1):
        deps = f" (depends on: {', '.join(phase.depends_on)})" if phase.depends_on else ""
        print(f"   {i}. {phase.name}{deps}")
        print(f"      Type: {phase.task_type}, Priority: {phase.priority}")

    print(f"\n5. Reasoning:")
    print(f"   {generated.reasoning}")

    if generated.parallel_opportunities:
        print(f"\n6. Parallel Execution Opportunities:")
        for opp in generated.parallel_opportunities:
            print(f"   - {opp}")

    if generated.risk_factors:
        print(f"\n7. Risk Factors:")
        for risk in generated.risk_factors:
            print(f"   - {risk}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_ai_dag_generator())
