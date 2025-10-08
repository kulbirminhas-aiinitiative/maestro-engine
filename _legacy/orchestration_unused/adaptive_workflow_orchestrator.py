#!/usr/bin/env python3
"""
Adaptive Workflow Orchestrator
Combines execution strategy decision team with working_tier_workflow pattern
to automatically select single-phase vs multi-phase execution based on requirements
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

# Import working tier workflow and decision team
sys.path.append('/data/maestro-v1')
sys.path.append('/data/maestro-v1/shared')

from working_tier_workflow import WorkingTierWorkflow, execute_tier_based_workflow
from execution_strategy_decision_team import (
    ExecutionStrategyDecisionTeam, ExecutionStrategy,
    make_execution_strategy_decision, quick_strategy_decision
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class WorkflowStrategy:
    """Workflow strategy definition"""
    strategy: ExecutionStrategy
    phases: List[str]
    description: str
    estimated_duration: str
    complexity_threshold: int

class AdaptiveWorkflowOrchestrator:
    """
    Orchestrator that automatically selects execution strategy and manages workflow

    Key Innovation: Multi-phase is just coordinated single phases
    - Single-phase: Direct execution with minimal checkpoints
    - Multi-phase: Multiple coordinated single-phase executions with reviews
    """

    def __init__(self, project_path: str, session_id: str = "", auto_deploy: bool = False):
        self.project_path = Path(project_path)
        self.session_id = session_id or f"adaptive_workflow_{int(time.time())}"
        self.auto_deploy = auto_deploy
        self.logger = logger

        # Strategy definitions
        self.strategies = {
            ExecutionStrategy.SINGLE_PHASE: WorkflowStrategy(
                strategy=ExecutionStrategy.SINGLE_PHASE,
                phases=[
                    "requirement_analysis",
                    "solution_design",
                    "implementation",
                    "deployment"
                ],
                description="Streamlined execution - one coordinated phase",
                estimated_duration="15-30 minutes",
                complexity_threshold=35
            ),
            ExecutionStrategy.MULTI_PHASE: WorkflowStrategy(
                strategy=ExecutionStrategy.MULTI_PHASE,
                phases=[
                    "requirement_analysis",
                    "solution_design",
                    "detailed_planning",
                    "implementation_phase_1",
                    "review_checkpoint",
                    "implementation_phase_2",
                    "integration_testing",
                    "deployment"
                ],
                description="Multiple coordinated single phases with checkpoints",
                estimated_duration="45-90 minutes",
                complexity_threshold=36
            )
        }

    async def execute_adaptive_workflow(self, requirement: str,
                                      force_strategy: ExecutionStrategy = None,
                                      additional_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute adaptive workflow with automatic strategy selection

        Args:
            requirement: Project requirement description
            force_strategy: Optional strategy override
            additional_context: Additional context for decision making

        Returns:
            Complete workflow execution results with strategy decision
        """
        self.logger.info("🚀 Starting Adaptive Workflow Orchestration")
        self.logger.info(f"📋 Requirement: {requirement[:100]}...")

        start_time = time.time()

        # Step 1: Strategy Decision (or use forced strategy)
        if force_strategy:
            strategy = force_strategy
            decision_time = 0
            decision_info = {
                'strategy': strategy.value,
                'forced': True,
                'confidence': 'override',
                'decision_time': 0
            }
            self.logger.info(f"🎯 Using forced strategy: {strategy.value}")
        else:
            decision_start = time.time()
            strategy_decision = await self._make_strategy_decision(requirement, additional_context)
            decision_time = time.time() - decision_start

            strategy = strategy_decision.strategy
            decision_info = {
                'strategy': strategy.value,
                'forced': False,
                'confidence': strategy_decision.confidence,
                'consensus_level': strategy_decision.consensus_level,
                'decision_time': decision_time,
                'reasoning': strategy_decision.final_reasoning,
                'risk_factors': strategy_decision.risk_factors,
                'success_factors': strategy_decision.success_factors
            }

            self.logger.info(f"🎯 Strategy Decision: {strategy.value}")
            self.logger.info(f"🤝 Team Consensus: {strategy_decision.consensus_level:.1%}")
            self.logger.info(f"⏱️ Decision Time: {decision_time:.1f}s")

        # Step 2: Execute Selected Strategy
        execution_start = time.time()

        if strategy == ExecutionStrategy.SINGLE_PHASE:
            workflow_result = await self._execute_single_phase_strategy(requirement)
        else:
            workflow_result = await self._execute_multi_phase_strategy(requirement)

        execution_time = time.time() - execution_start
        total_time = time.time() - start_time

        # Step 3: Compile Results
        final_result = {
            'adaptive_workflow': {
                'strategy_decision': decision_info,
                'execution_strategy': strategy.value,
                'strategy_definition': {
                    'phases': self.strategies[strategy].phases,
                    'description': self.strategies[strategy].description,
                    'estimated_duration': self.strategies[strategy].estimated_duration
                },
                'timing': {
                    'decision_time_s': decision_time,
                    'execution_time_s': execution_time,
                    'total_time_s': total_time
                },
                'success': workflow_result.get('success', False)
            },
            'workflow_execution': workflow_result,
            'project_path': str(self.project_path),
            'session_id': self.session_id
        }

        # Log final results
        success = final_result['adaptive_workflow']['success']
        self.logger.info(f"✅ Adaptive Workflow Complete: {'SUCCESS' if success else 'FAILED'}")
        self.logger.info(f"📊 Strategy Used: {strategy.value}")
        self.logger.info(f"⏱️ Total Time: {total_time:.1f}s")
        self.logger.info(f"📁 Project: {self.project_path}")

        return final_result

    async def _make_strategy_decision(self, requirement: str,
                                    additional_context: Dict[str, Any] = None) -> 'TeamDecision':
        """Make strategy decision using decision team"""
        self.logger.info("🎯 Making execution strategy decision with decision team")

        # Create temporary decision path
        decision_path = self.project_path / "decision_temp"
        decision_path.mkdir(parents=True, exist_ok=True)

        try:
            decision_team = ExecutionStrategyDecisionTeam(str(decision_path), self.session_id)

            # Enhanced context for decision making
            enhanced_context = {
                'session_id': self.session_id,
                'auto_deploy': self.auto_deploy,
                'workflow_type': 'adaptive',
                **(additional_context or {})
            }

            decision = await decision_team.make_execution_strategy_decision(
                requirement, enhanced_context
            )

            return decision

        except Exception as e:
            self.logger.error(f"❌ Strategy decision failed: {e}")
            # Fallback to simple keyword-based decision
            return await self._fallback_strategy_decision(requirement)

    async def _fallback_strategy_decision(self, requirement: str) -> 'TeamDecision':
        """Fallback strategy decision using simple keyword analysis"""
        from execution_strategy_decision_team import TeamDecision

        self.logger.info("🔄 Using fallback strategy decision")

        # Simple complexity analysis
        complex_keywords = ['enterprise', 'microservices', 'scalable', 'real-time', 'compliance', 'millions']
        medium_keywords = ['api', 'database', 'authentication', 'integration', 'dashboard']

        requirement_lower = requirement.lower()
        complex_count = sum(1 for keyword in complex_keywords if keyword in requirement_lower)
        medium_count = sum(1 for keyword in medium_keywords if keyword in requirement_lower)

        if complex_count >= 2:
            strategy = ExecutionStrategy.MULTI_PHASE
            confidence = 'medium'
            reasoning = f"High complexity detected: {complex_count} complex indicators"
        elif complex_count >= 1 or medium_count >= 3:
            strategy = ExecutionStrategy.MULTI_PHASE
            confidence = 'medium'
            reasoning = f"Medium-high complexity: {complex_count} complex, {medium_count} medium indicators"
        else:
            strategy = ExecutionStrategy.SINGLE_PHASE
            confidence = 'medium'
            reasoning = f"Low-medium complexity: {complex_count} complex, {medium_count} medium indicators"

        return TeamDecision(
            strategy=strategy,
            confidence=confidence,
            consensus_level=0.8,  # Reasonable consensus for fallback
            individual_recommendations={
                'fallback_analyzer': {
                    'recommendation': strategy.value,
                    'reasoning': reasoning,
                    'confidence': confidence
                }
            },
            final_reasoning=reasoning,
            risk_factors=['Fallback decision method used'],
            success_factors=['Simple and fast decision making']
        )

    async def _execute_single_phase_strategy(self, requirement: str) -> Dict[str, Any]:
        """
        Execute single-phase strategy

        Single phase = One coordinated execution with all personas working together
        """
        self.logger.info("📈 Executing Single-Phase Strategy (Coordinated Execution)")

        # Single coordinated execution using working tier workflow
        workflow = WorkingTierWorkflow(
            str(self.project_path),
            self.session_id,
            auto_deploy=self.auto_deploy
        )

        # Execute as single coordinated phase
        result = await workflow.execute_tier_workflow(requirement)

        # Enhance result with strategy info
        result['execution_strategy'] = 'single_phase'
        result['strategy_description'] = 'Single coordinated execution with all team members'
        result['checkpoints'] = ['final_review']

        return result

    async def _execute_multi_phase_strategy(self, requirement: str) -> Dict[str, Any]:
        """
        Execute multi-phase strategy

        Multi-phase = Multiple coordinated single phases with reviews between
        Key insight: Each phase is itself a "single phase" but with checkpoints
        """
        self.logger.info("📊 Executing Multi-Phase Strategy (Multiple Coordinated Phases)")

        # Phase 1: Requirements & Architecture (single coordinated phase)
        self.logger.info("🎯 Phase 1: Requirements & Architecture Analysis")

        phase1_path = self.project_path / "phase1_requirements"
        phase1_workflow = WorkingTierWorkflow(str(phase1_path), f"{self.session_id}_phase1")

        # Execute just requirements and architecture in coordinated manner
        phase1_requirement = f"""
        PHASE 1 - REQUIREMENTS & ARCHITECTURE ANALYSIS:

        {requirement}

        Focus on:
        1. Detailed requirements analysis
        2. Solution architecture design
        3. Technical specification
        4. Risk assessment

        Create comprehensive analysis and architecture documents for Phase 2 implementation.
        """

        phase1_result = await phase1_workflow.execute_tier_workflow(phase1_requirement)

        # Checkpoint 1: Review Phase 1
        self.logger.info("🔍 Checkpoint 1: Reviewing Requirements & Architecture")
        await asyncio.sleep(1)  # Simulate review time

        if not phase1_result.get('success', False):
            return {
                'success': False,
                'error': 'Phase 1 failed - stopping multi-phase execution',
                'phase_results': {'phase1': phase1_result}
            }

        # Phase 2: Implementation (single coordinated phase)
        self.logger.info("🎯 Phase 2: Implementation & Testing")

        phase2_path = self.project_path / "phase2_implementation"
        phase2_workflow = WorkingTierWorkflow(str(phase2_path), f"{self.session_id}_phase2")

        # Enhanced requirement with Phase 1 insights
        phase2_requirement = f"""
        PHASE 2 - IMPLEMENTATION & TESTING:

        Building on Phase 1 analysis, implement:
        {requirement}

        Phase 1 completed successfully with architecture and requirements.

        Focus on:
        1. Full implementation based on Phase 1 architecture
        2. Comprehensive testing
        3. Integration validation
        4. Performance optimization

        Create production-ready implementation.
        """

        phase2_result = await phase2_workflow.execute_tier_workflow(phase2_requirement)

        # Checkpoint 2: Review Phase 2
        self.logger.info("🔍 Checkpoint 2: Reviewing Implementation")
        await asyncio.sleep(1)  # Simulate review time

        if not phase2_result.get('success', False):
            return {
                'success': False,
                'error': 'Phase 2 failed - implementation issues detected',
                'phase_results': {'phase1': phase1_result, 'phase2': phase2_result}
            }

        # Phase 3: Deployment & Validation (single coordinated phase)
        self.logger.info("🎯 Phase 3: Deployment & Validation")

        phase3_path = self.project_path / "phase3_deployment"
        phase3_workflow = WorkingTierWorkflow(str(phase3_path), f"{self.session_id}_phase3", auto_deploy=self.auto_deploy)

        phase3_requirement = f"""
        PHASE 3 - DEPLOYMENT & VALIDATION:

        Final phase for: {requirement}

        Phase 1 & 2 completed successfully with full implementation.

        Focus on:
        1. Production deployment
        2. End-to-end validation
        3. Performance testing
        4. Final documentation

        Create production-ready deployment.
        """

        phase3_result = await phase3_workflow.execute_tier_workflow(phase3_requirement)

        # Final Checkpoint
        self.logger.info("🔍 Final Checkpoint: Validating Complete System")
        await asyncio.sleep(1)  # Simulate final validation

        # Compile multi-phase results
        all_files = []
        for phase_result in [phase1_result, phase2_result, phase3_result]:
            all_files.extend(phase_result.get('generated_files', []))

        success = all([
            phase1_result.get('success', False),
            phase2_result.get('success', False),
            phase3_result.get('success', False)
        ])

        return {
            'success': success,
            'execution_strategy': 'multi_phase',
            'strategy_description': 'Multiple coordinated phases with checkpoints',
            'checkpoints': ['phase1_review', 'phase2_review', 'final_validation'],
            'phase_results': {
                'phase1_requirements_architecture': phase1_result,
                'phase2_implementation_testing': phase2_result,
                'phase3_deployment_validation': phase3_result
            },
            'summary': {
                'total_phases': 3,
                'successful_phases': sum(1 for r in [phase1_result, phase2_result, phase3_result] if r.get('success', False)),
                'total_files_generated': len(all_files),
                'overall_success': success
            },
            'generated_files': all_files,
            'project_path': str(self.project_path)
        }


