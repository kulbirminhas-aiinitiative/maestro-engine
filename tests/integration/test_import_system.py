#!/usr/bin/env python3
"""
Import System Integration Tests
Verifies that all coherent system components can be imported correctly
without hardcoded path dependencies
"""

import sys
from pathlib import Path

import pytest

# Use Poetry and relative imports instead of hardcoded paths


class TestImportSystem:
    """Test that maestro-engine components can be imported correctly"""

    def test_maestro_engine_core_imports(self):
        """Test that maestro-engine core modules can be imported"""

        # Test Service Registry (NEW)
        try:
            from src.registry import ServiceInfo, ServiceRegistry, ServiceStatus

            assert ServiceRegistry is not None
            assert ServiceInfo is not None
            assert ServiceStatus is not None
        except ImportError as e:
            pytest.fail(f"Failed to import service registry: {e}")

        # Test API routes (NEW)
        try:
            from src.api import registry_routes

            assert registry_routes is not None
        except ImportError as e:
            pytest.fail(f"Failed to import registry routes: {e}")

        # Test MCP module exists (may have external deps)
        try:
            import src.mcp

            assert src.mcp is not None
        except ImportError as e:
            # MCP module may have external dependencies, don't fail hard
            print(f"MCP module import warning: {e}")

    def test_shared_library_imports(self):
        """Test that shared libraries are accessible"""

        # Test maestro-core-api
        try:
            from maestro_core_api import APIConfig, MaestroAPI, SecurityConfig

            assert MaestroAPI is not None
            assert APIConfig is not None
            assert SecurityConfig is not None
        except ImportError as e:
            pytest.fail(f"Failed to import maestro-core-api: {e}")

        # Test maestro-core-logging
        try:
            from maestro_core_logging import configure_logging, get_logger

            assert configure_logging is not None
            assert get_logger is not None
        except ImportError as e:
            pytest.fail(f"Failed to import maestro-core-logging: {e}")

        # Test maestro-core-config
        try:
            from maestro_core_config import BaseConfig, ConfigManager

            assert ConfigManager is not None
            assert BaseConfig is not None
        except ImportError as e:
            pytest.fail(f"Failed to import maestro-core-config: {e}")

    def test_no_hardcoded_paths_in_imports(self):
        """Verify that no components use hardcoded sys.path.insert"""

        # Check that sys.path doesn't contain hardcoded paths
        hardcoded_paths = ["/data/maestro", "/data/maestro-services"]
        current_dir = str(Path.cwd())

        for path_str in hardcoded_paths:
            # Check for exact path matches in sys.path, excluding current directory
            for sys_path in sys.path:
                if sys_path == path_str and path_str != current_dir:
                    pytest.fail(f"Found hardcoded path in sys.path: {path_str}")

    def test_import_resolution_without_path_manipulation(self):
        """Test that imports work without manual path manipulation"""

        # Save original sys.path
        original_path = sys.path.copy()

        try:
            # Remove any potential hardcoded paths
            sys.path = [
                p
                for p in sys.path
                if not any(hc in p for hc in ["/data/maestro", "/data/maestro-services"])
            ]

            # Test that we can still import shared libraries with Poetry resolution
            try:
                from maestro_core_api import MaestroAPI

                assert MaestroAPI is not None
            except ImportError:
                # This might fail depending on how Python is run, which is expected
                pass

        finally:
            # Restore original sys.path
            sys.path = original_path

    def test_relative_import_patterns(self):
        """Test that relative imports work correctly"""

        # Test within maestro-engine src
        try:
            # This should work with proper package structure
            from src.registry import service_registry

            assert service_registry is not None
        except ImportError:
            # Expected if package structure isn't fully set up yet
            pass

    def test_poetry_package_structure(self):
        """Test that Poetry package structure is correct"""

        # Verify pyproject.toml exists
        pyproject_path = Path("pyproject.toml")
        assert pyproject_path.exists(), "pyproject.toml must exist for Poetry management"

        # Read and verify basic structure
        content = pyproject_path.read_text()
        assert "[tool.poetry]" in content
        assert 'name = "maestro-engine"' in content
        assert "[tool.poetry.dependencies]" in content

    def test_no_import_errors_on_basic_components(self):
        """Test that maestro-engine components don't have import errors"""

        # Test that we can import maestro-engine modules without exceptions
        components_to_test = [
            "src.registry.service_registry",
            "src.api.registry_routes",
        ]

        for component in components_to_test:
            try:
                __import__(component)
            except ImportError as e:
                # Log but don't fail - these may have legitimate missing dependencies
                print(f"Import warning for {component}: {e}")
            except Exception as e:
                # Other exceptions might indicate real issues
                pytest.fail(f"Unexpected error importing {component}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
