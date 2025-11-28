#!/usr/bin/env python3
"""
Comprehensive AI DAG Generation Test Suite

Tests all aspects of AI-powered DAG generation:
- Requirement analysis
- DAG generation for all templates
- Validation rules
- Persona assignment
- Edge cases
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.requirement_analyzer import RequirementAnalyzer
from services.ai_dag_generator import AIDAGGenerator
from services.dag_validator import DAGValidator
from services.dag_presenter import DAGPresenter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestResults:
    """Track test results"""
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self, test_name: str):
        self.total += 1
        self.passed += 1
        logger.info(f"✅ PASS: {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.total += 1
        self.failed += 1
        self.errors.append((test_name, error))
        logger.error(f"❌ FAIL: {test_name} - {error}")

    def summary(self):
        pass_rate = (self.passed / self.total * 100) if self.total > 0 else 0
        logger.info("\n" + "=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Tests: {self.total}")
        logger.info(f"Passed: {self.passed}")
        logger.info(f"Failed: {self.failed}")
        logger.info(f"Pass Rate: {pass_rate:.1f}%")

        if self.errors:
            logger.info("\nFailed Tests:")
            for test_name, error in self.errors:
                logger.info(f"  - {test_name}: {error}")

        return pass_rate >= 95.0  # 95% pass rate required


# Test scenarios for different project types
TEST_SCENARIOS = {
    "saas_app": {
        "requirement": """Build a multi-tenant SaaS application with:
        - User authentication and authorization (JWT, OAuth)
        - Subscription billing (Stripe integration)
        - Admin dashboard for management
        - REST API for third-party integrations
        - Real-time notifications
        - Deploy on AWS with auto-scaling
        Expected to handle 50,000 users""",
        "expected_complexity": "complex",
        "expected_min_phases": 8,
        "expected_max_phases": 12,
        "required_phase_types": ["research", "test", "deploy"],
        "expected_components": ["authentication", "api", "frontend", "database"]
    },

    "mobile_app": {
        "requirement": """Create a mobile fitness tracking app:
        - iOS and Android native apps
        - Activity tracking (steps, calories, workouts)
        - Social features (friends, challenges)
        - Integration with wearable devices
        - Cloud backend with real-time sync
        - Push notifications
        - In-app purchases""",
        "expected_complexity": "complex",
        "expected_min_phases": 10,
        "expected_max_phases": 15,
        "required_phase_types": ["research", "test", "deploy"],
        "expected_components": ["mobile", "api", "database", "notification"]
    },

    "microservice_api": {
        "requirement": """Develop a microservice for order processing:
        - RESTful API with OpenAPI documentation
        - Event-driven architecture (Kafka/RabbitMQ)
        - PostgreSQL database
        - Redis caching
        - Background job processing
        - Monitoring and logging
        - Docker deployment""",
        "expected_complexity": "medium",
        "expected_min_phases": 6,
        "expected_max_phases": 10,
        "required_phase_types": ["research", "test", "deploy"],
        "expected_components": ["api", "database", "queue", "caching"]
    },

    "realtime_platform": {
        "requirement": """Build a real-time collaboration platform:
        - WebSocket-based live updates
        - Document co-editing
        - Video conferencing integration
        - File sharing and version control
        - User presence indicators
        - Cross-platform (web, desktop)
        - High availability setup""",
        "expected_complexity": "complex",
        "expected_min_phases": 8,
        "expected_max_phases": 12,
        "required_phase_types": ["research", "test", "deploy"],
        "expected_components": ["realtime", "frontend", "api", "file_storage"]
    },

    "ecommerce_platform": {
        "requirement": """Create an e-commerce platform:
        - Product catalog with search
        - Shopping cart and checkout
        - Payment processing (Stripe, PayPal)
        - Inventory management
        - Order tracking
        - Customer reviews and ratings
        - Admin dashboard
        - Mobile-responsive design""",
        "expected_complexity": "complex",
        "expected_min_phases": 10,
        "expected_max_phases": 14,
        "required_phase_types": ["research", "test", "deploy"],
        "expected_components": ["frontend", "api", "database", "payment", "search"]
    },

    "enterprise_system": {
        "requirement": """Develop an enterprise resource planning system:
        - Multi-module architecture (HR, Finance, Inventory)
        - Role-based access control
        - Workflow automation
        - Reporting and analytics
        - Integration with existing systems
        - Compliance and audit logging
        - High security requirements
        - On-premise deployment""",
        "expected_complexity": "enterprise",
        "expected_min_phases": 12,
        "expected_max_phases": 20,
        "required_phase_types": ["research", "test", "deploy"],
        "expected_components": ["authentication", "database", "api", "admin_dashboard"]
    }
}


async def test_requirement_analysis(results: TestResults):
    """Test requirement analysis for all scenarios"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUITE 1: Requirement Analysis")
    logger.info("=" * 80)

    analyzer = RequirementAnalyzer()

    for scenario_name, scenario in TEST_SCENARIOS.items():
        try:
            analysis = await analyzer.analyze_requirement(scenario["requirement"])

            # Test 1: Complexity matches
            if analysis.complexity == scenario["expected_complexity"]:
                results.add_pass(f"{scenario_name}: Complexity detection")
            else:
                results.add_fail(
                    f"{scenario_name}: Complexity detection",
                    f"Expected {scenario['expected_complexity']}, got {analysis.complexity}"
                )

            # Test 2: Has functional requirements
            if len(analysis.functional_requirements) >= 3:
                results.add_pass(f"{scenario_name}: Functional requirements extraction")
            else:
                results.add_fail(
                    f"{scenario_name}: Functional requirements extraction",
                    f"Only {len(analysis.functional_requirements)} requirements found"
                )

            # Test 3: Has technical components
            if len(analysis.technical_components) >= 2:
                results.add_pass(f"{scenario_name}: Technical components identification")
            else:
                results.add_fail(
                    f"{scenario_name}: Technical components identification",
                    f"Only {len(analysis.technical_components)} components found"
                )

        except Exception as e:
            results.add_fail(f"{scenario_name}: Analysis", str(e))


