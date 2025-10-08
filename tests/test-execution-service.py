#!/usr/bin/env python3
"""
Unit Tests for MAESTRO Execution Service

This module provides comprehensive unit tests for:
- Development workflow execution
- Code generation and validation
- Test execution and quality checks
- Task orchestration and management
- Tool integration and automation
"""

import os

# Import the execution service components
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "services", "execution_service"))

from executor import app


class TestExecutionServiceAPI:
    """Test suite for Execution Service API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "execution-service"
        assert "timestamp" in data
        assert "version" in data
        assert "uptime" in data


class TestExecutionEngine:
    """Test suite for execution engine logic"""

    @pytest.fixture
    def execution_engine(self):
        """Create execution engine instance for testing"""
        from executor import ExecutionEngine

        return ExecutionEngine()

    def test_task_execution_simple(self, execution_engine):
        """Test simple task execution"""
        task = {
            "type": "code_generation",
            "language": "python",
            "template": "basic_function",
            "parameters": {
                "function_name": "add_numbers",
                "params": ["a", "b"],
                "return_type": "int",
            },
        }

        result = execution_engine.execute_task(task)
        assert result["status"] == "completed"
        assert "generated_code" in result

    def test_task_execution_with_validation(self, execution_engine):
        """Test task execution with code validation"""
        task = {
            "type": "code_generation",
            "language": "python",
            "template": "api_endpoint",
            "parameters": {
                "endpoint_name": "get_users",
                "method": "GET",
                "response_model": "UserList",
            },
            "validation": {
                "syntax_check": True,
                "type_check": True,
                "security_scan": True,
            },
        }

        result = execution_engine.execute_task(task)
        assert result["status"] in ["completed", "validation_passed"]
        assert "validation_results" in result

    def test_task_execution_error_handling(self, execution_engine):
        """Test task execution error handling"""
        invalid_task = {"type": "invalid_task_type", "parameters": {}}

        result = execution_engine.execute_task(invalid_task)
        assert result["status"] == "failed"
        assert "error" in result

    def test_workflow_execution(self, execution_engine):
        """Test workflow execution with multiple tasks"""
        workflow = {
            "name": "api_development_workflow",
            "tasks": [
                {
                    "id": "generate_model",
                    "type": "code_generation",
                    "template": "database_model",
                    "parameters": {"model_name": "User"},
                },
                {
                    "id": "generate_api",
                    "type": "code_generation",
                    "template": "crud_api",
                    "parameters": {"model": "User"},
                    "depends_on": ["generate_model"],
                },
            ],
        }

        result = execution_engine.execute_workflow(workflow)
        assert result["status"] in ["completed", "in_progress"]
        assert "task_results" in result


class TestCodeGeneration:
    """Test suite for code generation functionality"""

    @pytest.fixture
    def code_generator(self):
        """Create code generator instance"""
        from executor import CodeGenerator

        return CodeGenerator()

    def test_python_function_generation(self, code_generator):
        """Test Python function generation"""
        spec = {
            "language": "python",
            "type": "function",
            "name": "calculate_tax",
            "parameters": [
                {"name": "amount", "type": "float"},
                {"name": "rate", "type": "float"},
            ],
            "return_type": "float",
            "documentation": "Calculate tax amount based on rate",
        }

        code = code_generator.generate_code(spec)
        assert "def calculate_tax(" in code
        assert "amount" in code
        assert "rate" in code
        assert '"""Calculate tax amount based on rate"""' in code

    def test_api_endpoint_generation(self, code_generator):
        """Test API endpoint generation"""
        spec = {
            "language": "python",
            "framework": "fastapi",
            "type": "endpoint",
            "path": "/users/{user_id}",
            "method": "GET",
            "response_model": "User",
            "parameters": [{"name": "user_id", "type": "int", "location": "path"}],
        }

        code = code_generator.generate_code(spec)
        assert "@app.get(" in code
        assert "/users/{user_id}" in code
        assert "user_id: int" in code

    def test_database_model_generation(self, code_generator):
        """Test database model generation"""
        spec = {
            "language": "python",
            "framework": "sqlalchemy",
            "type": "model",
            "name": "Product",
            "fields": [
                {"name": "id", "type": "Integer", "primary_key": True},
                {"name": "name", "type": "String", "nullable": False},
                {"name": "price", "type": "Float"},
            ],
        }

        code = code_generator.generate_code(spec)
        assert "class Product(" in code
        assert "id = Column(Integer" in code
        assert "name = Column(String" in code
        assert "price = Column(Float" in code

    def test_test_case_generation(self, code_generator):
        """Test test case generation"""
        spec = {
            "language": "python",
            "framework": "pytest",
            "type": "test_case",
            "target_function": "calculate_tax",
            "test_cases": [
                {"input": {"amount": 100, "rate": 0.1}, "expected": 10.0},
                {"input": {"amount": 200, "rate": 0.05}, "expected": 10.0},
            ],
        }

        code = code_generator.generate_code(spec)
        assert "def test_calculate_tax" in code
        assert "assert" in code
        assert "100" in code and "0.1" in code


class TestValidationEngine:
    """Test suite for code validation functionality"""

    @pytest.fixture
    def validator(self):
        """Create validation engine instance"""
        from executor import ValidationEngine

        return ValidationEngine()

    def test_syntax_validation_valid_python(self, validator):
        """Test syntax validation with valid Python code"""
        valid_code = """
