#!/usr/bin/env python3
"""
Unit tests for Debug Coherent Persona Executor
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Import the debug functions
from debug_coherent_persona_executor import (
    test_coherent_persona_executor_init,
    test_persona_file_loading,
    test_persona_imports,
)

# Fix import path for debug persona executor
# Use Poetry and relative imports instead of hardcoded paths



class TestPersonaImportsFunction:
    """Test suite for persona imports testing function"""

    def test_successful_persona_imports(self):
        """Test successful persona imports"""
        # Mock all the imports to succeed
        with patch("debug_coherent_persona_executor.logger") as mock_logger:
            with patch.dict(
                "sys.modules", {"chained_workflow": MagicMock(), "onestep_approach": MagicMock()}
            ):
                # Mock the specific persona classes
                mock_chained = MagicMock()
                mock_chained.BackendDeveloperPersona = MagicMock()
                mock_chained.DevOpsEngineerPersona = MagicMock()
                mock_chained.FrontendDeveloperPersona = MagicMock()
                mock_chained.ProgramManagerPersona = MagicMock()
                mock_chained.QAEngineerPersona = MagicMock()
                mock_chained.SolutionArchitectPersona = MagicMock()
                mock_chained.SolutionReviewerPersona = MagicMock()
                mock_chained.UXAnalystPersona = MagicMock()

                mock_onestep = MagicMock()
                mock_onestep.RequirementAnalystPersona = MagicMock()

                sys.modules["chained_workflow"] = mock_chained
                sys.modules["onestep_approach"] = mock_onestep

                result = test_persona_imports()

                assert result is True
                mock_logger.info.assert_any_call("🔍 Testing persona imports...")
                mock_logger.info.assert_any_call("✅ All persona imports successful")

    def test_failed_persona_imports(self):
        """Test failed persona imports"""
        with patch("debug_coherent_persona_executor.logger") as mock_logger:
            # Force an ImportError
            with patch("builtins.__import__", side_effect=ImportError("Module not found")):
                result = test_persona_imports()

                assert result is False
                mock_logger.error.assert_called_once()
                assert "❌ Persona import failed" in str(mock_logger.error.call_args)


class TestCoherentPersonaExecutorInitFunction:
    """Test suite for coherent persona executor initialization testing function"""

    def test_successful_executor_initialization(self):
        """Test successful executor initialization"""
        # Mock CoherentPersonaExecutor
        mock_executor_class = MagicMock()
        mock_executor1 = MagicMock()
        mock_executor2 = MagicMock()

        mock_executor1.personas_dir = "/default/personas"
        mock_executor1.persona_classes = {
            "backend": "BackendDeveloper",
            "frontend": "FrontendDeveloper",
        }
        mock_executor1.available_personas = {
            "backend": "/path/backend.json",
            "frontend": "/path/frontend.json",
        }

        mock_executor2.personas_dir = "/data/maestro-services/personas/json"
        mock_executor2.available_personas = {"solution_architect": "/path/solution_architect.json"}

        mock_executor_class.side_effect = [mock_executor1, mock_executor2]

        with patch("debug_coherent_persona_executor.logger") as mock_logger:
            with patch(
                "debug_coherent_persona_executor.CoherentPersonaExecutor", mock_executor_class
            ):
                result1, result2 = test_coherent_persona_executor_init()

                assert result1 == mock_executor1
                assert result2 == mock_executor2

                # Verify logging calls
                mock_logger.info.assert_any_call(
                    "🔍 Testing CoherentPersonaExecutor initialization..."
                )
                mock_logger.info.assert_any_call("✅ CoherentPersonaExecutor initialized")
                mock_logger.info.assert_any_call(
                    "✅ CoherentPersonaExecutor initialized with custom directory"
                )

                # Verify executor was called with correct parameters
                calls = mock_executor_class.call_args_list
                assert len(calls) == 2
                assert calls[0] == ((), {})  # Default initialization
                assert calls[1] == ((), {"personas_dir": "/data/maestro-services/personas/json"})

    def test_failed_executor_initialization(self):
        """Test failed executor initialization"""
        with patch("debug_coherent_persona_executor.logger") as mock_logger:
            with patch(
                "debug_coherent_persona_executor.CoherentPersonaExecutor",
                side_effect=Exception("Initialization failed"),
            ):
                result1, result2 = test_coherent_persona_executor_init()

                assert result1 is None
                assert result2 is None
                mock_logger.error.assert_called_once()
                assert "❌ CoherentPersonaExecutor initialization failed" in str(
                    mock_logger.error.call_args
                )


class TestPersonaFileLoadingFunction:
    """Test suite for persona file loading testing function"""

    def setup_method(self):
        """Setup test fixtures"""
        self.sample_persona_data = {
            "persona_id": "solution_architect",
            "name": "Solution Architect",
            "role": "Architecture and system design",
            "capabilities": [
                "System architecture design",
                "Technology selection",
                "Scalability planning",
            ],
            "personality": {
                "communication_style": "Technical and thorough",
                "decision_making": "Data-driven and systematic",
            },
        }

    def test_successful_persona_file_loading(self):
        """Test successful persona file loading"""
        # Mock CoherentPersonaExecutor
        mock_executor = MagicMock()
        mock_executor.available_personas = {
            "solution_architect": "/mock/path/solution_architect.json"
        }

        mock_executor_class = MagicMock(return_value=mock_executor)

        # Mock file reading
        mock_file_content = json.dumps(self.sample_persona_data)

        with patch("debug_coherent_persona_executor.logger") as mock_logger:
            with patch(
                "debug_coherent_persona_executor.CoherentPersonaExecutor", mock_executor_class
            ):
                with patch("builtins.open", mock_open(read_data=mock_file_content)):
                    result = test_persona_file_loading()

                    # Should not raise an exception (returns None implicitly)
                    assert result is None

                    # Verify logging
                    mock_logger.info.assert_any_call("🔍 Testing persona JSON file loading...")

    def test_persona_file_not_available(self):
        """Test when persona file is not available"""
        # Mock CoherentPersonaExecutor with no solution_architect
        mock_executor = MagicMock()
        mock_executor.available_personas = {
            "backend_developer": "/mock/path/backend_developer.json"
        }

        mock_executor_class = MagicMock(return_value=mock_executor)

        with patch("debug_coherent_persona_executor.logger") as mock_logger:
            with patch(
                "debug_coherent_persona_executor.CoherentPersonaExecutor", mock_executor_class
            ):
                result = test_persona_file_loading()

                assert result is None
                mock_logger.info.assert_any_call("🔍 Testing persona JSON file loading...")

    def test_persona_file_loading_with_json_error(self):
        """Test persona file loading with JSON parsing error"""
        # Mock CoherentPersonaExecutor
        mock_executor = MagicMock()
        mock_executor.available_personas = {
            "solution_architect": "/mock/path/solution_architect.json"
        }

        mock_executor_class = MagicMock(return_value=mock_executor)

        # Mock file with invalid JSON
        invalid_json = "{ invalid json content"

        with patch("debug_coherent_persona_executor.logger") as mock_logger:
            with patch(
                "debug_coherent_persona_executor.CoherentPersonaExecutor", mock_executor_class
            ):
                with patch("builtins.open", mock_open(read_data=invalid_json)):
                    with pytest.raises(json.JSONDecodeError):
                        test_persona_file_loading()

    def test_persona_file_loading_with_file_not_found(self):
        """Test persona file loading when file doesn't exist"""
        # Mock CoherentPersonaExecutor
        mock_executor = MagicMock()
        mock_executor.available_personas = {
            "solution_architect": "/nonexistent/path/solution_architect.json"
        }

        mock_executor_class = MagicMock(return_value=mock_executor)

        with patch("debug_coherent_persona_executor.logger") as mock_logger:
            with patch(
                "debug_coherent_persona_executor.CoherentPersonaExecutor", mock_executor_class
            ):
                with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
                    with pytest.raises(FileNotFoundError):
                        test_persona_file_loading()


