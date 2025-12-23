# Services package for MAESTRO Engine
# MD-3203: Added __init__.py to make services a proper Python package

"""
MAESTRO Engine Services

This package contains service modules for the MAESTRO Engine including:
- template_validation_service: Quality Fabric validation for templates
- audit_trail_service: Audit logging and compliance
- deployment_service: Deployment management
- gate_service: Gate controls and policy enforcement
"""

from typing import TYPE_CHECKING

# Conditional imports - only import if modules are available
try:
    from .template_validation_service import (
        get_template_validation_service,
        ValidationOperation,
        ValidationStatus,
        ValidationResult,
        ValidationThresholds,
    )
    __all__ = [
        'get_template_validation_service',
        'ValidationOperation',
        'ValidationStatus',
        'ValidationResult',
        'ValidationThresholds',
    ]
except ImportError:
    __all__ = []
