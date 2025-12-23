#!/usr/bin/env python3
"""
Governance Service for MAESTRO Engine
Implements MD-2107: Governance Protocol Integration

This service provides:
- Governance Protocol schema loading and validation
- Document requirement verification per phase
- Phase transition governance enforcement
- Approval workflow management
- Audit trail for all governance decisions

Acceptance Criteria:
- AC-1: Governance Protocol schema defines required docs per phase
- AC-2: GovernanceService validates phases have required documentation
- AC-3: Phase transitions blocked if governance fails
- AC-4: Governance decisions logged for audit trail
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import yaml

# Try to import Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, Gauge

    GOVERNANCE_VALIDATIONS = Counter(
        "maestro_governance_validations_total",
        "Total governance validations",
        ["phase", "result"]
    )
    GOVERNANCE_VALIDATION_LATENCY = Histogram(
        "maestro_governance_validation_latency_seconds",
        "Governance validation latency",
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
    )
    GOVERNANCE_OVERRIDES = Counter(
        "maestro_governance_overrides_total",
        "Total governance overrides",
        ["phase", "reason"]
    )
    DOCUMENT_VALIDATIONS = Counter(
        "maestro_document_validations_total",
        "Total document validations",
        ["phase", "document_type", "result"]
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

    class StubMetric:
        def inc(self):
            pass
        def dec(self):
            pass
        def observe(self, value):
            pass
        def labels(self, **kwargs):
            return self
        def set(self, value):
            pass

    GOVERNANCE_VALIDATIONS = StubMetric()
    GOVERNANCE_VALIDATION_LATENCY = StubMetric()
    GOVERNANCE_OVERRIDES = StubMetric()
    DOCUMENT_VALIDATIONS = StubMetric()

logger = logging.getLogger("governance_service")


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class GovernanceResult(str, Enum):
    """Result of a governance validation."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"  # Advisory gates failed but mandatory passed
    SKIPPED = "skipped"  # Governance was skipped (override)


class DocumentStatus(str, Enum):
    """Status of a document in governance context."""
    MISSING = "missing"
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalStatus(str, Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class EnforcementLevel(str, Enum):
    """Enforcement level for governance rules."""
    MANDATORY = "mandatory"
    ADVISORY = "advisory"


# Default config path
DEFAULT_GOVERNANCE_CONFIG = Path(__file__).parent.parent.parent / "config" / "governance_protocol.yaml"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class DocumentRequirement:
    """A required document for a phase."""
    name: str
    template: str
    validation: Dict[str, Any] = field(default_factory=dict)
    optional: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "template": self.template,
            "validation": self.validation,
            "optional": self.optional,
        }


@dataclass
class QualityGateRequirement:
    """A quality gate requirement for a phase."""
    gate_type: str
    name: str
    enforcement: EnforcementLevel
    criteria: Dict[str, Any] = field(default_factory=dict)
    approvers: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_type": self.gate_type,
            "name": self.name,
            "enforcement": self.enforcement.value if isinstance(self.enforcement, EnforcementLevel) else self.enforcement,
            "criteria": self.criteria,
            "approvers": self.approvers,
            "metrics": self.metrics,
        }


@dataclass
class ApprovalWorkflow:
    """Approval workflow configuration."""
    workflow_type: str
    stages: List[Dict[str, Any]] = field(default_factory=list)
    quorum: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.workflow_type,
            "stages": self.stages,
            "quorum": self.quorum,
        }


@dataclass
class PhaseGovernance:
    """Governance requirements for a phase."""
    phase_id: str
    display_name: str
    required_documents: List[DocumentRequirement] = field(default_factory=list)
    quality_gates: List[QualityGateRequirement] = field(default_factory=list)
    approval_workflow: Optional[ApprovalWorkflow] = None
    audit_requirements: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "display_name": self.display_name,
            "required_documents": [d.to_dict() for d in self.required_documents],
            "quality_gates": [g.to_dict() for g in self.quality_gates],
            "approval_workflow": self.approval_workflow.to_dict() if self.approval_workflow else None,
            "audit_requirements": self.audit_requirements,
        }