# Convenience functions
async def execute_adaptive_workflow(requirement: str, project_path: str,
                                  force_strategy: ExecutionStrategy = None,
                                  auto_deploy: bool = False,
                                  additional_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Execute adaptive workflow with automatic strategy selection

    Args:
        requirement: Project requirement description
        project_path: Path for project output
        force_strategy: Optional strategy override
        auto_deploy: Whether to automatically deploy
        additional_context: Additional context for decision making

    Returns:
        Complete workflow execution results
    """
    orchestrator = AdaptiveWorkflowOrchestrator(project_path, auto_deploy=auto_deploy)
    return await orchestrator.execute_adaptive_workflow(
        requirement, force_strategy, additional_context
    )

async def execute_adaptive_single_phase(requirement: str, project_path: str,
                                      auto_deploy: bool = False) -> Dict[str, Any]:
    """Execute with forced single-phase strategy"""
    return await execute_adaptive_workflow(
        requirement, project_path, ExecutionStrategy.SINGLE_PHASE, auto_deploy
    )

async def execute_adaptive_multi_phase(requirement: str, project_path: str,
                                     auto_deploy: bool = False) -> Dict[str, Any]:
    """Execute with forced multi-phase strategy"""
    return await execute_adaptive_workflow(
        requirement, project_path, ExecutionStrategy.MULTI_PHASE, auto_deploy
    )


# Demo
async def demo_adaptive_workflow():
    """Demonstrate adaptive workflow with different complexity levels"""

    test_cases = [
        {
            "name": "Simple Task Manager",
            "requirement": "Create a simple task management app with user login and basic CRUD operations for tasks",
            "expected_strategy": "single_phase"
        },
        {
            "name": "Enterprise E-commerce",
            "requirement": "Build an enterprise e-commerce platform with microservices architecture, real-time inventory management, payment processing, recommendation engine, and support for millions of users globally",
            "expected_strategy": "multi_phase"
        },
        {
            "name": "Healthcare System",
            "requirement": "Develop a HIPAA-compliant patient management system with electronic health records, appointment scheduling, billing integration, and regulatory reporting",
            "expected_strategy": "multi_phase"
        }
    ]

    print("🚀 Adaptive Workflow Orchestrator Demo")
    print("=" * 60)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test Case {i}: {test_case['name']}")
        print(f"📝 Requirement: {test_case['requirement'][:80]}...")
        print(f"🎯 Expected Strategy: {test_case['expected_strategy']}")

        try:
            project_path = f"/tmp/adaptive_demo_{i}"

            start_time = time.time()
            result = await execute_adaptive_workflow(
                requirement=test_case['requirement'],
                project_path=project_path,
                additional_context={'test_case': test_case['name']}
            )
            execution_time = time.time() - start_time

            # Extract results
            strategy_used = result['adaptive_workflow']['execution_strategy']
            success = result['adaptive_workflow']['success']
            decision_time = result['adaptive_workflow']['timing']['decision_time_s']

            print(f"✅ Strategy Selected: {strategy_used}")
            print(f"🎯 Match Expected: {'✅' if strategy_used == test_case['expected_strategy'] else '❌'}")
            print(f"🎭 Success: {'✅' if success else '❌'}")
            print(f"⏱️ Decision Time: {decision_time:.1f}s")
            print(f"⏱️ Total Time: {execution_time:.1f}s")

            # Show strategy reasoning if available
            reasoning = result['adaptive_workflow']['strategy_decision'].get('reasoning', '')
            if reasoning:
                print(f"💭 Reasoning: {reasoning[:100]}...")

        except Exception as e:
            print(f"❌ Test failed: {e}")

    print(f"\n🏆 Adaptive Workflow Demo completed!")


if __name__ == "__main__":
    asyncio.run(demo_adaptive_workflow())