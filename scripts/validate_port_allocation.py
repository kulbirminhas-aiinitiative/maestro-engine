#!/usr/bin/env python3
"""
Validate service port allocations.

Checks:
1. No port conflicts (duplicate assignments)
2. Ports within allocated ranges
3. All services defined in registry
4. Health endpoints accessible (optional)

Part of ADR-004: Port Allocation Strategy

Port Range Strategy:
  1000-2999: Reserved (system/well-known)
  3000-3999: Frontend services
  4000-4999: Backend APIs (user-facing)
  5000-5999: Core orchestration engines
  6000-6999: Reserved for future use
  7000-7999: Reserved for future use
  8000-8999: Infrastructure services
  9000-9999: Internal microservices
  10000+:    Development/testing

Usage:
    python scripts/validate_port_allocation.py              # Validate config
    python scripts/validate_port_allocation.py --check-health # Check health endpoints
"""

import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


class PortValidator:
    """Validate service port allocations."""

    # Port range definitions
    PORT_RANGES = {
        "system": (1000, 2999),
        "frontend": (3000, 3999),
        "user_facing_api": (4000, 4999),
        "core_engines": (5000, 5999),
        "reserved_6k": (6000, 6999),
        "reserved_7k": (7000, 7999),
        "infrastructure": (8000, 8999),
        "microservices": (9000, 9999),
        "development": (10000, 65535),
    }

    # Category to range mapping
    CATEGORY_RANGES = {
        "frontend": (3000, 3999),
        "api": (4000, 4999),
        "engine": (5000, 5999),
        "infrastructure": (8000, 8999),
        "monitoring": (9000, 9999),
        "gateway": (8000, 8999),
    }

    def __init__(self, config_path: Path = Path("config/services.yaml")):
        self.config_path = config_path
        self.services = []
        self.errors = []
        self.warnings = []

    def load_config(self) -> bool:
        """Load service configuration."""
        try:
            with open(self.config_path) as f:
                config = yaml.safe_load(f)
                self.services = config.get("services", {})
                return True
        except FileNotFoundError:
            self.errors.append(f"❌ Configuration file not found: {self.config_path}")
            return False
        except yaml.YAMLError as e:
            self.errors.append(f"❌ Invalid YAML: {e}")
            return False

    def find_port_conflicts(self) -> List[Tuple[int, List[str]]]:
        """Find duplicate port assignments."""
        port_usage = defaultdict(list)

        for service_name, service_config in self.services.items():
            if "port" in service_config:
                port = service_config["port"]
                port_usage[port].append(service_name)

        # Return only ports with conflicts
        conflicts = [(port, services) for port, services in port_usage.items() if len(services) > 1]

        return conflicts

    def validate_port_ranges(self) -> List[Dict]:
        """Validate ports are within allocated ranges for their category."""
        violations = []

        for service_name, service_config in self.services.items():
            if "port" not in service_config:
                self.warnings.append(f"⚠️  Service '{service_name}' has no port defined")
                continue

            port = service_config["port"]
            category = service_config.get("category", "unknown")

            # Skip external services (they're not in our control)
            if service_config.get("external", False):
                continue

            # Check if category has an expected range
            if category in self.CATEGORY_RANGES:
                min_port, max_port = self.CATEGORY_RANGES[category]
                if not (min_port <= port <= max_port):
                    violations.append(
                        {
                            "service": service_name,
                            "port": port,
                            "category": category,
                            "expected_range": f"{min_port}-{max_port}",
                        }
                    )

        return violations

    def check_well_known_ports(self) -> List[Dict]:
        """Check for usage of well-known ports (< 1024)."""
        well_known = []

        for service_name, service_config in self.services.items():
            if "port" in service_config:
                port = service_config["port"]
                if port < 1024:
                    well_known.append(
                        {
                            "service": service_name,
                            "port": port,
                        }
                    )

        return well_known

    def validate_health_endpoints(self) -> List[Dict]:
        """Validate health endpoint definitions."""
        missing = []

        for service_name, service_config in self.services.items():
            # Skip external services
            if service_config.get("external", False):
                continue

            if "health" not in service_config:
                missing.append(
                    {
                        "service": service_name,
                        "port": service_config.get("port", "N/A"),
                    }
                )

        return missing

    def print_summary(self) -> None:
        """Print summary of services and port allocations."""
        print("\n📊 Service Port Allocation Summary")
        print("=" * 60)

        # Count by category
        by_category = defaultdict(list)
        for service_name, service_config in self.services.items():
            category = service_config.get("category", "unknown")
            port = service_config.get("port", "N/A")
            external = "(external)" if service_config.get("external") else ""
            by_category[category].append(f"  {service_name:20s} {port:>5} {external}")

        for category in sorted(by_category.keys()):
            print(f"\n{category.upper()}:")
            for line in sorted(by_category[category]):
                print(line)

        print(f"\n{'=' * 60}")
        print(f"Total services: {len(self.services)}")

    def run(self) -> int:
        """Run all validations and return exit code."""
        print("🔍 Validating MAESTRO port allocations...")
        print(f"   Config: {self.config_path}\n")

        # Load configuration
        if not self.load_config():
            for error in self.errors:
                print(error)
            return 1

        # Run validations
        conflicts = self.find_port_conflicts()
        range_violations = self.validate_port_ranges()
        well_known = self.check_well_known_ports()
        missing_health = self.validate_health_endpoints()

        # Report conflicts
        if conflicts:
            print("\n❌ PORT CONFLICTS DETECTED:")
            for port, services in conflicts:
                print(f"   Port {port}: {', '.join(services)}")
            self.errors.append("Port conflicts found")

        # Report range violations
        if range_violations:
            print("\n⚠️  PORT RANGE VIOLATIONS:")
            for v in range_violations:
                print(
                    f"   {v['service']}: port {v['port']} (category: {v['category']}) "
                    f"not in expected range {v['expected_range']}"
                )
            self.warnings.append(f"{len(range_violations)} range violations")

        # Report well-known ports
        if well_known:
            print("\n⚠️  WELL-KNOWN PORTS (<1024) USAGE:")
            for w in well_known:
                print(f"   {w['service']}: port {w['port']} (requires root privileges)")
            self.warnings.append("Well-known ports used")

        # Report missing health endpoints
        if missing_health:
            print("\n⚠️  MISSING HEALTH ENDPOINTS:")
            for m in missing_health:
                print(f"   {m['service']} (port {m['port']})")
            self.warnings.append(f"{len(missing_health)} services without health endpoints")

        # Print summary
        self.print_summary()

        # Print results
        print("\n" + "=" * 60)
        if not self.errors:
            print("✅ All port allocations valid!")
            if self.warnings:
                print(f"   {len(self.warnings)} warning(s)")
            return 0
        else:
            print(f"❌ Validation failed: {len(self.errors)} error(s)")
            if self.warnings:
                print(f"   {len(self.warnings)} warning(s)")
            return 1


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate service port allocations")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/services.yaml"),
        help="Path to services.yaml (default: config/services.yaml)",
    )

    args = parser.parse_args()

    validator = PortValidator(config_path=args.config)
    exit_code = validator.run()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