async def test_dag_generation(results: TestResults):
    """Test DAG generation for all scenarios"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUITE 2: DAG Generation")
    logger.info("=" * 80)

    analyzer = RequirementAnalyzer()
    generator = AIDAGGenerator()

    for scenario_name, scenario in TEST_SCENARIOS.items():
        try:
            # Analyze requirement
            analysis = await analyzer.analyze_requirement(scenario["requirement"])

            # Generate DAG
            generated_dag = await generator.generate_dag(analysis, user_id="test_user")

            # Test 1: DAG was created
            if generated_dag.dag is not None:
                results.add_pass(f"{scenario_name}: DAG created")
            else:
                results.add_fail(f"{scenario_name}: DAG created", "DAG is None")
                continue

            # Test 2: Phase count in expected range
            phase_count = len(generated_dag.dag.nodes)
            if scenario["expected_min_phases"] <= phase_count <= scenario["expected_max_phases"]:
                results.add_pass(f"{scenario_name}: Phase count ({phase_count})")
            else:
                results.add_fail(
                    f"{scenario_name}: Phase count",
                    f"Expected {scenario['expected_min_phases']}-{scenario['expected_max_phases']}, got {phase_count}"
                )

            # Test 3: Has required phase types
            phase_types = set(node.task_type.value for node in generated_dag.dag.nodes.values())
            required_types = set(scenario["required_phase_types"])
            if required_types.issubset(phase_types):
                results.add_pass(f"{scenario_name}: Required phase types")
            else:
                missing = required_types - phase_types
                results.add_fail(
                    f"{scenario_name}: Required phase types",
                    f"Missing: {missing}"
                )

            # Test 4: Validation passed
            if generated_dag.validation_passed:
                results.add_pass(f"{scenario_name}: Validation")
            else:
                results.add_fail(f"{scenario_name}: Validation", "Validation failed")

            # Test 5: Has reasoning
            if generated_dag.reasoning and len(generated_dag.reasoning) > 20:
                results.add_pass(f"{scenario_name}: Reasoning provided")
            else:
                results.add_fail(f"{scenario_name}: Reasoning provided", "No reasoning")

            # Test 6: Has timeline estimate
            if generated_dag.estimated_timeline:
                results.add_pass(f"{scenario_name}: Timeline estimate")
            else:
                results.add_fail(f"{scenario_name}: Timeline estimate", "No timeline")

        except Exception as e:
            results.add_fail(f"{scenario_name}: Generation", str(e))


async def test_dag_validation(results: TestResults):
    """Test DAG validation rules"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUITE 3: DAG Validation")
    logger.info("=" * 80)

    analyzer = RequirementAnalyzer()
    generator = AIDAGGenerator()
    validator = DAGValidator()

    # Test with one scenario
    scenario = TEST_SCENARIOS["saas_app"]

    try:
        analysis = await analyzer.analyze_requirement(scenario["requirement"])
        generated_dag = await generator.generate_dag(analysis, user_id="test_user")

        # Run detailed validation
        validation_result = validator.validate_dag(generated_dag.dag)

        # Test 1: No circular dependencies
        if not validation_result.errors or not any("circular" in e.lower() for e in validation_result.errors):
            results.add_pass("Validation: No circular dependencies")
        else:
            results.add_fail("Validation: No circular dependencies", "Circular dependencies found")

        # Test 2: All dependencies exist
        if not validation_result.errors or not any("non-existent" in e.lower() for e in validation_result.errors):
            results.add_pass("Validation: All dependencies exist")
        else:
            results.add_fail("Validation: All dependencies exist", "Missing dependencies")

        # Test 3: Has starting phases
        if not validation_result.errors or not any("starting" in e.lower() for e in validation_result.errors):
            results.add_pass("Validation: Has starting phases")
        else:
            results.add_fail("Validation: Has starting phases", "No starting phases")

        # Test 4: Topological sort succeeds
        try:
            sorted_phases = generated_dag.dag.topological_sort()
            if len(sorted_phases) == len(generated_dag.dag.nodes):
                results.add_pass("Validation: Topological sort")
            else:
                results.add_fail("Validation: Topological sort", "Phase count mismatch")
        except Exception as e:
            results.add_fail("Validation: Topological sort", str(e))

    except Exception as e:
        results.add_fail("Validation: Tests", str(e))


