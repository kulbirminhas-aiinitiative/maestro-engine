"""
Service Integrations via API Gateway

This package contains integration clients for communicating with other
MAESTRO services through the API Gateway.

All inter-service communication should go through the gateway using these clients.
"""

from src.integrations.quality_service import quality_service
from src.integrations.templates_service import templates_service

__all__ = ["quality_service", "templates_service"]