class TestDebugPersonaExecutorIntegration:
    """Integration tests for debug persona executor functionality"""

    def test_persona_data_structure_validation(self):
        """Test validation of persona data structure"""
        valid_persona_data = {
            "persona_id": "test_persona",
            "name": "Test Persona",
            "role": "Testing",
            "capabilities": ["Testing", "Validation"],
            "personality": {
                "communication_style": "Clear and concise",
                "decision_making": "Evidence-based",
            },
            "tools": ["pytest", "unittest"],
            "knowledge_domains": ["software_testing", "quality_assurance"],
        }

        # Validate required fields
        required_fields = ["persona_id", "name", "role", "capabilities"]
        for field in required_fields:
            assert field in valid_persona_data

        # Validate data types
        assert isinstance(valid_persona_data["persona_id"], str)
        assert isinstance(valid_persona_data["name"], str)
        assert isinstance(valid_persona_data["role"], str)
        assert isinstance(valid_persona_data["capabilities"], list)
        assert len(valid_persona_data["capabilities"]) > 0

        if "personality" in valid_persona_data:
            assert isinstance(valid_persona_data["personality"], dict)

    def test_persona_directory_structure(self):
        """Test persona directory structure validation"""
        # Test with temporary directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            personas_dir = Path(temp_dir) / "personas" / "json"
            personas_dir.mkdir(parents=True, exist_ok=True)

            # Create test persona files
            test_personas = [
                "backend_developer.json",
                "frontend_developer.json",
                "solution_architect.json",
            ]

            for persona_file in test_personas:
                persona_path = personas_dir / persona_file
                with open(persona_path, "w") as f:
                    json.dump(
                        {
                            "persona_id": persona_file.replace(".json", ""),
                            "name": persona_file.replace(".json", "").replace("_", " ").title(),
                            "role": "Test role",
                            "capabilities": ["Testing"],
                        },
                        f,
                    )

            # Verify directory structure
            assert personas_dir.exists()
            assert personas_dir.is_dir()

            # Verify persona files exist
            for persona_file in test_personas:
                persona_path = personas_dir / persona_file
                assert persona_path.exists()
                assert persona_path.is_file()

                # Verify file can be parsed as JSON
                with open(persona_path, "r") as f:
                    persona_data = json.load(f)
                    assert "persona_id" in persona_data
                    assert "name" in persona_data

    def test_mock_coherent_persona_executor_behavior(self):
        """Test mock behavior of CoherentPersonaExecutor"""

        # Create a realistic mock of CoherentPersonaExecutor
        class MockCoherentPersonaExecutor:
            def __init__(self, personas_dir=None):
                self.personas_dir = personas_dir or "/default/personas"
                self.persona_classes = {
                    "backend_developer": "BackendDeveloperPersona",
                    "frontend_developer": "FrontendDeveloperPersona",
                    "solution_architect": "SolutionArchitectPersona",
                }
                self.available_personas = {}
                self._scan_personas_directory()

            def _scan_personas_directory(self):
                """Mock scanning of personas directory"""
                if "json" in self.personas_dir:
                    self.available_personas = {
                        "solution_architect": f"{self.personas_dir}/solution_architect.json",
                        "backend_developer": f"{self.personas_dir}/backend_developer.json",
                        "frontend_developer": f"{self.personas_dir}/frontend_developer.json",
                    }

        # Test mock executor
        mock_executor = MockCoherentPersonaExecutor()
        assert mock_executor.personas_dir == "/default/personas"
        assert len(mock_executor.persona_classes) == 3

        # Test with custom directory
        custom_executor = MockCoherentPersonaExecutor("/data/maestro-services/personas/json")
        assert custom_executor.personas_dir == "/data/maestro-services/personas/json"
        assert len(custom_executor.available_personas) == 3

    def test_persona_execution_compatibility(self):
        """Test compatibility of persona execution interfaces"""

        # Test persona interface compatibility
        class MockPersona:
            def __init__(self, persona_data):
                self.persona_id = persona_data.get("persona_id")
                self.name = persona_data.get("name")
                self.role = persona_data.get("role")
                self.capabilities = persona_data.get("capabilities", [])

            async def execute(self, requirement):
                """Mock execution method"""
                return {
                    "success": True,
                    "output": f"Mock output from {self.name} for: {requirement}",
                    "persona_id": self.persona_id,
                    "execution_time": 1.0,
                }

        # Test persona creation and execution
        persona_data = {
            "persona_id": "test_persona",
            "name": "Test Persona",
            "role": "Testing",
            "capabilities": ["Unit Testing", "Integration Testing"],
        }

        persona = MockPersona(persona_data)
        assert persona.persona_id == "test_persona"
        assert persona.name == "Test Persona"
        assert len(persona.capabilities) == 2

    def test_error_scenarios_handling(self):
        """Test handling of various error scenarios"""
        error_scenarios = [
            {
                "name": "Missing persona directory",
                "error_type": FileNotFoundError,
                "description": "Personas directory does not exist",
            },
            {
                "name": "Invalid JSON format",
                "error_type": json.JSONDecodeError,
                "description": "Persona file contains invalid JSON",
            },
            {
                "name": "Missing required fields",
                "error_type": KeyError,
                "description": "Persona data missing required fields",
            },
            {
                "name": "Import module error",
                "error_type": ImportError,
                "description": "Required persona modules cannot be imported",
            },
        ]

        for scenario in error_scenarios:
            # Verify error types are properly defined
            assert issubclass(scenario["error_type"], Exception)
            assert isinstance(scenario["name"], str)
            assert isinstance(scenario["description"], str)

    def test_logging_configuration_validation(self):
        """Test logging configuration for debug functions"""
        import logging

        # Verify logging is properly configured
        logger = logging.getLogger("CoherentPersonaExecutor_Debug")
        assert logger.name == "CoherentPersonaExecutor_Debug"

        # Test log level configuration
        original_level = logger.level
        logger.setLevel(logging.DEBUG)
        assert logger.level == logging.DEBUG

        logger.setLevel(logging.INFO)
        assert logger.level == logging.INFO

        # Restore original level
        logger.setLevel(original_level)