async def test_edge_cases(results: TestResults):
    """Test edge cases and error handling"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUITE 4: Edge Cases")
    logger.info("=" * 80)

    analyzer = RequirementAnalyzer()
    generator = AIDAGGenerator()

    # Test 1: Very simple requirement
    try:
        simple_req = "Build a simple contact form"
        analysis = await analyzer.analyze_requirement(simple_req)
        generated_dag = await generator.generate_dag(analysis, user_id="test_user")

        if generated_dag.dag is not None and len(generated_dag.dag.nodes) >= 3:
            results.add_pass("Edge case: Simple requirement")
        else:
            results.add_fail("Edge case: Simple requirement", "Too few phases")
    except Exception as e:
        results.add_fail("Edge case: Simple requirement", str(e))

    # Test 2: Complex multi-platform requirement
    try:
        complex_req = """Build a comprehensive platform with web, iOS, Android, API,
        admin dashboard, analytics, reporting, multiple integrations, real-time features,
        and advanced security"""
        analysis = await analyzer.analyze_requirement(complex_req)
        generated_dag = await generator.generate_dag(analysis, user_id="test_user")

        if generated_dag.dag is not None and len(generated_dag.dag.nodes) <= 20:
            results.add_pass("Edge case: Complex multi-platform")
        else:
            results.add_fail("Edge case: Complex multi-platform", "Too many phases or no DAG")
    except Exception as e:
        results.add_fail("Edge case: Complex multi-platform", str(e))

    # Test 3: Requirement with technical jargon
    try:
        tech_req = """Implement a microservices architecture with Kubernetes orchestration,
        Istio service mesh, GraphQL federation, gRPC for inter-service communication,
        Kafka event streaming, Elasticsearch for logging"""
        analysis = await analyzer.analyze_requirement(tech_req)

        if len(analysis.technical_components) >= 3:
            results.add_pass("Edge case: Technical jargon")
        else:
            results.add_fail("Edge case: Technical jargon", "Failed to parse technical terms")
    except Exception as e:
        results.add_fail("Edge case: Technical jargon", str(e))


async def test_presentation_formatting(results: TestResults):
    """Test DAG presentation formatting"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUITE 5: Presentation Formatting")
    logger.info("=" * 80)

    analyzer = RequirementAnalyzer()
    generator = AIDAGGenerator()
    presenter = DAGPresenter()

    try:
        scenario = TEST_SCENARIOS["saas_app"]
        analysis = await analyzer.analyze_requirement(scenario["requirement"])
        generated_dag = await generator.generate_dag(analysis, user_id="test_user")

        # Format for presentation
        presentation = await presenter.format_dag_for_approval(generated_dag, "test_pending_id")

        # Test 1: Has all required sections
        required_sections = ["dag", "overview", "phases", "approval_actions"]
        if all(section in presentation for section in required_sections):
            results.add_pass("Presentation: Required sections")
        else:
            missing = [s for s in required_sections if s not in presentation]
            results.add_fail("Presentation: Required sections", f"Missing: {missing}")

        # Test 2: Overview has key info
        overview = presentation.get("overview", {})
        if all(key in overview for key in ["phase_count", "complexity", "validation_passed"]):
            results.add_pass("Presentation: Overview info")
        else:
            results.add_fail("Presentation: Overview info", "Missing overview fields")

        # Test 3: Phases are formatted
        phases = presentation.get("phases", [])
        if len(phases) > 0 and all("name" in p for p in phases):
            results.add_pass("Presentation: Phase formatting")
        else:
            results.add_fail("Presentation: Phase formatting", "Phases not properly formatted")

    except Exception as e:
        results.add_fail("Presentation: Tests", str(e))


async def main():
    """Run all test suites"""
    logger.info("=" * 80)
    logger.info("AI DAG GENERATION - COMPREHENSIVE TEST SUITE")
    logger.info("=" * 80)

    results = TestResults()

    # Run test suites
    await test_requirement_analysis(results)
    await test_dag_generation(results)
    await test_dag_validation(results)
    await test_edge_cases(results)
    await test_presentation_formatting(results)

    # Print summary
    success = results.summary()

    if success:
        logger.info("\n✅ TEST SUITE PASSED (95%+ pass rate)")
        return 0
    else:
        logger.info("\n❌ TEST SUITE FAILED (< 95% pass rate)")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
