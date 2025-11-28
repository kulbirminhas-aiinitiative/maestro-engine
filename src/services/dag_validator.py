#!/usr/bin/env python3
"""
DAG Validator

Comprehensive validation for generated DAG workflows.
Ensures DAGs meet all requirements before presenting to users.
"""

import logging
from typing import List, Set
from dataclasses import dataclass

from workflow.dag import DAG, TaskType

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of DAG validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]


class DAGValidator:
    """
    Validates DAG structure and completeness.

    Checks:
    - No circular dependencies
    - All dependencies exist
    - At least one starting phase
    - Essential phases included (testing, deployment)
    - Valid task types
    - Unique phase names
    """

    REQUIRED_PHASE_TYPES = {
        TaskType.RESEARCH,  # Requirements/research phase
        TaskType.TEST,      # Testing phase
        TaskType.DEPLOY     # Deployment phase
    }

    def validate_dag(self, dag: DAG) -> ValidationResult:
        """
        Perform comprehensive validation on DAG.

        Args:
            dag: DAG to validate

        Returns:
            ValidationResult with errors, warnings, and suggestions
        """
        errors = []
        warnings = []
        suggestions = []

        logger.info(f"Validating DAG: {dag.workflow_id} with {len(dag.nodes)} nodes")

        # 1. Check if DAG has nodes
        if len(dag.nodes) == 0:
            errors.append("DAG has no phases - must have at least one phase")
            return ValidationResult(False, errors, warnings, suggestions)

        # 2. Check for circular dependencies
        try:
            sorted_nodes = dag.topological_sort()
            logger.debug(f"✓ Topological sort successful - no circular dependencies")
        except ValueError as e:
            errors.append(f"Circular dependency detected: {str(e)}")
            logger.error(f"✗ Circular dependency found")

        # 3. Check all dependencies exist
        for node_id, node in dag.nodes.items():
            for dep in node.depends_on:
                if dep not in dag.nodes:
                    errors.append(f"Phase '{node_id}' depends on non-existent phase '{dep}'")
                    logger.error(f"✗ Missing dependency: {node_id} -> {dep}")

        # 4. Check for starting phases (no dependencies)
        starting_phases = [
            node_id for node_id, node in dag.nodes.items()
            if len(node.depends_on) == 0
        ]

        if len(starting_phases) == 0:
            errors.append("No starting phase found - at least one phase must have no dependencies")
            logger.error("✗ No starting phase")
        elif len(starting_phases) > 3:
            warnings.append(f"Multiple starting phases ({len(starting_phases)}) - consider consolidating")
            logger.warning(f"⚠ {len(starting_phases)} starting phases")

        # 5. Check for ending phases (no dependents)
        ending_phases = []
        for node_id in dag.nodes.keys():
            has_dependents = any(
                node_id in node.depends_on
                for node in dag.nodes.values()
            )
            if not has_dependents:
                ending_phases.append(node_id)

        if len(ending_phases) == 0:
            warnings.append("No clear ending phase - all phases have dependents (circular?)")
        elif len(ending_phases) > 3:
            warnings.append(f"Multiple ending phases ({len(ending_phases)}) - consider adding final integration phase")

        # 6. Check for required phase types
        present_types = set(node.task_type for node in dag.nodes.values())

        if TaskType.RESEARCH not in present_types:
            warnings.append("No research/requirements phase - consider adding initial planning phase")

        if TaskType.TEST not in present_types:
            errors.append("No testing phase found - testing is required for quality assurance")
            logger.error("✗ Missing testing phase")

        if TaskType.DEPLOY not in present_types:
            warnings.append("No deployment phase found - consider adding deployment/launch phase")

        # 7. Check phase naming (uniqueness)
        phase_names = [node.title for node in dag.nodes.values()]
        if len(phase_names) != len(set(phase_names)):
            errors.append("Duplicate phase names detected - all phase names must be unique")
            logger.error("✗ Duplicate phase names")

        # 8. Check phase IDs (valid format)
        for node_id in dag.nodes.keys():
            if not node_id.replace('_', '').isalnum():
                warnings.append(f"Phase ID '{node_id}' contains special characters - use alphanumeric and underscores only")

        # 9. Check for orphaned phases (not reachable from start)
        if starting_phases and not errors:
            reachable = set()
            to_visit = list(starting_phases)

            while to_visit:
                current = to_visit.pop(0)
                if current in reachable:
                    continue
                reachable.add(current)

                # Find phases that depend on current
                for node_id, node in dag.nodes.items():
                    if current in node.depends_on and node_id not in reachable:
                        to_visit.append(node_id)

            unreachable = set(dag.nodes.keys()) - reachable
            if unreachable:
                errors.append(f"Unreachable phases detected: {', '.join(unreachable)}")
                logger.error(f"✗ Unreachable phases: {unreachable}")

        # 10. Check priorities
        priorities = [node.priority for node in dag.nodes.values()]
        if len(set(priorities)) == 1:
            warnings.append("All phases have the same priority - consider varying priorities for execution order")

        # 11. Check for reasonable phase count
        if len(dag.nodes) < 3:
            warnings.append("Very few phases (< 3) - consider breaking down into more granular phases")
        elif len(dag.nodes) > 20:
            warnings.append("Many phases (> 20) - consider consolidating related phases")

        # 12. Check for long dependency chains
        if not errors:
            max_chain_length = self._calculate_max_chain_length(dag, starting_phases)
            if max_chain_length > 10:
                warnings.append(f"Long dependency chain detected ({max_chain_length} phases) - may cause delays")

        # 13. Check for parallel opportunities
        if not errors:
            parallel_groups = self._find_parallel_phases(dag)
            if parallel_groups:
                suggestions.append(f"Parallel execution opportunities: {len(parallel_groups)} groups can run concurrently")

        # 14. Check task type distribution
        type_counts = {}
        for node in dag.nodes.values():
            type_counts[node.task_type] = type_counts.get(node.task_type, 0) + 1

        if type_counts.get(TaskType.CODE, 0) == 0:
            warnings.append("No implementation (code) phases - consider adding development phases")

        # Generate final result
        is_valid = len(errors) == 0

        if is_valid:
            logger.info(f"✅ DAG validation PASSED - {len(warnings)} warnings, {len(suggestions)} suggestions")
        else:
            logger.error(f"❌ DAG validation FAILED - {len(errors)} errors")

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )

    def _calculate_max_chain_length(self, dag: DAG, starting_phases: List[str]) -> int:
        """Calculate the longest dependency chain in DAG"""
        max_length = 0

        def dfs(node_id: str, current_length: int):
            nonlocal max_length
            max_length = max(max_length, current_length)

            # Find phases that depend on this one
            for other_id, other_node in dag.nodes.items():
                if node_id in other_node.depends_on:
                    dfs(other_id, current_length + 1)

        for start in starting_phases:
            dfs(start, 1)

        return max_length

    def _find_parallel_phases(self, dag: DAG) -> List[List[str]]:
        """Find groups of phases that can execute in parallel"""
        parallel_groups = []

        # Group phases by their dependency set
        dep_groups = {}
        for node_id, node in dag.nodes.items():
            dep_key = tuple(sorted(node.depends_on))
            if dep_key not in dep_groups:
                dep_groups[dep_key] = []
            dep_groups[dep_key].append(node_id)

        # Groups with > 1 phase can run in parallel
        for dep_key, phases in dep_groups.items():
            if len(phases) > 1:
                parallel_groups.append(phases)

        return parallel_groups


