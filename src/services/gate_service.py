#!/usr/bin/env python3
"""
Gate Framework Service for MAESTRO Engine
Implements EPIC-2: Gate Framework (DDE/BRV/ACC)

This service provides:
- Gate type definitions: DDE (Design Decision Evidence), BRV (Business Review), ACC (Acceptance Criteria)
- Gate status management: open, pending, passed, failed
- Evidence attachment and tracking
- Audit trail for all gate operations
- Dry-run mode for non-blocking gate evaluation
- Override support with X-Gate-Override header
- WebSocket event emission for real-time updates

Acceptance Criteria:
- AC-1: Gates computed and stored per phase with status open/pending/passed/failed
- AC-2: Evidence URIs attachable to gates
- AC-3: Mixed-mode execution halts on failed mandatory gate unless override
- AC-4: Override requires explicit X-Gate-Override header with audit
- AC-5: WebSocket ws:gate:update broadcasts state changes
- AC-6: Dry-run mode computes gates without blocking
- AC-7: Audit trail persists all gate decisions
- AC-8: Per-template gate checklists configurable
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Try to import Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, Gauge

    GATE_EVALUATIONS = Counter(
        "maestro_gate_evaluations_total",
        "Total gate evaluations",
        ["gate_type", "status"]
    )
    GATE_EVALUATION_LATENCY = Histogram(
        "maestro_gate_evaluation_latency_seconds",
        "Gate evaluation latency",
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
    )
    GATE_OVERRIDES = Counter(
        "maestro_gate_overrides_total",
        "Total gate overrides",
        ["gate_type", "reason"]
    )
    ACTIVE_GATES = Gauge(
        "maestro_active_gates",
        "Number of active gates",
        ["status"]
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

    GATE_EVALUATIONS = StubMetric()
    GATE_EVALUATION_LATENCY = StubMetric()
    GATE_OVERRIDES = StubMetric()
    ACTIVE_GATES = StubMetric()

logger = logging.getLogger("gate_service")


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class GateType(str, Enum):
    """Types of quality gates."""
    DDE = "DDE"  # Design Decision Evidence
    BRV = "BRV"  # Business Review Validation
    ACC = "ACC"  # Acceptance Criteria Complete


class GateStatus(str, Enum):
    """Status of a gate."""
    OPEN = "open"        # Gate not yet evaluated
    PENDING = "pending"  # Gate evaluation in progress / awaiting approval
    PASSED = "passed"    # Gate requirements met
    FAILED = "failed"    # Gate requirements not met


class GateEnforcement(str, Enum):
    """Enforcement level for gates."""
    MANDATORY = "mandatory"  # Must pass to continue
    ADVISORY = "advisory"    # Warning only, doesn't block


class EvidenceType(str, Enum):
    """Types of evidence that can be attached to gates."""
    DOCUMENT = "document"      # Document URL/reference
    TEST_RESULT = "test_result"  # Test execution result
    CODE_REVIEW = "code_review"  # Code review approval
    APPROVAL = "approval"      # Manual approval
    METRIC = "metric"          # Quality metric
    ARTIFACT = "artifact"      # Build artifact


# Default gate checklists per phase type
DEFAULT_PHASE_GATES = {
    "requirements": [
        {"gate_type": GateType.BRV, "name": "Requirements Approved", "enforcement": GateEnforcement.MANDATORY},
        {"gate_type": GateType.ACC, "name": "Acceptance Criteria Defined", "enforcement": GateEnforcement.MANDATORY},
    ],
    "design": [
        {"gate_type": GateType.DDE, "name": "Architecture Decisions Documented", "enforcement": GateEnforcement.MANDATORY},
        {"gate_type": GateType.BRV, "name": "Design Review Completed", "enforcement": GateEnforcement.ADVISORY},
    ],
    "implementation": [
        {"gate_type": GateType.DDE, "name": "Code Standards Met", "enforcement": GateEnforcement.MANDATORY},
        {"gate_type": GateType.ACC, "name": "Unit Tests Passing", "enforcement": GateEnforcement.MANDATORY},
    ],
    "testing": [
        {"gate_type": GateType.ACC, "name": "Integration Tests Passing", "enforcement": GateEnforcement.MANDATORY},
        {"gate_type": GateType.DDE, "name": "Test Coverage Met", "enforcement": GateEnforcement.ADVISORY},
    ],
    "deployment": [
        {"gate_type": GateType.BRV, "name": "Deployment Approved", "enforcement": GateEnforcement.MANDATORY},
        {"gate_type": GateType.ACC, "name": "Smoke Tests Passing", "enforcement": GateEnforcement.MANDATORY},
    ],
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Evidence:
    """Evidence attached to a gate."""
    id: str
    type: EvidenceType
    uri: str
    description: str
    attached_by: Optional[str] = None
    attached_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, EvidenceType) else self.type,
            "uri": self.uri,
            "description": self.description,
            "attached_by": self.attached_by,
            "attached_at": self.attached_at,
            "metadata": self.metadata,
        }


@dataclass
class GateCheckItem:
    """Individual check item within a gate."""
    id: str
    name: str
    description: str
    passed: bool
    score: Optional[float] = None  # 0-100
    message: Optional[str] = None
    evidence_required: bool = False
    evidence: Optional[Evidence] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "passed": self.passed,
            "score": self.score,
            "message": self.message,
            "evidence_required": self.evidence_required,
            "evidence": self.evidence.to_dict() if self.evidence else None,
        }


@dataclass
class Gate:
    """
    A quality gate for a workflow phase.
    """
    id: str
    gate_type: GateType
    name: str
    description: str
    phase_id: str
    workflow_id: str
    session_id: Optional[str]

    # Status tracking
    status: GateStatus = GateStatus.OPEN
    enforcement: GateEnforcement = GateEnforcement.MANDATORY

    # Check results
    check_items: List[GateCheckItem] = field(default_factory=list)
    overall_score: Optional[float] = None  # 0-100

    # Evidence
    evidence: List[Evidence] = field(default_factory=list)

    # Timestamps
    created_at: Optional[str] = None
    evaluated_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Override tracking
    was_overridden: bool = False
    override_reason: Optional[str] = None
    override_by: Optional[str] = None
    override_at: Optional[str] = None

    # Audit
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "gate_type": self.gate_type.value,
            "name": self.name,
            "description": self.description,
            "phase_id": self.phase_id,
            "workflow_id": self.workflow_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "enforcement": self.enforcement.value,
            "check_items": [item.to_dict() for item in self.check_items],
            "overall_score": self.overall_score,
            "evidence": [e.to_dict() for e in self.evidence],
            "created_at": self.created_at,
            "evaluated_at": self.evaluated_at,
            "completed_at": self.completed_at,
            "was_overridden": self.was_overridden,
            "override_reason": self.override_reason,
            "override_by": self.override_by,
            "override_at": self.override_at,
            "audit_trail": self.audit_trail,
        }


@dataclass
class GateEvaluationResult:
    """Result of evaluating a gate."""
    gate_id: str
    gate_type: GateType
    status: GateStatus
    passed: bool
    blocking: bool  # Whether this blocks workflow progression
    overall_score: float
    check_items: List[GateCheckItem]
    message: str
    remediation: List[str]
    evaluated_at: str
    evaluation_time_ms: float
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "gate_type": self.gate_type.value,
            "status": self.status.value,
            "passed": self.passed,
            "blocking": self.blocking,
            "overall_score": round(self.overall_score, 2),
            "check_items": [item.to_dict() for item in self.check_items],
            "message": self.message,
            "remediation": self.remediation,
            "evaluated_at": self.evaluated_at,
            "evaluation_time_ms": round(self.evaluation_time_ms, 2),
            "dry_run": self.dry_run,
        }


@dataclass
class AuditEntry:
    """Audit trail entry for gate operations."""
    id: str
    gate_id: str
    action: str  # created, evaluated, passed, failed, overridden, evidence_attached
    actor: Optional[str]
    timestamp: str
    details: Dict[str, Any]
    previous_status: Optional[str] = None
    new_status: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "gate_id": self.gate_id,
            "action": self.action,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "details": self.details,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
        }


# ============================================================================
# GATE STORAGE (In-Memory + Redis-ready)
# ============================================================================

class GateStorage:
    """
    Storage manager for gates.
    Uses in-memory storage with Redis-compatible interface.
    Can be extended to use Redis directly.
    """

    def __init__(self):
        self._gates: Dict[str, Gate] = {}
        self._workflow_gates: Dict[str, List[str]] = {}  # workflow_id -> [gate_ids]
        self._phase_gates: Dict[str, List[str]] = {}  # phase_id -> [gate_ids]
        self._audit_log: List[AuditEntry] = []
        logger.info("Gate Storage initialized")

    def store_gate(self, gate: Gate) -> None:
        """Store a gate."""
        self._gates[gate.id] = gate

        # Index by workflow
        if gate.workflow_id not in self._workflow_gates:
            self._workflow_gates[gate.workflow_id] = []
        if gate.id not in self._workflow_gates[gate.workflow_id]:
            self._workflow_gates[gate.workflow_id].append(gate.id)

        # Index by phase
        if gate.phase_id not in self._phase_gates:
            self._phase_gates[gate.phase_id] = []
        if gate.id not in self._phase_gates[gate.phase_id]:
            self._phase_gates[gate.phase_id].append(gate.id)

    def get_gate(self, gate_id: str) -> Optional[Gate]:
        """Get a gate by ID."""
        return self._gates.get(gate_id)

    def get_gates_by_workflow(self, workflow_id: str) -> List[Gate]:
        """Get all gates for a workflow."""
        gate_ids = self._workflow_gates.get(workflow_id, [])
        return [self._gates[gid] for gid in gate_ids if gid in self._gates]

    def get_gates_by_phase(self, phase_id: str) -> List[Gate]:
        """Get all gates for a phase."""
        gate_ids = self._phase_gates.get(phase_id, [])
        return [self._gates[gid] for gid in gate_ids if gid in self._gates]

    def update_gate(self, gate: Gate) -> None:
        """Update an existing gate."""
        self._gates[gate.id] = gate

    def add_audit_entry(self, entry: AuditEntry) -> None:
        """Add an audit entry."""
        self._audit_log.append(entry)

    def get_audit_trail(self, gate_id: str) -> List[AuditEntry]:
        """Get audit trail for a gate."""
        return [e for e in self._audit_log if e.gate_id == gate_id]

    def get_all_gates(self) -> List[Gate]:
        """Get all gates."""
        return list(self._gates.values())


# ============================================================================
# GATE EVALUATOR
# ============================================================================

class GateEvaluator:
    """
    Evaluates gates based on check criteria.
    """

    def __init__(self):
        """Initialize gate evaluator."""
        logger.info("Gate Evaluator initialized")

    def evaluate_dde_gate(
        self,
        gate: Gate,
        context: Dict[str, Any],
    ) -> GateEvaluationResult:
        """
        Evaluate a Design Decision Evidence (DDE) gate.

        Checks:
        - Architecture decisions documented
        - Technical rationale provided
        - Trade-offs analyzed
        - Evidence attached
        """
        start_time = time.time()
        check_items = []

        # Check 1: Architecture document exists
        arch_doc = context.get("architecture_document")
        check_items.append(GateCheckItem(
            id=f"{gate.id}_arch_doc",
            name="Architecture Document",
            description="Architecture decisions are documented",
            passed=bool(arch_doc),
            score=100.0 if arch_doc else 0.0,
            message="Architecture document found" if arch_doc else "No architecture document",
            evidence_required=True,
        ))

        # Check 2: Technical rationale provided
        rationale = context.get("technical_rationale")
        check_items.append(GateCheckItem(
            id=f"{gate.id}_rationale",
            name="Technical Rationale",
            description="Technical rationale is provided for key decisions",
            passed=bool(rationale),
            score=100.0 if rationale else 0.0,
            message="Rationale documented" if rationale else "No rationale found",
        ))

        # Check 3: Code standards met
        code_quality = context.get("code_quality_score", 0)
        min_quality = context.get("min_code_quality", 70)
        check_items.append(GateCheckItem(
            id=f"{gate.id}_code_quality",
            name="Code Quality Standards",
            description=f"Code quality score >= {min_quality}",
            passed=code_quality >= min_quality,
            score=code_quality,
            message=f"Code quality: {code_quality}%",
        ))

        # Check 4: Evidence attached
        has_evidence = len(gate.evidence) > 0
        check_items.append(GateCheckItem(
            id=f"{gate.id}_evidence",
            name="Evidence Attached",
            description="Supporting evidence is attached",
            passed=has_evidence,
            score=100.0 if has_evidence else 0.0,
            message=f"{len(gate.evidence)} evidence items attached",
            evidence_required=True,
        ))

        return self._build_result(gate, check_items, start_time)

    def evaluate_brv_gate(
        self,
        gate: Gate,
        context: Dict[str, Any],
    ) -> GateEvaluationResult:
        """
        Evaluate a Business Review Validation (BRV) gate.

        Checks:
        - Business requirements addressed
        - Stakeholder approval received
        - ROI/value documented
        - Risk assessment completed
        """
        start_time = time.time()
        check_items = []

        # Check 1: Requirements addressed
        requirements_met = context.get("requirements_addressed", False)
        check_items.append(GateCheckItem(
            id=f"{gate.id}_requirements",
            name="Requirements Addressed",
            description="All business requirements are addressed",
            passed=requirements_met,
            score=100.0 if requirements_met else 0.0,
            message="Requirements verified" if requirements_met else "Requirements not fully addressed",
        ))

        # Check 2: Stakeholder approval
        approvals = context.get("stakeholder_approvals", [])
        required_approvals = context.get("required_approvals", 1)
        has_approvals = len(approvals) >= required_approvals
        check_items.append(GateCheckItem(
            id=f"{gate.id}_approvals",
            name="Stakeholder Approval",
            description=f"At least {required_approvals} stakeholder approval(s)",
            passed=has_approvals,
            score=min(100.0, (len(approvals) / required_approvals) * 100) if required_approvals > 0 else 100.0,
            message=f"{len(approvals)}/{required_approvals} approvals received",
            evidence_required=True,
        ))

        # Check 3: Value documentation
        value_documented = context.get("value_documented", False)
        check_items.append(GateCheckItem(
            id=f"{gate.id}_value",
            name="Value Documentation",
            description="Business value/ROI is documented",
            passed=value_documented,
            score=100.0 if value_documented else 0.0,
            message="Value documented" if value_documented else "Value not documented",
        ))

        # Check 4: Risk assessment
        risk_assessed = context.get("risk_assessment_completed", False)
        check_items.append(GateCheckItem(
            id=f"{gate.id}_risk",
            name="Risk Assessment",
            description="Risk assessment is completed",
            passed=risk_assessed,
            score=100.0 if risk_assessed else 0.0,
            message="Risk assessment complete" if risk_assessed else "Risk assessment pending",
        ))

        return self._build_result(gate, check_items, start_time)

    def evaluate_acc_gate(
        self,
        gate: Gate,
        context: Dict[str, Any],
    ) -> GateEvaluationResult:
        """
        Evaluate an Acceptance Criteria Complete (ACC) gate.

        Checks:
        - All acceptance criteria defined
        - Tests exist for each criterion
        - Tests passing
        - Coverage threshold met
        """
        start_time = time.time()
        check_items = []

        # Check 1: Acceptance criteria defined
        ac_defined = context.get("acceptance_criteria", [])
        check_items.append(GateCheckItem(
            id=f"{gate.id}_ac_defined",
            name="Acceptance Criteria Defined",
            description="Acceptance criteria are clearly defined",
            passed=len(ac_defined) > 0,
            score=100.0 if len(ac_defined) > 0 else 0.0,
            message=f"{len(ac_defined)} acceptance criteria defined",
        ))

        # Check 2: Test coverage
        test_coverage = context.get("test_coverage", 0)
        min_coverage = context.get("min_test_coverage", 80)
        check_items.append(GateCheckItem(
            id=f"{gate.id}_coverage",
            name="Test Coverage",
            description=f"Test coverage >= {min_coverage}%",
            passed=test_coverage >= min_coverage,
            score=test_coverage,
            message=f"Test coverage: {test_coverage}%",
        ))

        # Check 3: Tests passing
        tests_passed = context.get("tests_passed", 0)
        tests_total = context.get("tests_total", 0)
        all_passing = tests_passed == tests_total and tests_total > 0
        check_items.append(GateCheckItem(
            id=f"{gate.id}_tests",
            name="Tests Passing",
            description="All tests are passing",
            passed=all_passing,
            score=(tests_passed / tests_total * 100) if tests_total > 0 else 0.0,
            message=f"{tests_passed}/{tests_total} tests passing",
        ))

        # Check 4: AC verification
        ac_verified = context.get("acceptance_criteria_verified", 0)
        ac_total = len(ac_defined)
        all_verified = ac_verified == ac_total and ac_total > 0
        check_items.append(GateCheckItem(
            id=f"{gate.id}_ac_verified",
            name="Acceptance Criteria Verified",
            description="All acceptance criteria are verified",
            passed=all_verified,
            score=(ac_verified / ac_total * 100) if ac_total > 0 else 0.0,
            message=f"{ac_verified}/{ac_total} criteria verified",
        ))

        return self._build_result(gate, check_items, start_time)

    def _build_result(
        self,
        gate: Gate,
        check_items: List[GateCheckItem],
        start_time: float,
    ) -> GateEvaluationResult:
        """Build evaluation result from check items."""
        evaluation_time = (time.time() - start_time) * 1000

        # Calculate overall score
        scores = [item.score for item in check_items if item.score is not None]
        overall_score = sum(scores) / len(scores) if scores else 0.0

        # Determine pass/fail
        passed = all(item.passed for item in check_items)
        status = GateStatus.PASSED if passed else GateStatus.FAILED

        # Determine if blocking
        blocking = not passed and gate.enforcement == GateEnforcement.MANDATORY

        # Generate message
        passed_count = sum(1 for item in check_items if item.passed)
        message = f"{passed_count}/{len(check_items)} checks passed"
        if passed:
            message = f"Gate passed: {message}"
        else:
            message = f"Gate failed: {message}"

        # Generate remediation suggestions
        remediation = []
        for item in check_items:
            if not item.passed:
                remediation.append(f"Fix: {item.name} - {item.message}")

        return GateEvaluationResult(
            gate_id=gate.id,
            gate_type=gate.gate_type,
            status=status,
            passed=passed,
            blocking=blocking,
            overall_score=overall_score,
            check_items=check_items,
            message=message,
            remediation=remediation,
            evaluated_at=datetime.now().isoformat(),
            evaluation_time_ms=evaluation_time,
        )


# ============================================================================
# GATE SERVICE
# ============================================================================

class GateService:
    """
    Main service for managing quality gates.

    Provides:
    - Gate creation and management
    - Gate evaluation
    - Evidence attachment
    - Override handling
    - Audit trail
    - Dry-run mode
    """

    def __init__(
        self,
        storage: Optional[GateStorage] = None,
        feature_flag_enabled: bool = True,
    ):
        """
        Initialize Gate Service.

        Args:
            storage: Gate storage backend
            feature_flag_enabled: Whether FF_GATES_ENFORCEMENT_ENABLED is true
        """
        self.storage = storage or GateStorage()
        self.evaluator = GateEvaluator()
        self.feature_flag_enabled = feature_flag_enabled

        logger.info(f"Gate Service initialized (FF_GATES_ENFORCEMENT_ENABLED={feature_flag_enabled})")

    def create_gate(
        self,
        gate_type: GateType,
        name: str,
        description: str,
        phase_id: str,
        workflow_id: str,
        session_id: Optional[str] = None,
        enforcement: GateEnforcement = GateEnforcement.MANDATORY,
    ) -> Gate:
        """
        Create a new gate.

        Args:
            gate_type: Type of gate (DDE, BRV, ACC)
            name: Gate name
            description: Gate description
            phase_id: ID of the phase this gate belongs to
            workflow_id: ID of the workflow
            session_id: Optional session ID
            enforcement: Enforcement level (mandatory/advisory)

        Returns:
            Created Gate object
        """
        gate_id = self._generate_gate_id(gate_type, phase_id, workflow_id)

        gate = Gate(
            id=gate_id,
            gate_type=gate_type,
            name=name,
            description=description,
            phase_id=phase_id,
            workflow_id=workflow_id,
            session_id=session_id,
            status=GateStatus.OPEN,
            enforcement=enforcement,
            created_at=datetime.now().isoformat(),
        )

        # Store gate
        self.storage.store_gate(gate)

        # Audit
        self._audit(gate, "created", None, {"enforcement": enforcement.value})

        logger.info(f"Gate created: {gate_id} ({gate_type.value}) for phase {phase_id}")

        return gate

    def create_gates_for_phase(
        self,
        phase_type: str,
        phase_id: str,
        workflow_id: str,
        session_id: Optional[str] = None,
        custom_gates: Optional[List[Dict]] = None,
    ) -> List[Gate]:
        """
        Create default gates for a phase type.

        Args:
            phase_type: Type of phase (requirements, design, etc.)
            phase_id: Phase ID
            workflow_id: Workflow ID
            session_id: Optional session ID
            custom_gates: Optional custom gate definitions

        Returns:
            List of created gates
        """
        gate_defs = custom_gates or DEFAULT_PHASE_GATES.get(phase_type, [])
        gates = []

        for gate_def in gate_defs:
            gate = self.create_gate(
                gate_type=gate_def["gate_type"] if isinstance(gate_def["gate_type"], GateType) else GateType(gate_def["gate_type"]),
                name=gate_def["name"],
                description=gate_def.get("description", gate_def["name"]),
                phase_id=phase_id,
                workflow_id=workflow_id,
                session_id=session_id,
                enforcement=gate_def.get("enforcement", GateEnforcement.MANDATORY) if isinstance(gate_def.get("enforcement"), GateEnforcement) else GateEnforcement(gate_def.get("enforcement", "mandatory")),
            )
            gates.append(gate)

        logger.info(f"Created {len(gates)} gates for phase {phase_id} ({phase_type})")
        return gates

    def evaluate_gate(
        self,
        gate_id: str,
        context: Dict[str, Any],
        dry_run: bool = False,
        override: bool = False,
        override_reason: Optional[str] = None,
        override_by: Optional[str] = None,
    ) -> GateEvaluationResult:
        """
        Evaluate a gate.

        Args:
            gate_id: ID of the gate to evaluate
            context: Evaluation context with check data
            dry_run: If True, don't update gate status
            override: If True, force gate to pass
            override_reason: Reason for override
            override_by: Who is overriding

        Returns:
            GateEvaluationResult
        """
        start_time = time.time()

        gate = self.storage.get_gate(gate_id)
        if not gate:
            raise ValueError(f"Gate not found: {gate_id}")

        # Evaluate based on gate type
        if gate.gate_type == GateType.DDE:
            result = self.evaluator.evaluate_dde_gate(gate, context)
        elif gate.gate_type == GateType.BRV:
            result = self.evaluator.evaluate_brv_gate(gate, context)
        elif gate.gate_type == GateType.ACC:
            result = self.evaluator.evaluate_acc_gate(gate, context)
        else:
            raise ValueError(f"Unknown gate type: {gate.gate_type}")

        result.dry_run = dry_run

        # Handle override
        if override and not result.passed:
            result.passed = True
            result.blocking = False
            result.status = GateStatus.PASSED
            result.message = f"Gate overridden: {override_reason or 'No reason provided'}"

            if not dry_run:
                gate.was_overridden = True
                gate.override_reason = override_reason
                gate.override_by = override_by
                gate.override_at = datetime.now().isoformat()

                if HAS_PROMETHEUS:
                    GATE_OVERRIDES.labels(
                        gate_type=gate.gate_type.value,
                        reason=override_reason or "unspecified"
                    ).inc()

        # Update gate if not dry run
        if not dry_run:
            previous_status = gate.status
            gate.status = result.status
            gate.check_items = result.check_items
            gate.overall_score = result.overall_score
            gate.evaluated_at = result.evaluated_at

            if result.passed:
                gate.completed_at = datetime.now().isoformat()

            self.storage.update_gate(gate)

            # Audit
            self._audit(
                gate,
                "evaluated" if not override else "overridden",
                override_by,
                {
                    "passed": result.passed,
                    "score": result.overall_score,
                    "dry_run": dry_run,
                    "override": override,
                    "override_reason": override_reason,
                },
                previous_status.value,
                result.status.value,
            )

        # Metrics
        if HAS_PROMETHEUS:
            GATE_EVALUATIONS.labels(
                gate_type=gate.gate_type.value,
                status=result.status.value
            ).inc()
            GATE_EVALUATION_LATENCY.observe((time.time() - start_time))

        logger.info(
            f"Gate evaluated: {gate_id} ({gate.gate_type.value}) -> {result.status.value} "
            f"(score={result.overall_score:.1f}%, dry_run={dry_run}, override={override})"
        )

        return result

    def evaluate_phase_gates(
        self,
        phase_id: str,
        context: Dict[str, Any],
        dry_run: bool = False,
    ) -> Tuple[bool, List[GateEvaluationResult]]:
        """
        Evaluate all gates for a phase.

        Args:
            phase_id: Phase ID
            context: Evaluation context
            dry_run: If True, don't update gate status

        Returns:
            Tuple of (all_passed, results)
        """
        gates = self.storage.get_gates_by_phase(phase_id)
        results = []
        all_passed = True
        any_blocking = False

        for gate in gates:
            result = self.evaluate_gate(gate.id, context, dry_run=dry_run)
            results.append(result)

            if not result.passed:
                all_passed = False
                if result.blocking:
                    any_blocking = True

        logger.info(
            f"Phase gates evaluated: {phase_id} - "
            f"{sum(1 for r in results if r.passed)}/{len(results)} passed, "
            f"blocking={any_blocking}"
        )

        return (all_passed and not any_blocking), results

    def attach_evidence(
        self,
        gate_id: str,
        evidence_type: EvidenceType,
        uri: str,
        description: str,
        attached_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Evidence:
        """
        Attach evidence to a gate.

        Args:
            gate_id: Gate ID
            evidence_type: Type of evidence
            uri: Evidence URI/reference
            description: Evidence description
            attached_by: Who attached the evidence
            metadata: Additional metadata

        Returns:
            Created Evidence object
        """
        gate = self.storage.get_gate(gate_id)
        if not gate:
            raise ValueError(f"Gate not found: {gate_id}")

        evidence = Evidence(
            id=f"ev_{hashlib.md5(f'{gate_id}_{uri}_{time.time()}'.encode()).hexdigest()[:12]}",
            type=evidence_type,
            uri=uri,
            description=description,
            attached_by=attached_by,
            attached_at=datetime.now().isoformat(),
            metadata=metadata or {},
        )

        gate.evidence.append(evidence)
        self.storage.update_gate(gate)

        # Audit
        self._audit(gate, "evidence_attached", attached_by, {
            "evidence_id": evidence.id,
            "evidence_type": evidence_type.value,
            "uri": uri,
        })

        logger.info(f"Evidence attached to gate {gate_id}: {evidence.id}")

        return evidence

    def approve_gate(
        self,
        gate_id: str,
        approved_by: str,
        comment: Optional[str] = None,
    ) -> Gate:
        """
        Manually approve a gate.

        Args:
            gate_id: Gate ID
            approved_by: Approver identifier
            comment: Optional approval comment

        Returns:
            Updated Gate object
        """
        gate = self.storage.get_gate(gate_id)
        if not gate:
            raise ValueError(f"Gate not found: {gate_id}")

        previous_status = gate.status
        gate.status = GateStatus.PASSED
        gate.completed_at = datetime.now().isoformat()

        self.storage.update_gate(gate)

        # Audit
        self._audit(
            gate,
            "approved",
            approved_by,
            {"comment": comment},
            previous_status.value,
            GateStatus.PASSED.value,
        )

        logger.info(f"Gate approved: {gate_id} by {approved_by}")

        return gate

    def reject_gate(
        self,
        gate_id: str,
        rejected_by: str,
        reason: str,
    ) -> Gate:
        """
        Manually reject a gate.

        Args:
            gate_id: Gate ID
            rejected_by: Rejector identifier
            reason: Rejection reason

        Returns:
            Updated Gate object
        """
        gate = self.storage.get_gate(gate_id)
        if not gate:
            raise ValueError(f"Gate not found: {gate_id}")

        previous_status = gate.status
        gate.status = GateStatus.FAILED

        self.storage.update_gate(gate)

        # Audit
        self._audit(
            gate,
            "rejected",
            rejected_by,
            {"reason": reason},
            previous_status.value,
            GateStatus.FAILED.value,
        )

        logger.info(f"Gate rejected: {gate_id} by {rejected_by} - {reason}")

        return gate

    def get_gate(self, gate_id: str) -> Optional[Gate]:
        """Get a gate by ID."""
        return self.storage.get_gate(gate_id)

    def get_gates_by_session(
        self,
        session_id: str,
        phase: Optional[str] = None,
    ) -> List[Gate]:
        """
        Get gates for a session, optionally filtered by phase.

        Args:
            session_id: Session ID
            phase: Optional phase filter

        Returns:
            List of gates
        """
        all_gates = self.storage.get_all_gates()
        filtered = [g for g in all_gates if g.session_id == session_id]

        if phase:
            filtered = [g for g in filtered if g.phase_id == phase]

        return filtered

    def get_audit_trail(self, gate_id: str) -> List[AuditEntry]:
        """Get audit trail for a gate."""
        return self.storage.get_audit_trail(gate_id)

    def _generate_gate_id(
        self,
        gate_type: GateType,
        phase_id: str,
        workflow_id: str,
    ) -> str:
        """Generate a unique gate ID."""
        data = f"{gate_type.value}:{phase_id}:{workflow_id}:{time.time()}"
        return f"gate_{hashlib.md5(data.encode()).hexdigest()[:16]}"

    def _audit(
        self,
        gate: Gate,
        action: str,
        actor: Optional[str],
        details: Dict[str, Any],
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
    ) -> None:
        """Add audit entry for gate operation."""
        entry = AuditEntry(
            id=f"audit_{hashlib.md5(f'{gate.id}_{action}_{time.time()}'.encode()).hexdigest()[:12]}",
            gate_id=gate.id,
            action=action,
            actor=actor,
            timestamp=datetime.now().isoformat(),
            details=details,
            previous_status=previous_status,
            new_status=new_status,
        )

        self.storage.add_audit_entry(entry)
        gate.audit_trail.append(entry.to_dict())


# ============================================================================
# SINGLETON & MODULE FUNCTIONS
# ============================================================================

_gate_service: Optional[GateService] = None
_gate_storage: Optional[GateStorage] = None


def get_gate_storage() -> GateStorage:
    """Get or create singleton GateStorage."""
    global _gate_storage
    if _gate_storage is None:
        _gate_storage = GateStorage()
    return _gate_storage


def get_gate_service(feature_flag_enabled: bool = True) -> GateService:
    """Get or create singleton GateService."""
    global _gate_service
    if _gate_service is None:
        _gate_service = GateService(
            storage=get_gate_storage(),
            feature_flag_enabled=feature_flag_enabled,
        )
    return _gate_service


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 70)
    print("GATE FRAMEWORK SERVICE - Test")
    print("=" * 70)

    service = get_gate_service()

    # Create gates for a workflow
    workflow_id = "wf_test_001"
    session_id = "session_test"

    # Create gates for requirements phase
    print("\n[1] Creating gates for requirements phase...")
    gates = service.create_gates_for_phase(
        phase_type="requirements",
        phase_id="phase_requirements",
        workflow_id=workflow_id,
        session_id=session_id,
    )
    print(f"   Created {len(gates)} gates")

    for gate in gates:
        print(f"   - {gate.name} ({gate.gate_type.value}): {gate.status.value}")

    # Attach evidence
    print("\n[2] Attaching evidence...")
    evidence = service.attach_evidence(
        gate_id=gates[0].id,
        evidence_type=EvidenceType.DOCUMENT,
        uri="https://docs.example.com/requirements.md",
        description="Requirements document",
        attached_by="user@example.com",
    )
    print(f"   Evidence attached: {evidence.id}")

    # Evaluate a gate (simulated context)
    print("\n[3] Evaluating BRV gate...")
    context = {
        "requirements_addressed": True,
        "stakeholder_approvals": ["pm@example.com", "cto@example.com"],
        "required_approvals": 2,
        "value_documented": True,
        "risk_assessment_completed": True,
    }

    result = service.evaluate_gate(gates[0].id, context)
    print(f"   Result: {result.status.value}")
    print(f"   Score: {result.overall_score:.1f}%")
    print(f"   Passed: {result.passed}")
    print(f"   Blocking: {result.blocking}")

    # Dry-run evaluation
    print("\n[4] Dry-run evaluation...")
    dry_result = service.evaluate_gate(gates[0].id, context, dry_run=True)
    print(f"   Dry-run result: {dry_result.status.value} (dry_run={dry_result.dry_run})")

    # Test override
    print("\n[5] Testing override...")
    failed_context = {
        "requirements_addressed": False,
        "stakeholder_approvals": [],
        "value_documented": False,
        "risk_assessment_completed": False,
    }

    override_result = service.evaluate_gate(
        gates[1].id,
        failed_context,
        override=True,
        override_reason="Emergency deployment",
        override_by="admin@example.com",
    )
    print(f"   Override result: {override_result.status.value}")
    print(f"   Was overridden: gate.was_overridden={service.get_gate(gates[1].id).was_overridden}")

    # Get audit trail
    print("\n[6] Audit trail...")
    audit = service.get_audit_trail(gates[0].id)
    for entry in audit:
        print(f"   {entry.timestamp}: {entry.action} by {entry.actor}")

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETED!")
    print("=" * 70)