@dataclass
class DocumentValidationResult:
    """Result of validating a document."""
    document_name: str
    status: DocumentStatus
    passed: bool
    issues: List[str] = field(default_factory=list)
    hash: Optional[str] = None
    validated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_name": self.document_name,
            "status": self.status.value,
            "passed": self.passed,
            "issues": self.issues,
            "hash": self.hash,
            "validated_at": self.validated_at,
        }


@dataclass
class GateValidationResult:
    """Result of validating a quality gate."""
    gate_name: str
    gate_type: str
    enforcement: str
    passed: bool
    score: Optional[float] = None
    issues: List[str] = field(default_factory=list)
    validated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "gate_type": self.gate_type,
            "enforcement": self.enforcement,
            "passed": self.passed,
            "score": self.score,
            "issues": self.issues,
            "validated_at": self.validated_at,
        }


@dataclass
class GovernanceValidationResult:
    """Complete result of governance validation for a phase."""
    phase_id: str
    result: GovernanceResult
    document_results: List[DocumentValidationResult] = field(default_factory=list)
    gate_results: List[GateValidationResult] = field(default_factory=list)
    blocking_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    can_proceed: bool = False
    validated_at: Optional[str] = None
    validated_by: Optional[str] = None
    override_applied: bool = False
    override_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "result": self.result.value,
            "document_results": [d.to_dict() for d in self.document_results],
            "gate_results": [g.to_dict() for g in self.gate_results],
            "blocking_issues": self.blocking_issues,
            "warnings": self.warnings,
            "can_proceed": self.can_proceed,
            "validated_at": self.validated_at,
            "validated_by": self.validated_by,
            "override_applied": self.override_applied,
            "override_reason": self.override_reason,
        }


@dataclass
class AuditEntry:
    """An entry in the governance audit trail."""
    id: str
    timestamp: str
    action: str
    phase_id: str
    workflow_id: Optional[str]
    actor: Optional[str]
    result: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "action": self.action,
            "phase_id": self.phase_id,
            "workflow_id": self.workflow_id,
            "actor": self.actor,
            "result": self.result,
            "details": self.details,
        }


# ============================================================================
# GOVERNANCE SERVICE
# ============================================================================

