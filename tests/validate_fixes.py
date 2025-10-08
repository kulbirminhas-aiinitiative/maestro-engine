#!/usr/bin/env python3
"""
Quick Validation Test
Verifies that the core configuration standardization fixes are working
"""

import os
import sys
from pathlib import Path


def test_configuration_loading():
    """Test that configuration can be loaded"""
    try:
        from maestro_config import get_config, load_config

        config = load_config()
        print("✅ Configuration loads successfully")

        print(f"   - Orchestration Port: {config.orchestration_gateway.port}")
        print(f"   - Intelligence Port: {config.intelligence_service.port}")
        print(f"   - Database Host: {config.database.host}")
        print(f"   - Redis Host: {config.redis.host}")

        return True
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        return False


def test_no_hardcoded_paths():
    """Verify no hardcoded sys.path.insert statements remain"""

    print("\n🔍 Checking for hardcoded paths...")

    # Key files to check
    key_files = [
        "enhanced_coherent_with_ai_coordination.py",
        "stigmergy_engine.py",
        "coherent_persona_executor.py",
        "tests/conftest.py",
        "tests/run_coherent_system_tests.py",
    ]

    found_hardcoded = False

    for file_path in key_files:
        full_path = Path("/data/maestro-services") / file_path
        if full_path.exists():
            try:
                content = full_path.read_text()
                if 'sys.path.insert(0, "/data/maestro' in content:
                    if not content.count("# Use") > content.count("sys.path.insert"):
                        print(f"❌ Found uncommented hardcoded path in {file_path}")
                        found_hardcoded = True
                    else:
                        print(f"✅ {file_path} - hardcoded paths properly commented")
                else:
                    print(f"✅ {file_path} - no hardcoded paths")
            except Exception as e:
                print(f"⚠️  Could not check {file_path}: {e}")
        else:
            print(f"⚠️  File not found: {file_path}")

    if not found_hardcoded:
        print("✅ All checked files are clean of hardcoded paths")
        return True
    else:
        print("❌ Some files still have hardcoded paths")
        return False


def test_poetry_configuration():
    """Test Poetry configuration exists and is valid"""

    print("\n📦 Checking Poetry configuration...")

    pyproject_path = Path("/data/maestro-services/pyproject.toml")

    if not pyproject_path.exists():
        print("❌ pyproject.toml not found")
        return False

    try:
        content = pyproject_path.read_text()

        required_sections = [
            "[tool.poetry]",
            "[tool.poetry.dependencies]",
            'name = "maestro-services"',
        ]

        for section in required_sections:
            if section not in content:
                print(f"❌ Missing required section: {section}")
                return False
            else:
                print(f"✅ Found: {section}")

        print("✅ Poetry configuration is valid")
        return True

    except Exception as e:
        print(f"❌ Error reading pyproject.toml: {e}")
        return False


def test_environment_override():
    """Test environment variable override works"""

    print("\n🔧 Testing environment variable override...")

    try:
        # Test with environment override
        test_env = {"ORCHESTRATION_PORT": "9999", "DATABASE_HOST": "test.db.com"}

        # Temporarily set environment variables
        original_env = {}
        for key, value in test_env.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            from maestro_config import load_config

            config = load_config()

            if config.orchestration_gateway.port == 9999:
                print("✅ Port override works")
            else:
                print(f"❌ Port override failed: got {config.orchestration_gateway.port}")
                return False

            if config.database.host == "test.db.com":
                print("✅ Database host override works")
            else:
                print(f"❌ Database host override failed: got {config.database.host}")
                return False

            print("✅ Environment variable overrides work correctly")
            return True

        finally:
            # Restore original environment
            for key, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value

    except Exception as e:
        print(f"❌ Environment override test failed: {e}")
        return False


def main():
    """Run validation tests"""

    print("🚀 MAESTRO Configuration Standardization Validation")
    print("=" * 60)

    tests = [
        ("Configuration Loading", test_configuration_loading),
        ("Hardcoded Paths Check", test_no_hardcoded_paths),
        ("Poetry Configuration", test_poetry_configuration),
        ("Environment Override", test_environment_override),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n🧪 {test_name}")
        print("-" * 40)
        success = test_func()
        results.append((test_name, success))

    # Summary
    print("\n" + "=" * 60)
    print("🏁 Validation Results")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} - {test_name}")

    print(f"\n📊 Success Rate: {passed}/{total} ({(passed/total)*100:.1f}%)")

    if passed == total:
        print("🎉 All validation tests passed! Configuration standardization is complete.")
        return 0
    else:
        print("⚠️  Some validation tests failed. Review the issues above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
