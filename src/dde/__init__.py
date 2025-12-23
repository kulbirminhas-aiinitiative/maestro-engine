#!/usr/bin/env python3
"""
DDE (Dependency-Driven Execution) Module

Provides production-ready execution tracking, routing, artifact management,
auditing, contract enforcement, and resilience patterns for Maestro workflows.

Components:
- ExecutionManifest: Track all DAG node iterations
- RoutingEngine: Interface-first task scheduling
- ArtifactStamper: Artifact metadata and provenance
- DDEAuditor: PostgreSQL-backed audit trail
- ContractEnforcer: Interface contract validation
- CircuitBreaker: Agent failure resilience

Part of MD-2044: [EPIC 4] DDE Stream Completion
"""

from .execution_manifest import (
    ExecutionManifest,
    NodeExecution,
    ExecutionStatus,
    ErrorInfo,
)
from .routing_engine import (
    RoutingEngine,
    InterfaceContract,
    InterfaceField,
    ReadinessScore,
)
from .artifact_stamper import (
    ArtifactStamper,
    ArtifactStamp,
    VerificationResult,
)
from .auditor import (
    DDEAuditor,
    DDEAuditEvent,
    DDEAuditEventType,
)
from .contract_enforcer import (
    ContractEnforcer,
    ValidationResult,
    EnforcementMode,
    Drift,
)
from .circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreakerStats,
)

__all__ = [
    # Execution Manifest
    "ExecutionManifest",
    "NodeExecution",
    "ExecutionStatus",
    "ErrorInfo",
    # Routing Engine
    "RoutingEngine",
    "InterfaceContract",
    "InterfaceField",
    "ReadinessScore",
    # Artifact Stamper
    "ArtifactStamper",
    "ArtifactStamp",
    "VerificationResult",
    # Auditor
    "DDEAuditor",
    "DDEAuditEvent",
    "DDEAuditEventType",
    # Contract Enforcer
    "ContractEnforcer",
    "ValidationResult",
    "EnforcementMode",
    "Drift",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitBreakerStats",
]

__version__ = "1.0.0"