# Standalone test
def test_dag_validator():
    """Test DAG validator"""
    from workflow.dag import WorkflowBuilder, TaskType

    validator = DAGValidator()

    # Test 1: Valid DAG
    print("Test 1: Valid DAG")
    print("="*60)

    valid_dag = (
        WorkflowBuilder("test_valid", "Valid Workflow")
        .add_task("req", "Requirements", "Gather requirements", TaskType.RESEARCH, priority=10)
        .add_task("design", "Design", "Create design", TaskType.DECISION, depends_on=["req"], priority=9)
        .add_task("code", "Development", "Write code", TaskType.CODE, depends_on=["design"], priority=8)
        .add_task("test", "Testing", "Run tests", TaskType.TEST, depends_on=["code"], priority=7)
        .add_task("deploy", "Deployment", "Deploy", TaskType.DEPLOY, depends_on=["test"], priority=6)
        .build()
    )

    result = validator.validate_dag(valid_dag)
    print(f"Valid: {result.is_valid}")
    print(f"Errors: {result.errors}")
    print(f"Warnings: {result.warnings}")

    # Test 2: Missing testing phase
    print("\nTest 2: Missing Testing Phase")
    print("="*60)

    no_test_dag = (
        WorkflowBuilder("test_no_test", "No Testing")
        .add_task("req", "Requirements", "Gather requirements", TaskType.RESEARCH)
        .add_task("code", "Development", "Write code", TaskType.CODE, depends_on=["req"])
        .add_task("deploy", "Deployment", "Deploy", TaskType.DEPLOY, depends_on=["code"])
        .build()
    )

    result = validator.validate_dag(no_test_dag)
    print(f"Valid: {result.is_valid}")
    print(f"Errors: {result.errors}")

    # Test 3: Parallel phases
    print("\nTest 3: Parallel Phases")
    print("="*60)

    parallel_dag = (
        WorkflowBuilder("test_parallel", "Parallel Workflow")
        .add_task("req", "Requirements", "Requirements", TaskType.RESEARCH)
        .add_task("frontend", "Frontend", "Build UI", TaskType.CODE, depends_on=["req"])
        .add_task("backend", "Backend", "Build API", TaskType.CODE, depends_on=["req"])
        .add_task("test", "Testing", "Test", TaskType.TEST, depends_on=["frontend", "backend"])
        .add_task("deploy", "Deploy", "Deploy", TaskType.DEPLOY, depends_on=["test"])
        .build()
    )

    result = validator.validate_dag(parallel_dag)
    print(f"Valid: {result.is_valid}")
    print(f"Suggestions: {result.suggestions}")


if __name__ == "__main__":
    test_dag_validator()