def hello_world():
    return "Hello, World!"
"""
        result = validator.validate_syntax(valid_code, "python")
        assert result["valid"] == True
        assert result["errors"] == []

    def test_syntax_validation_invalid_python(self, validator):
        """Test syntax validation with invalid Python code"""
        invalid_code = """
def hello_world(
    return "Hello, World!"
"""
        result = validator.validate_syntax(invalid_code, "python")
        assert result["valid"] == False
        assert len(result["errors"]) > 0

    def test_type_checking_python(self, validator):
        """Test type checking for Python code"""
        typed_code = """
def add_numbers(a: int, b: int) -> int:
    return a + b
"""
        result = validator.validate_types(typed_code, "python")
        assert "type_errors" in result

    def test_security_scanning(self, validator):
        """Test security scanning for potential vulnerabilities"""
        potentially_unsafe_code = """
import os
def delete_file(filename):
    os.system(f"rm {filename}")
"""
        result = validator.scan_security(potentially_unsafe_code, "python")
        assert "security_issues" in result

    def test_code_quality_analysis(self, validator):
        """Test code quality analysis"""
        code_to_analyze = """
def very_long_function_name_that_does_multiple_things(x, y, z):
    if x > 0:
        if y > 0:
            if z > 0:
                return x + y + z
            else:
                return x + y
        else:
            return x
    else:
        return 0
"""
        result = validator.analyze_quality(code_to_analyze, "python")
        assert "quality_score" in result
        assert "suggestions" in result


class TestTestRunner:
    """Test suite for test execution functionality"""

    @pytest.fixture
    def test_runner(self):
        """Create test runner instance"""
        from executor import TestRunner

        return TestRunner()

    def test_run_unit_tests(self, test_runner):
        """Test running unit tests"""
        test_config = {
            "framework": "pytest",
            "test_directory": "/tmp/test_project/tests",
            "test_files": ["test_models.py", "test_api.py"],
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "2 passed, 0 failed"

            result = test_runner.run_tests(test_config)
            assert result["status"] == "passed"
            assert "2 passed" in result["output"]

    def test_run_integration_tests(self, test_runner):
        """Test running integration tests"""
        test_config = {
            "framework": "pytest",
            "test_directory": "/tmp/test_project/integration_tests",
            "environment": "test",
            "setup_commands": ["docker-compose up -d"],
            "teardown_commands": ["docker-compose down"],
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "5 passed, 0 failed"

            result = test_runner.run_tests(test_config)
            assert result["status"] == "passed"

    def test_test_failure_handling(self, test_runner):
        """Test handling of test failures"""
        test_config = {
            "framework": "pytest",
            "test_directory": "/tmp/test_project/tests",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = "1 passed, 2 failed"
            mock_run.return_value.stderr = "FAILED test_models.py::test_user_creation"

            result = test_runner.run_tests(test_config)
            assert result["status"] == "failed"
            assert "2 failed" in result["output"]


class TestDocumentationGenerator:
    """Test suite for documentation generation"""

    @pytest.fixture
    def doc_generator(self):
        """Create documentation generator instance"""
        from executor import DocumentationGenerator

        return DocumentationGenerator()

    def test_api_documentation_generation(self, doc_generator):
        """Test API documentation generation"""
        api_spec = {
            "title": "User Management API",
            "version": "1.0.0",
            "endpoints": [
                {
                    "path": "/users",
                    "method": "GET",
                    "description": "Get all users",
                    "responses": {"200": {"description": "List of users"}},
                }
            ],
        }

        doc = doc_generator.generate_api_docs(api_spec)
        assert "User Management API" in doc
        assert "/users" in doc
        assert "GET" in doc

    def test_code_documentation_generation(self, doc_generator):
        """Test code documentation generation"""
        code = """
def calculate_interest(principal, rate, time):
    \"\"\"Calculate compound interest.\"\"\"
    return principal * (1 + rate) ** time

class BankAccount:
    \"\"\"Represents a bank account.\"\"\"
    def __init__(self, balance):
        self.balance = balance
"""

        doc = doc_generator.generate_code_docs(code, "python")
        assert "calculate_interest" in doc
        assert "BankAccount" in doc
        assert "compound interest" in doc

    def test_readme_generation(self, doc_generator):
        """Test README file generation"""
        project_info = {
            "name": "My API Project",
            "description": "A REST API for user management",
            "installation": ["pip install -r requirements.txt"],
            "usage": ["python app.py"],
            "features": ["User authentication", "CRUD operations"],
        }

        readme = doc_generator.generate_readme(project_info)
        assert "# My API Project" in readme
        assert "## Installation" in readme
        assert "pip install" in readme


class TestDeploymentAutomation:
    """Test suite for deployment automation"""

    @pytest.fixture
    def deployment_manager(self):
        """Create deployment manager instance"""
        from executor import DeploymentManager

        return DeploymentManager()

    def test_docker_deployment(self, deployment_manager):
        """Test Docker deployment configuration"""
        deployment_config = {
            "type": "docker",
            "image": "my-app:latest",
            "ports": ["8000:8000"],
            "environment": {"ENV": "production"},
        }

        result = deployment_manager.deploy(deployment_config)
        assert result["status"] in ["deployed", "in_progress"]

    def test_kubernetes_deployment(self, deployment_manager):
        """Test Kubernetes deployment configuration"""
        deployment_config = {
            "type": "kubernetes",
            "namespace": "production",
            "replicas": 3,
            "image": "my-app:v1.0.0",
            "resources": {
                "requests": {"cpu": "100m", "memory": "128Mi"},
                "limits": {"cpu": "500m", "memory": "512Mi"},
            },
        }

        result = deployment_manager.deploy(deployment_config)
        assert result["status"] in ["deployed", "in_progress"]

    def test_deployment_rollback(self, deployment_manager):
        """Test deployment rollback functionality"""
        rollback_config = {
            "deployment_id": "app-deployment-123",
            "target_version": "v0.9.0",
        }

        result = deployment_manager.rollback(rollback_config)
        assert result["status"] in ["rolled_back", "in_progress"]


class TestMessageHandling:
    """Test suite for message queue handling"""

    @pytest.fixture
    def message_handler(self):
        """Create message handler instance"""
        from executor import MessageHandler

        return MessageHandler()

    def test_task_message_processing(self, message_handler):
        """Test processing task messages from queue"""
        task_message = {
            "type": "execute_task",
            "task_id": "task-123",
            "payload": {
                "type": "code_generation",
                "parameters": {"template": "api_endpoint"},
            },
        }

        with patch.object(message_handler, "execute_task") as mock_execute:
            mock_execute.return_value = {"status": "completed"}

            result = message_handler.process_message(task_message)
            assert result["status"] == "completed"
            mock_execute.assert_called_once()

    def test_workflow_message_processing(self, message_handler):
        """Test processing workflow messages"""
        workflow_message = {
            "type": "execute_workflow",
            "workflow_id": "workflow-456",
            "payload": {
                "name": "api_development",
                "tasks": [{"type": "code_generation"}],
            },
        }

        with patch.object(message_handler, "execute_workflow") as mock_execute:
            mock_execute.return_value = {"status": "in_progress"}

            result = message_handler.process_message(workflow_message)
            assert result["status"] == "in_progress"

    def test_invalid_message_handling(self, message_handler):
        """Test handling of invalid messages"""
        invalid_message = {"type": "unknown_type", "payload": {}}

        result = message_handler.process_message(invalid_message)
        assert result["status"] == "error"
        assert "error" in result


class TestErrorHandling:
    """Test suite for error handling and recovery"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_service_error_recovery(self, client):
        """Test service error recovery mechanisms"""
        # This would test how the service handles and recovers from errors
        pass

    def test_task_timeout_handling(self):
        """Test task timeout handling"""
        from executor import ExecutionEngine

        engine = ExecutionEngine()
        long_running_task = {
            "type": "code_generation",
            "timeout": 1,  # 1 second timeout
            "parameters": {"complex_operation": True},
        }

        with patch("time.sleep", side_effect=lambda x: None if x < 2 else Exception("Timeout")):
            result = engine.execute_task(long_running_task)
            assert result["status"] in ["timeout", "failed"]

    def test_resource_exhaustion_handling(self):
        """Test handling of resource exhaustion"""
        from executor import ExecutionEngine

        engine = ExecutionEngine()
        resource_intensive_task = {
            "type": "code_generation",
            "parameters": {"large_codebase": True},
        }

        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value.percent = 95  # 95% memory usage

            result = engine.execute_task(resource_intensive_task)
            # Should handle high memory usage gracefully


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
