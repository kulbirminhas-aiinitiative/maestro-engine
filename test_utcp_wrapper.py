#!/usr/bin/env python3
"""
MAESTRO UTCP Test Wrapper
Comprehensive testing framework for all UTCP functionalities

Features tested:
1. Basic code generation
2. PDF document generation
3. Quality-Fabric integration
4. RAG template retrieval
5. MCP context sharing
6. UTCP distributed execution
7. Git template publishing
8. Multi-persona workflows
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from maestro_mcp.enhanced_lean_ultimate_mega_team_utcp import (
    EnhancedTeamConfig,
    UTCPToolConfig,
    execute_enhanced_lean_workflow_utcp,
)


class UTCPTestWrapper:
    """Wrapper for testing UTCP functionalities"""

    def __init__(self):
        self.results = []
        self.quality_fabric_url = "http://localhost:8000"
        self.template_registry_url = "http://localhost:9600"

    def _print_header(self, title: str):
        """Print test header"""
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80)

    def _print_result(self, test_name: str, success: bool, details: str = ""):
        """Print test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")
        if details:
            print(f"    {details}")

    async def _check_service(self, name: str, url: str, endpoint: str = "/health") -> bool:
        """Check if a service is running"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{url}{endpoint}")
                return response.status_code == 200
        except Exception as e:
            print(f"    ⚠️  {name} not available at {url}: {e}")
            return False

    async def check_dependencies(self):
        """Test 0: Check all service dependencies"""
        self._print_header("Test 0: Dependency Check")

        services = {
            "Quality-Fabric": (self.quality_fabric_url, "/health"),
            "Template Registry": (self.template_registry_url, "/health"),
            "Backend API": ("http://localhost:5000", "/health"),
            "BFF Service": ("http://localhost:4001", "/health"),
        }

        all_ok = True
        for name, (url, endpoint) in services.items():
            available = await self._check_service(name, url, endpoint)
            self._print_result(name, available, url)
            if not available:
                all_ok = False

        return all_ok

    async def test_basic_workflow(self):
        """Test 1: Basic code generation workflow"""
        self._print_header("Test 1: Basic Code Generation")

        start = time.time()

        try:
            config = EnhancedTeamConfig(
                enable_utcp=False,  # Local execution
                enable_rag=True,
                enable_mcp=True,
                project_name="test_basic_calc",
            )

            result = await execute_enhanced_lean_workflow_utcp(
                requirement="Create a simple calculator web app with HTML, CSS, and JavaScript",
                config=config,
            )

            duration = time.time() - start

            success = result.get("success", False)
            files = result.get("files_generated", [])
            project_path = result.get("project_path", "")

            self._print_result(
                "Basic Workflow", success, f"{len(files)} files in {duration:.2f}s - {project_path}"
            )

            self.results.append(
                {
                    "test": "basic_workflow",
                    "success": success,
                    "duration": duration,
                    "files_count": len(files),
                    "project_path": project_path,
                }
            )

            return result

        except Exception as e:
            self._print_result("Basic Workflow", False, f"Error: {e}")
            return {"success": False, "error": str(e)}

    async def test_pdf_generation(self):
        """Test 2: PDF document generation"""
        self._print_header("Test 2: PDF Document Generation")

        start = time.time()

        try:
            config = EnhancedTeamConfig(
                enable_utcp=False,
                enable_rag=True,
                enable_mcp=True,
                project_name="test_pdf_report",
                selected_personas=["requirement_analyst", "backend_developer"],
            )

            result = await execute_enhanced_lean_workflow_utcp(
                requirement="""Create a Python script that generates a professional PDF report.

Requirements:
- Use reportlab library to generate PDF
- Include title, sections, paragraphs, and a simple table
- Add page numbers and headers
- Create a sample report about "Software Testing Best Practices"
- Output file should be named 'testing_report.pdf'
- Include proper formatting with fonts, colors, and spacing
                """,
                config=config,
            )

            duration = time.time() - start
            success = result.get("success", False)
            files = result.get("files_generated", [])

            # Check if PDF was created
            has_pdf = any(".pdf" in str(f).lower() or "pdf" in str(f).lower() for f in files)

            self._print_result(
                "PDF Generation",
                success and has_pdf,
                f"{len(files)} files in {duration:.2f}s - PDF: {has_pdf}",
            )

            if files:
                print(f"    Generated files:")
                for f in files[:5]:
                    print(f"      - {f}")

            self.results.append(
                {
                    "test": "pdf_generation",
                    "success": success,
                    "has_pdf": has_pdf,
                    "duration": duration,
                    "files": files,
                }
            )

            return result

        except Exception as e:
            self._print_result("PDF Generation", False, f"Error: {e}")
            return {"success": False, "error": str(e)}

    async def test_quality_fabric_integration(self):
        """Test 3: Quality-Fabric validation"""
        self._print_header("Test 3: Quality-Fabric Integration")

        # First, check if Quality-Fabric is running
        qf_available = await self._check_service("Quality-Fabric", self.quality_fabric_url)

        if not qf_available:
            self._print_result("Quality-Fabric", False, "Service not available")
            return {"success": False, "error": "Quality-Fabric not running"}

        start = time.time()

        try:
            config = EnhancedTeamConfig(
                enable_utcp=False,
                enable_rag=True,
                enable_mcp=True,
                project_name="test_quality_validated",
                selected_personas=["backend_developer", "qa_engineer"],
            )

            result = await execute_enhanced_lean_workflow_utcp(
                requirement="""Create a FastAPI application with:
- User registration endpoint
- Login endpoint with JWT authentication
- User profile endpoint (protected)
- Input validation using Pydantic
- Unit tests using pytest
                """,
                config=config,
            )

            duration = time.time() - start
            success = result.get("success", False)

            # Check quality validation results
            quality = result.get("quality_validation", {})
            quality_score = quality.get("quality_score", 0)
            test_results = quality.get("test_results", {})

            self._print_result(
                "Quality-Fabric Validation",
                success,
                f"Score: {quality_score}, Tests: {test_results}",
            )

            self.results.append(
                {
                    "test": "quality_fabric",
                    "success": success,
                    "duration": duration,
                    "quality_score": quality_score,
                    "test_results": test_results,
                }
            )

            return result

        except Exception as e:
            self._print_result("Quality-Fabric", False, f"Error: {e}")
            return {"success": False, "error": str(e)}

    async def test_rag_template_retrieval(self):
        """Test 4: RAG template retrieval and enhancement"""
        self._print_header("Test 4: RAG Template Retrieval")

        # Check Template Registry
        registry_available = await self._check_service(
            "Template Registry", self.template_registry_url
        )

        if not registry_available:
            self._print_result("RAG Templates", False, "Template Registry not available")
            return {"success": False, "error": "Template Registry not running"}

        start = time.time()

        try:
            config = EnhancedTeamConfig(
                enable_utcp=False,
                enable_rag=True,  # Enable RAG
                enable_mcp=True,
                project_name="test_rag_enhanced",
            )

            result = await execute_enhanced_lean_workflow_utcp(
                requirement="Create a REST API for task management with CRUD operations",
                config=config,
            )

            duration = time.time() - start
            success = result.get("success", False)

            # Check if templates were used (this info would be in logs or metadata)
            artifacts = result.get("artifacts", {})
            templates_used = artifacts.get("templates_retrieved", [])

            self._print_result(
                "RAG Template Retrieval",
                success,
                f"{len(templates_used)} templates in {duration:.2f}s",
            )

            self.results.append(
                {
                    "test": "rag_templates",
                    "success": success,
                    "duration": duration,
                    "templates_count": len(templates_used),
                }
            )

            return result

        except Exception as e:
            self._print_result("RAG Templates", False, f"Error: {e}")
            return {"success": False, "error": str(e)}

    async def test_multi_persona_workflow(self):
        """Test 5: Multi-persona collaboration"""
        self._print_header("Test 5: Multi-Persona Workflow")

        start = time.time()

        try:
            config = EnhancedTeamConfig(
                enable_utcp=False,
                enable_rag=True,
                enable_mcp=True,
                project_name="test_full_stack_app",
                selected_personas=[
                    "requirement_analyst",
                    "solution_architect",
                    "backend_developer",
                    "frontend_developer",
                    "qa_engineer",
                    "devops_engineer",
                ],
            )

            result = await execute_enhanced_lean_workflow_utcp(
                requirement="""Create a full-stack todo application:

Backend:
- FastAPI REST API
- SQLite database
- CRUD operations for todos
- API documentation

Frontend:
- Simple HTML/CSS/JavaScript UI
- List, add, complete, delete todos
- Responsive design