class GovernanceService:
    """
    Service for enforcing governance protocols at phase gates.

    Responsibilities:
    - Load and validate governance protocol configuration
    - Validate documents against phase requirements
    - Evaluate quality gates for phase transitions
    - Manage approval workflows
    - Log all governance decisions for audit
    """

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        strict_mode: bool = False,
        allow_overrides: bool = True,
    ):
        """
        Initialize the governance service.

        Args:
            config_path: Path to governance protocol YAML file
            strict_mode: When True, block all transitions on any failure
            allow_overrides: When True, allow governance overrides with justification
        """
        self.config_path = Path(config_path) if config_path else DEFAULT_GOVERNANCE_CONFIG
        self.strict_mode = strict_mode
        self.allow_overrides = allow_overrides

        # Loaded configuration
        self._config: Dict[str, Any] = {}
        self._phase_governance: Dict[str, PhaseGovernance] = {}
        self._roles: Dict[str, Dict[str, Any]] = {}
        self._global_settings: Dict[str, Any] = {}

        # Audit trail
        self._audit_trail: List[AuditEntry] = []

        # Phase hooks for integration
        self._pre_transition_hooks: List[Callable] = []
        self._post_transition_hooks: List[Callable] = []

        # Document store (in-memory for now, could be backed by DB)
        self._documents: Dict[str, Dict[str, Any]] = {}

        # Approval requests
        self._approval_requests: Dict[str, Dict[str, Any]] = {}

        # Load configuration
        self._load_config()

    def _load_config(self) -> None:
        """Load governance protocol configuration from YAML."""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r") as f:
                    self._config = yaml.safe_load(f) or {}
                self._parse_config()
                logger.info(f"Loaded governance config from {self.config_path}")
            else:
                logger.warning(f"Governance config not found at {self.config_path}, using defaults")
                self._load_defaults()
        except Exception as e:
            logger.error(f"Failed to load governance config: {e}")
            self._load_defaults()

    def _parse_config(self) -> None:
        """Parse the loaded configuration into data structures."""
        # Parse phase governance
        phases = self._config.get("phases", {})
        for phase_id, phase_config in phases.items():
            self._phase_governance[phase_id] = self._parse_phase_governance(phase_id, phase_config)

        # Parse roles
        self._roles = self._config.get("roles", {})

        # Parse global settings
        self._global_settings = self._config.get("global_settings", {})

        # Apply global settings
        enforcement = self._global_settings.get("enforcement", {})
        self.strict_mode = enforcement.get("strict_mode", self.strict_mode)
        self.allow_overrides = enforcement.get("allow_overrides", self.allow_overrides)

    def _parse_phase_governance(self, phase_id: str, config: Dict[str, Any]) -> PhaseGovernance:
        """Parse phase governance configuration."""
        # Parse required documents
        required_docs = []
        for doc in config.get("required_documents", []):
            required_docs.append(DocumentRequirement(
                name=doc.get("name", "Unknown"),
                template=doc.get("template", ""),
                validation=doc.get("validation", {}),
                optional=doc.get("optional", False),
            ))

        # Parse quality gates
        quality_gates = []
        for gate in config.get("quality_gates", []):
            enforcement = gate.get("enforcement", "mandatory")
            if isinstance(enforcement, str):
                enforcement = EnforcementLevel(enforcement) if enforcement in ["mandatory", "advisory"] else EnforcementLevel.MANDATORY
            quality_gates.append(QualityGateRequirement(
                gate_type=gate.get("gate_type", ""),
                name=gate.get("name", ""),
                enforcement=enforcement,
                criteria=gate.get("criteria", {}),
                approvers=gate.get("approvers", {}),
                metrics=gate.get("metrics", {}),
            ))

        # Parse approval workflow
        approval_workflow = None
        if "approval_workflow" in config:
            wf = config["approval_workflow"]
            approval_workflow = ApprovalWorkflow(
                workflow_type=wf.get("type", "sequential"),
                stages=wf.get("stages", []),
                quorum=wf.get("quorum"),
            )

        return PhaseGovernance(
            phase_id=phase_id,
            display_name=config.get("display_name", phase_id.title()),
            required_documents=required_docs,
            quality_gates=quality_gates,
            approval_workflow=approval_workflow,
            audit_requirements=config.get("audit_requirements", {}),
        )

    def _load_defaults(self) -> None:
        """Load default governance configuration."""
        default_phases = ["requirements", "design", "implementation", "testing", "deployment"]
        for phase in default_phases:
            self._phase_governance[phase] = PhaseGovernance(
                phase_id=phase,
                display_name=phase.title(),
                required_documents=[],
                quality_gates=[],
            )

    def get_phase_requirements(self, phase_id: str) -> Optional[PhaseGovernance]:
        """
        Get governance requirements for a phase.

        Args:
            phase_id: The phase identifier

        Returns:
            PhaseGovernance object or None if not found
        """
        return self._phase_governance.get(phase_id)

    def list_phases(self) -> List[str]:
        """List all configured phases."""
        return list(self._phase_governance.keys())

    def register_document(
        self,
        phase_id: str,
        document_name: str,
        content: str,
        document_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Register a document for governance tracking.

        Args:
            phase_id: The phase this document belongs to
            document_name: Name of the document
            content: Document content
            document_type: Type of document
            metadata: Additional metadata

        Returns:
            Document ID
        """
        doc_id = hashlib.sha256(f"{phase_id}:{document_name}:{datetime.utcnow().isoformat()}".encode()).hexdigest()[:16]
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        self._documents[doc_id] = {
            "id": doc_id,
            "phase_id": phase_id,
            "name": document_name,
            "type": document_type,
            "content": content,
            "content_hash": content_hash,
            "status": DocumentStatus.SUBMITTED.value,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }

        self._log_audit(
            action="document_registered",
            phase_id=phase_id,
            result="success",
            details={"document_id": doc_id, "document_name": document_name},
        )

        return doc_id

    def validate_document(
        self,
        phase_id: str,
        document_name: str,
        content: str,
        sections: Optional[List[str]] = None,
    ) -> DocumentValidationResult:
        """
        Validate a document against phase requirements.

        Args:
            phase_id: The phase to validate against
            document_name: Name of the document
            content: Document content
            sections: List of sections found in the document

        Returns:
            DocumentValidationResult
        """
        phase_gov = self.get_phase_requirements(phase_id)
        if not phase_gov:
            return DocumentValidationResult(
                document_name=document_name,
                status=DocumentStatus.REJECTED,
                passed=False,
                issues=[f"Unknown phase: {phase_id}"],
                validated_at=datetime.utcnow().isoformat(),
            )

        # Find matching document requirement
        doc_req = None
        for req in phase_gov.required_documents:
            if req.name == document_name:
                doc_req = req
                break

        if not doc_req:
            # Document not required, pass it
            return DocumentValidationResult(
                document_name=document_name,
                status=DocumentStatus.APPROVED,
                passed=True,
                hash=hashlib.sha256(content.encode()).hexdigest(),
                validated_at=datetime.utcnow().isoformat(),
            )

        issues = []
        validation = doc_req.validation

        # Validate minimum sections
        if "min_sections" in validation and sections:
            if len(sections) < validation["min_sections"]:
                issues.append(f"Insufficient sections: {len(sections)} < {validation['min_sections']}")

        # Validate required sections
        if "required_sections" in validation and sections:
            missing = set(validation["required_sections"]) - set(sections)
            if missing:
                issues.append(f"Missing required sections: {', '.join(missing)}")

        # Validate content length
        if "min_length" in validation:
            if len(content) < validation["min_length"]:
                issues.append(f"Content too short: {len(content)} < {validation['min_length']}")

        passed = len(issues) == 0
        status = DocumentStatus.APPROVED if passed else DocumentStatus.REJECTED

        # Update metrics
        if HAS_PROMETHEUS:
            DOCUMENT_VALIDATIONS.labels(
                phase=phase_id,
                document_type=doc_req.template,
                result="passed" if passed else "failed"
            ).inc()

        return DocumentValidationResult(
            document_name=document_name,
            status=status,
            passed=passed,
            issues=issues,
            hash=hashlib.sha256(content.encode()).hexdigest(),
            validated_at=datetime.utcnow().isoformat(),
        )

    def validate_quality_gate(
        self,
        phase_id: str,
        gate_name: str,
        metrics: Optional[Dict[str, Any]] = None,
        evidence: Optional[List[Dict[str, Any]]] = None,
    ) -> GateValidationResult:
        """
        Validate a quality gate for a phase.

        Args:
            phase_id: The phase to validate
            gate_name: Name of the quality gate
            metrics: Metrics to evaluate
            evidence: Evidence supporting the gate

        Returns:
            GateValidationResult
        """
        phase_gov = self.get_phase_requirements(phase_id)
        if not phase_gov:
            return GateValidationResult(
                gate_name=gate_name,
                gate_type="unknown",
                enforcement="mandatory",
                passed=False,
                issues=[f"Unknown phase: {phase_id}"],
                validated_at=datetime.utcnow().isoformat(),
            )

        # Find matching gate requirement
        gate_req = None
        for req in phase_gov.quality_gates:
            if req.name == gate_name:
                gate_req = req
                break

        if not gate_req:
            return GateValidationResult(
                gate_name=gate_name,
                gate_type="unknown",
                enforcement="advisory",
                passed=True,  # Unknown gate passes by default
                validated_at=datetime.utcnow().isoformat(),
            )

        issues = []
        metrics = metrics or {}

        # Evaluate gate metrics
        for metric_name, required_value in gate_req.metrics.items():
            actual_value = metrics.get(metric_name)
            if actual_value is None:
                issues.append(f"Missing metric: {metric_name}")
            elif isinstance(required_value, bool):
                if actual_value != required_value:
                    issues.append(f"{metric_name}: expected {required_value}, got {actual_value}")
            elif isinstance(required_value, (int, float)):
                if actual_value < required_value:
                    issues.append(f"{metric_name}: {actual_value} < required {required_value}")

        # Evaluate gate criteria
        for criteria_name, required_value in gate_req.criteria.items():
            actual_value = metrics.get(criteria_name)
            if actual_value is None:
                issues.append(f"Missing criteria: {criteria_name}")
            elif actual_value != required_value:
                issues.append(f"{criteria_name}: expected {required_value}, got {actual_value}")

        # Check approvers if required
        if gate_req.approvers:
            min_count = gate_req.approvers.get("min_count", 1)
            approvals = metrics.get("approvals", [])
            if len(approvals) < min_count:
                issues.append(f"Insufficient approvals: {len(approvals)} < {min_count}")

        passed = len(issues) == 0
        enforcement = gate_req.enforcement.value if isinstance(gate_req.enforcement, EnforcementLevel) else gate_req.enforcement

        # Calculate score (0-100)
        total_checks = len(gate_req.metrics) + len(gate_req.criteria)
        if total_checks > 0:
            passed_checks = total_checks - len([i for i in issues if "Missing" not in i])
            score = (passed_checks / total_checks) * 100
        else:
            score = 100.0 if passed else 0.0

        return GateValidationResult(
            gate_name=gate_name,
            gate_type=gate_req.gate_type,
            enforcement=enforcement,
            passed=passed,
            score=score,
            issues=issues,
            validated_at=datetime.utcnow().isoformat(),
        )

    def validate_phase_transition(
        self,
        phase_id: str,
        workflow_id: Optional[str] = None,
        documents: Optional[Dict[str, Dict[str, Any]]] = None,
        gate_metrics: Optional[Dict[str, Dict[str, Any]]] = None,
        actor: Optional[str] = None,
        override: bool = False,
        override_reason: Optional[str] = None,
    ) -> GovernanceValidationResult:
        """
        Validate governance requirements for a phase transition.

        Args:
            phase_id: The phase to validate
            workflow_id: Optional workflow identifier
            documents: Map of document_name -> {content, sections, metadata}
            gate_metrics: Map of gate_name -> {metrics}
            actor: Who is requesting the transition
            override: Whether to apply governance override
            override_reason: Justification for override

        Returns:
            GovernanceValidationResult
        """
        import time
        start_time = time.time()

        phase_gov = self.get_phase_requirements(phase_id)
        if not phase_gov:
            result = GovernanceValidationResult(
                phase_id=phase_id,
                result=GovernanceResult.FAILED,
                blocking_issues=[f"Unknown phase: {phase_id}"],
                can_proceed=False,
                validated_at=datetime.utcnow().isoformat(),
                validated_by=actor,
            )
            self._log_audit(
                action="phase_validation",
                phase_id=phase_id,
                workflow_id=workflow_id,
                actor=actor,
                result="failed",
                details={"reason": "unknown_phase"},
            )
            return result

        documents = documents or {}
        gate_metrics = gate_metrics or {}

        document_results = []
        gate_results = []
        blocking_issues = []
        warnings = []

        # Validate required documents
        for doc_req in phase_gov.required_documents:
            doc_data = documents.get(doc_req.name, {})
            if not doc_data and not doc_req.optional:
                doc_result = DocumentValidationResult(
                    document_name=doc_req.name,
                    status=DocumentStatus.MISSING,
                    passed=False,
                    issues=["Document not provided"],
                    validated_at=datetime.utcnow().isoformat(),
                )
                blocking_issues.append(f"Missing required document: {doc_req.name}")
            else:
                doc_result = self.validate_document(
                    phase_id=phase_id,
                    document_name=doc_req.name,
                    content=doc_data.get("content", ""),
                    sections=doc_data.get("sections"),
                )
                if not doc_result.passed and not doc_req.optional:
                    blocking_issues.extend([f"[{doc_req.name}] {issue}" for issue in doc_result.issues])
                elif not doc_result.passed and doc_req.optional:
                    warnings.extend([f"[{doc_req.name}] {issue}" for issue in doc_result.issues])

            document_results.append(doc_result)

        # Validate quality gates
        for gate_req in phase_gov.quality_gates:
            metrics = gate_metrics.get(gate_req.name, {})
            gate_result = self.validate_quality_gate(
                phase_id=phase_id,
                gate_name=gate_req.name,
                metrics=metrics,
            )

            if not gate_result.passed:
                if gate_req.enforcement == EnforcementLevel.MANDATORY:
                    blocking_issues.extend([f"[{gate_req.name}] {issue}" for issue in gate_result.issues])
                else:
                    warnings.extend([f"[{gate_req.name}] {issue}" for issue in gate_result.issues])

            gate_results.append(gate_result)

        # Determine result
        has_blocking = len(blocking_issues) > 0
        has_warnings = len(warnings) > 0

        if has_blocking:
            result = GovernanceResult.FAILED
        elif has_warnings:
            result = GovernanceResult.WARNING
        else:
            result = GovernanceResult.PASSED

        # Handle override
        can_proceed = not has_blocking
        override_applied = False

        if has_blocking and override and self.allow_overrides:
            if override_reason:
                can_proceed = True
                override_applied = True
                result = GovernanceResult.SKIPPED

                if HAS_PROMETHEUS:
                    GOVERNANCE_OVERRIDES.labels(phase=phase_id, reason="manual").inc()

                self._log_audit(
                    action="governance_override",
                    phase_id=phase_id,
                    workflow_id=workflow_id,
                    actor=actor,
                    result="applied",
                    details={
                        "blocking_issues": blocking_issues,
                        "override_reason": override_reason,
                    },
                )
            else:
                warnings.append("Override requested but no reason provided")

        # Record metrics
        elapsed = time.time() - start_time
        if HAS_PROMETHEUS:
            GOVERNANCE_VALIDATIONS.labels(phase=phase_id, result=result.value).inc()
            GOVERNANCE_VALIDATION_LATENCY.observe(elapsed)

        # Log audit
        self._log_audit(
            action="phase_validation",
            phase_id=phase_id,
            workflow_id=workflow_id,
            actor=actor,
            result=result.value,
            details={
                "blocking_issues_count": len(blocking_issues),
                "warnings_count": len(warnings),
                "can_proceed": can_proceed,
                "override_applied": override_applied,
                "elapsed_ms": round(elapsed * 1000, 2),
            },
        )

        return GovernanceValidationResult(
            phase_id=phase_id,
            result=result,
            document_results=document_results,
            gate_results=gate_results,
            blocking_issues=blocking_issues,
            warnings=warnings,
            can_proceed=can_proceed,
            validated_at=datetime.utcnow().isoformat(),
            validated_by=actor,
            override_applied=override_applied,
            override_reason=override_reason if override_applied else None,
        )

    def _log_audit(
        self,
        action: str,
        phase_id: str,
        result: str,
        workflow_id: Optional[str] = None,
        actor: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an audit entry."""
        entry_id = hashlib.sha256(
            f"{action}:{phase_id}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]

        entry = AuditEntry(
            id=entry_id,
            timestamp=datetime.utcnow().isoformat(),
            action=action,
            phase_id=phase_id,
            workflow_id=workflow_id,
            actor=actor,
            result=result,
            details=details or {},
        )

        self._audit_trail.append(entry)
        logger.debug(f"Audit: {action} on {phase_id} = {result}")

    def get_audit_trail(
        self,
        phase_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail entries.

        Args:
            phase_id: Filter by phase
            workflow_id: Filter by workflow
            limit: Maximum entries to return

        Returns:
            List of audit entries
        """
        entries = self._audit_trail

        if phase_id:
            entries = [e for e in entries if e.phase_id == phase_id]
        if workflow_id:
            entries = [e for e in entries if e.workflow_id == workflow_id]

        # Return most recent first
        return [e.to_dict() for e in sorted(entries, key=lambda x: x.timestamp, reverse=True)[:limit]]

    def register_pre_transition_hook(self, hook: Callable) -> None:
        """Register a hook to run before phase transitions."""
        self._pre_transition_hooks.append(hook)

    def register_post_transition_hook(self, hook: Callable) -> None:
        """Register a hook to run after phase transitions."""
        self._post_transition_hooks.append(hook)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize service configuration."""
        return {
            "config_path": str(self.config_path),
            "strict_mode": self.strict_mode,
            "allow_overrides": self.allow_overrides,
            "phases": [p.to_dict() for p in self._phase_governance.values()],
            "roles": self._roles,
            "global_settings": self._global_settings,
        }


# ============================================================================
# GOVERNANCE PROTOCOL HOOK FOR PHASE GATES
# ============================================================================

class GovernancePhaseHook:
    """
    Hook for integrating governance validation into phase transitions.

    This class can be registered with the Phase service to enforce
    governance at phase boundaries.
    """

    def __init__(self, governance_service: GovernanceService):
        self.governance_service = governance_service
        self._document_cache: Dict[str, Dict[str, Any]] = {}
        self._gate_metrics_cache: Dict[str, Dict[str, Any]] = {}

    def set_phase_documents(self, phase_id: str, documents: Dict[str, Dict[str, Any]]) -> None:
        """Cache documents for a phase validation."""
        self._document_cache[phase_id] = documents

    def set_gate_metrics(self, phase_id: str, metrics: Dict[str, Dict[str, Any]]) -> None:
        """Cache gate metrics for a phase validation."""
        self._gate_metrics_cache[phase_id] = metrics

    def validate_transition(
        self,
        from_phase: str,
        to_phase: str,
        workflow_id: Optional[str] = None,
        actor: Optional[str] = None,
        override: bool = False,
        override_reason: Optional[str] = None,
    ) -> Tuple[bool, GovernanceValidationResult]:
        """
        Validate that a phase transition can proceed.

        Args:
            from_phase: Current phase
            to_phase: Target phase
            workflow_id: Workflow identifier
            actor: Who is requesting the transition
            override: Whether to override governance
            override_reason: Justification for override

        Returns:
            Tuple of (can_proceed, validation_result)
        """
        # Validate the current phase before allowing transition
        result = self.governance_service.validate_phase_transition(
            phase_id=from_phase,
            workflow_id=workflow_id,
            documents=self._document_cache.get(from_phase, {}),
            gate_metrics=self._gate_metrics_cache.get(from_phase, {}),
            actor=actor,
            override=override,
            override_reason=override_reason,
        )

        return result.can_proceed, result

    def clear_cache(self, phase_id: Optional[str] = None) -> None:
        """Clear cached documents and metrics."""
        if phase_id:
            self._document_cache.pop(phase_id, None)
            self._gate_metrics_cache.pop(phase_id, None)
        else:
            self._document_cache.clear()
            self._gate_metrics_cache.clear()


# ============================================================================
# SINGLETON ACCESS
# ============================================================================

_governance_service: Optional[GovernanceService] = None


def get_governance_service(
    config_path: Optional[Union[str, Path]] = None,
    strict_mode: bool = False,
    allow_overrides: bool = True,
) -> GovernanceService:
    """
    Get or create the singleton governance service.

    Args:
        config_path: Path to governance config (only used on first call)
        strict_mode: Enable strict governance mode
        allow_overrides: Allow governance overrides

    Returns:
        GovernanceService singleton
    """
    global _governance_service
    if _governance_service is None:
        _governance_service = GovernanceService(
            config_path=config_path,
            strict_mode=strict_mode,
            allow_overrides=allow_overrides,
        )
    return _governance_service


def reset_governance_service() -> None:
    """Reset the singleton for testing."""
    global _governance_service
    _governance_service = None