DevOps:
- Docker configuration
- docker-compose.yml for easy deployment
                """,
                config=config,
            )

            duration = time.time() - start
            success = result.get("success", False)
            team = result.get("team_members", [])
            files = result.get("files_generated", [])

            self._print_result(
                "Multi-Persona Workflow",
                success,
                f"{len(team)} personas, {len(files)} files in {duration:.2f}s",
            )

            print(f"    Team: {', '.join(team)}")

            self.results.append(
                {
                    "test": "multi_persona",
                    "success": success,
                    "duration": duration,
                    "team_size": len(team),
                    "files_count": len(files),
                }
            )

            return result

        except Exception as e:
            self._print_result("Multi-Persona", False, f"Error: {e}")
            return {"success": False, "error": str(e)}

    async def test_utcp_distributed_execution(self):
        """Test 6: UTCP distributed execution (if UTCP service available)"""
        self._print_header("Test 6: UTCP Distributed Execution")

        # Check if UTCP service is running
        utcp_available = await self._check_service(
            "UTCP Service", "http://localhost:8001", "/health"
        )

        if not utcp_available:
            self._print_result("UTCP Distributed", False, "UTCP service not available - skipping")
            return {"success": False, "error": "UTCP service not running", "skipped": True}

        start = time.time()

        try:
            utcp_config = UTCPToolConfig(enabled=True, fallback_to_local=True)

            config = EnhancedTeamConfig(
                enable_utcp=True,  # Enable UTCP
                enable_rag=True,
                enable_mcp=True,
                project_name="test_utcp_distributed",
                utcp_config=utcp_config,
            )

            result = await execute_enhanced_lean_workflow_utcp(
                requirement="Create a simple blog API with posts and comments", config=config
            )

            duration = time.time() - start
            success = result.get("success", False)
            execution_method = result.get("execution_method", "unknown")

            self._print_result(
                "UTCP Distributed", success, f"Method: {execution_method} in {duration:.2f}s"
            )

            self.results.append(
                {
                    "test": "utcp_distributed",
                    "success": success,
                    "duration": duration,
                    "execution_method": execution_method,
                }
            )

            return result

        except Exception as e:
            self._print_result("UTCP Distributed", False, f"Error: {e}")
            return {"success": False, "error": str(e)}

    async def test_template_extraction(self):
        """Test 7: Extract successful project as template"""
        self._print_header("Test 7: Template Extraction")

        start = time.time()

        try:
            config = EnhancedTeamConfig(
                enable_utcp=False,
                enable_rag=True,
                enable_mcp=True,
                project_name="test_template_extraction",
            )

            result = await execute_enhanced_lean_workflow_utcp(
                requirement="Create a reusable Python CLI template with Click library",
                config=config,
            )

            duration = time.time() - start
            success = result.get("success", False)

            # Check template extraction results
            template_info = result.get("template_extraction", {})
            templates_created = template_info.get("templates_created", 0)
            template_ids = template_info.get("template_ids", [])

            self._print_result(
                "Template Extraction",
                success,
                f"{templates_created} templates created in {duration:.2f}s",
            )

            if template_ids:
                print(f"    Template IDs: {', '.join(template_ids[:3])}")

            self.results.append(
                {
                    "test": "template_extraction",
                    "success": success,
                    "duration": duration,
                    "templates_created": templates_created,
                }
            )

            return result

        except Exception as e:
            self._print_result("Template Extraction", False, f"Error: {e}")
            return {"success": False, "error": str(e)}

    async def run_all_tests(self, tests: Optional[List[str]] = None):
        """Run all tests or specified tests"""
        print("\n" + "🧪" * 40)
        print("  MAESTRO UTCP Test Suite")
        print("🧪" * 40)

        # Check dependencies first
        await self.check_dependencies()

        # Define all tests
        all_tests = {
            "basic": self.test_basic_workflow,
            "pdf": self.test_pdf_generation,
            "quality": self.test_quality_fabric_integration,
            "rag": self.test_rag_template_retrieval,
            "multi_persona": self.test_multi_persona_workflow,
            "utcp": self.test_utcp_distributed_execution,
            "template": self.test_template_extraction,
        }

        # Run specified tests or all
        tests_to_run = tests if tests else list(all_tests.keys())

        for test_name in tests_to_run:
            if test_name in all_tests:
                await all_tests[test_name]()
            else:
                print(f"⚠️  Unknown test: {test_name}")

        # Print summary
        self._print_summary()

    def _print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("  TEST SUMMARY")
        print("=" * 80)

        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("success"))
        failed = total - passed

        print(f"\nTotal Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")

        if self.results:
            total_duration = sum(r.get("duration", 0) for r in self.results)
            print(f"⏱️  Total Time: {total_duration:.2f}s")
            print(f"⏱️  Average Time: {total_duration/total:.2f}s")

        print("\nDetailed Results:")
        for result in self.results:
            status = "✅" if result.get("success") else "❌"
            test = result.get("test", "unknown")
            duration = result.get("duration", 0)
            print(f"  {status} {test:20s} - {duration:.2f}s")

        # Save results to file
        output_file = f"test_results_{int(time.time())}.json"
        with open(output_file, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "summary": {
                        "total": total,
                        "passed": passed,
                        "failed": failed,
                        "duration": total_duration if self.results else 0,
                    },
                    "results": self.results,
                },
                f,
                indent=2,
            )

        print(f"\n📊 Results saved to: {output_file}")
        print("=" * 80)


async def main():
    """Main test runner"""
    import argparse

    parser = argparse.ArgumentParser(description="MAESTRO UTCP Test Wrapper")
    parser.add_argument(
        "--tests",
        nargs="+",
        choices=["basic", "pdf", "quality", "rag", "multi_persona", "utcp", "template", "all"],
        default=["all"],
        help="Tests to run",
    )

    args = parser.parse_args()

    wrapper = UTCPTestWrapper()

    tests_to_run = None if "all" in args.tests else args.tests

    await wrapper.run_all_tests(tests_to_run)


if __name__ == "__main__":
    asyncio.run(main())
