"""
Block Promotion Pipeline for MD-2510

Implements the 4-level promotion system for blocks:
NEW -> SHARABLE -> CATALOGUED -> TRUSTED

Each transition requires:
1. Automated criteria validation
2. Human-in-the-loop approval gates
3. Audit trail tracking

Author: Maestro Platform Team
Created: 2025-12-06
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable
import hashlib
import json
import logging
import uuid

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS - AC-1: BlockStatus with 4 levels
# ============================================================================

class BlockStatus(str, Enum):
    """
    Block status levels for promotion pipeline.

    Each level represents increasing trust and reduced testing requirements:
    - NEW: Project-specific, full testing required, not reusable
    - SHARABLE: Pattern in 2+ projects, abstracted interface, pending review
    - CATALOGUED: Security reviewed, >90% coverage, contract tests defined
    - TRUSTED: 5+ production deployments, 30 days zero critical bugs
    """
    NEW = "new"
    SHARABLE = "sharable"
    CATALOGUED = "catalogued"
    TRUSTED = "trusted"


class ApproverRole(str, Enum):
    """Roles that can approve block promotions."""
    DEVELOPER = "developer"
    PEER = "peer"
    SECURITY_TEAM = "security_team"
    PLATFORM_LEAD = "platform_lead"
    PLATFORM_TEAM = "platform_team"


class ApprovalStatus(str, Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class GateResult(str, Enum):
    """Result of a promotion gate evaluation."""
    PASSED = "passed"
    FAILED = "failed"
    PENDING_APPROVAL = "pending_approval"
    SKIPPED = "skipped"


# ============================================================================
# DATA CLASSES - Core structures
# ============================================================================

@dataclass
class PromotionCriteria:
    """
    Criteria required for a specific promotion transition.

    Attributes:
        name: Human-readable name of the criterion
        description: Detailed description of what's being checked
        validator: Callable that returns (passed, details)
        required: Whether this criterion must pass
    """
    name: str
    description: str
    validator: Optional[Callable[[Dict[str, Any]], tuple]] = None
    required: bool = True
    weight: float = 1.0


@dataclass
class CriteriaResult:
    """Result of evaluating a single criterion."""
    criterion_name: str
    passed: bool
    details: str
    score: float = 0.0
    evaluated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class HumanApproval:
    """
    Record of a human approval for a promotion gate.

    Attributes:
        role: The role of the approver
        approver_id: Unique identifier of the approver
        approver_name: Human-readable name of the approver
        status: Current approval status
        notes: Optional notes from the approver
        approved_at: Timestamp when approval was given
        expires_at: When this approval request expires
    """
    role: ApproverRole
    approver_id: Optional[str] = None
    approver_name: Optional[str] = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    notes: Optional[str] = None
    approved_at: Optional[datetime] = None
    requested_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


@dataclass
class PromotionLevelConfig:
    """
    Configuration for a promotion level.

    Defines the requirements for entering this level.
    """
    status: BlockStatus
    description: str
    min_projects_used: int = 0
    min_coverage_percent: float = 0.0
    min_production_deployments: int = 0
    min_days_without_critical_bugs: int = 0
    required_approvers: List[ApproverRole] = field(default_factory=list)
    require_all_approvers: bool = True
    timeout_hours: int = 72


@dataclass
class GateEvaluation:
    """Complete evaluation result for a promotion gate."""
    gate_name: str
    from_status: BlockStatus
    to_status: BlockStatus
    criteria_results: List[CriteriaResult] = field(default_factory=list)
    human_approvals: List[HumanApproval] = field(default_factory=list)
    result: GateResult = GateResult.PENDING_APPROVAL
    score: float = 0.0
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""


@dataclass
class PromotionAttempt:
    """
    Record of a promotion attempt for audit trail.

    Attributes:
        attempt_id: Unique identifier for this attempt
        block_id: ID of the block being promoted
        block_version: Version of the block
        from_status: Starting status
        to_status: Target status
        requester_id: Who requested the promotion
        gate_evaluations: Results of gate checks
        success: Whether promotion succeeded
        failure_reason: Why promotion failed (if applicable)
    """
    attempt_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    block_id: str = ""
    block_version: str = ""
    from_status: BlockStatus = BlockStatus.NEW
    to_status: BlockStatus = BlockStatus.NEW
    requester_id: str = ""
    requester_name: str = ""
    gate_evaluations: List[GateEvaluation] = field(default_factory=list)
    success: bool = False
    failure_reason: Optional[str] = None
    is_emergency_override: bool = False
    override_justification: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class BlockInfo:
    """Information about a block for promotion evaluation."""
    block_id: str
    name: str
    version: str
    current_status: BlockStatus
    projects_used: int = 0
    test_coverage: float = 0.0
    production_deployments: int = 0
    days_without_critical_bugs: int = 0
    security_review_passed: bool = False
    contract_tests_defined: bool = False
    interface_abstracted: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# PROMOTION GATES - AC-2 & AC-3: Automated criteria + Human approval
# ============================================================================

class PromotionGate(ABC):
    """
    Abstract base class for promotion gates.

    Each gate handles the transition between two BlockStatus levels.
    Gates perform:
    1. Automated criteria validation
    2. Human approval collection
    3. Result aggregation
    """

    def __init__(self, from_status: BlockStatus, to_status: BlockStatus):
        """
        Initialize the promotion gate.

        Args:
            from_status: The starting status for this gate
            to_status: The target status after passing this gate
        """
        self.from_status = from_status
        self.to_status = to_status
        self.criteria: List[PromotionCriteria] = []
        self.required_approvers: List[ApproverRole] = []
        self.require_all_approvers: bool = True
        self._setup_criteria()
        self._setup_approvers()

    @abstractmethod
    def _setup_criteria(self) -> None:
        """Set up the automated criteria for this gate."""
        pass

    @abstractmethod
    def _setup_approvers(self) -> None:
        """Set up the required human approvers for this gate."""
        pass

    @property
    def gate_name(self) -> str:
        """Return the name of this gate."""
        return f"{self.from_status.value}_to_{self.to_status.value}"

    def evaluate_criteria(self, block_info: BlockInfo) -> List[CriteriaResult]:
        """
        Evaluate all automated criteria for the block.

        Args:
            block_info: Information about the block being evaluated

        Returns:
            List of CriteriaResult objects
        """
        results = []
        for criterion in self.criteria:
            if criterion.validator:
                try:
                    passed, details = criterion.validator(block_info.__dict__)
                except Exception as e:
                    passed, details = False, f"Validation error: {str(e)}"
            else:
                passed, details = True, "No validator defined"

            score = criterion.weight if passed else 0.0
            results.append(CriteriaResult(
                criterion_name=criterion.name,
                passed=passed,
                details=details,
                score=score
            ))

        return results

    def check_approvals(self, approvals: List[HumanApproval]) -> tuple:
        """
        Check if required approvals have been obtained.

        Args:
            approvals: List of human approvals received

        Returns:
            Tuple of (all_approved, missing_roles, rejected_by)
        """
        approved_roles = set()
        rejected_by = []

        for approval in approvals:
            if approval.status == ApprovalStatus.APPROVED:
                approved_roles.add(approval.role)
            elif approval.status == ApprovalStatus.REJECTED:
                rejected_by.append(approval.role)

        required_roles = set(self.required_approvers)
        missing_roles = required_roles - approved_roles

        if self.require_all_approvers:
            all_approved = len(missing_roles) == 0 and len(rejected_by) == 0
        else:
            # Majority rule
            approval_count = len(approved_roles & required_roles)
            required_count = len(required_roles)
            all_approved = approval_count > required_count / 2 and len(rejected_by) == 0

        return all_approved, list(missing_roles), rejected_by

    def evaluate(self, block_info: BlockInfo, approvals: List[HumanApproval]) -> GateEvaluation:
        """
        Perform complete gate evaluation.

        Args:
            block_info: Information about the block
            approvals: List of human approvals

        Returns:
            Complete GateEvaluation result
        """
        # Evaluate automated criteria
        criteria_results = self.evaluate_criteria(block_info)

        # Check if all required criteria passed
        required_passed = all(
            cr.passed for cr in criteria_results
            if any(c.name == cr.criterion_name and c.required for c in self.criteria)
        )

        # Calculate score
        total_weight = sum(c.weight for c in self.criteria) or 1
        score = sum(cr.score for cr in criteria_results) / total_weight * 100

        # Check human approvals
        all_approved, missing_roles, rejected_by = self.check_approvals(approvals)

        # Determine overall result
        if rejected_by:
            result = GateResult.FAILED
            notes = f"Rejected by: {', '.join(r.value for r in rejected_by)}"
        elif not required_passed:
            result = GateResult.FAILED
            failed_criteria = [cr.criterion_name for cr in criteria_results if not cr.passed]
            notes = f"Failed criteria: {', '.join(failed_criteria)}"
        elif missing_roles:
            result = GateResult.PENDING_APPROVAL
            notes = f"Awaiting approval from: {', '.join(r.value for r in missing_roles)}"
        elif all_approved:
            result = GateResult.PASSED
            notes = "All criteria and approvals satisfied"
        else:
            result = GateResult.PENDING_APPROVAL
            notes = "Awaiting human approvals"

        return GateEvaluation(
            gate_name=self.gate_name,
            from_status=self.from_status,
            to_status=self.to_status,
            criteria_results=criteria_results,
            human_approvals=approvals,
            result=result,
            score=score,
            notes=notes
        )


class NewToSharableGate(PromotionGate):
    """
    Gate for promoting blocks from NEW to SHARABLE.

    Requirements:
    - Pattern reused in 2+ projects
    - Abstracted interface defined
    - Approvals: Developer + 1 Peer
    """

    def __init__(self):
        super().__init__(BlockStatus.NEW, BlockStatus.SHARABLE)

    def _setup_criteria(self) -> None:
        """Set up criteria for NEW -> SHARABLE promotion."""
        self.criteria = [
            PromotionCriteria(
                name="projects_used",
                description="Pattern reused in 2+ projects",
                validator=lambda b: (
                    b.get("projects_used", 0) >= 2,
                    f"Used in {b.get('projects_used', 0)} projects (need 2+)"
                ),
                required=True,
                weight=2.0
            ),
            PromotionCriteria(
                name="interface_abstracted",
                description="Abstracted interface defined",
                validator=lambda b: (
                    b.get("interface_abstracted", False),
                    "Interface abstraction: " + ("defined" if b.get("interface_abstracted") else "not defined")
                ),
                required=True,
                weight=1.5
            ),
            PromotionCriteria(
                name="documentation",
                description="Basic documentation provided",
                validator=lambda b: (
                    b.get("metadata", {}).get("has_documentation", False),
                    "Documentation: " + ("present" if b.get("metadata", {}).get("has_documentation") else "missing")
                ),
                required=False,
                weight=0.5
            )
        ]

    def _setup_approvers(self) -> None:
        """Set up required approvers for NEW -> SHARABLE."""
        self.required_approvers = [
            ApproverRole.DEVELOPER,
            ApproverRole.PEER
        ]
        self.require_all_approvers = True


class SharableToCataloguedGate(PromotionGate):
    """
    Gate for promoting blocks from SHARABLE to CATALOGUED.

    Requirements:
    - Security review passed
    - Unit tests >90% coverage
    - Contract tests defined
    - Approvals: Security Team + Platform Lead
    """

    def __init__(self):
        super().__init__(BlockStatus.SHARABLE, BlockStatus.CATALOGUED)

    def _setup_criteria(self) -> None:
        """Set up criteria for SHARABLE -> CATALOGUED promotion."""
        self.criteria = [
            PromotionCriteria(
                name="security_review",
                description="Security review passed",
                validator=lambda b: (
                    b.get("security_review_passed", False),
                    "Security review: " + ("passed" if b.get("security_review_passed") else "not passed")
                ),
                required=True,
                weight=3.0
            ),
            PromotionCriteria(
                name="test_coverage",
                description="Unit tests >90% coverage",
                validator=lambda b: (
                    b.get("test_coverage", 0) >= 90,
                    f"Test coverage: {b.get('test_coverage', 0):.1f}% (need 90%+)"
                ),
                required=True,
                weight=2.0
            ),
            PromotionCriteria(
                name="contract_tests",
                description="Contract tests defined",
                validator=lambda b: (
                    b.get("contract_tests_defined", False),
                    "Contract tests: " + ("defined" if b.get("contract_tests_defined") else "not defined")
                ),
                required=True,
                weight=2.0
            ),
            PromotionCriteria(
                name="interface_stable",
                description="Interface marked as stable",
                validator=lambda b: (
                    b.get("metadata", {}).get("interface_stable", False),
                    "Interface stability: " + ("stable" if b.get("metadata", {}).get("interface_stable") else "unstable")
                ),
                required=False,
                weight=1.0
            )
        ]

    def _setup_approvers(self) -> None:
        """Set up required approvers for SHARABLE -> CATALOGUED."""
        self.required_approvers = [
            ApproverRole.SECURITY_TEAM,
            ApproverRole.PLATFORM_LEAD
        ]
        self.require_all_approvers = True


class CataloguedToTrustedGate(PromotionGate):
    """
    Gate for promoting blocks from CATALOGUED to TRUSTED.

    Requirements:
    - 5+ production deployments
    - 30 days zero critical bugs
    - SLA guarantee defined
    - Approvals: Platform Team (2+ members)
    """

    def __init__(self):
        super().__init__(BlockStatus.CATALOGUED, BlockStatus.TRUSTED)

    def _setup_criteria(self) -> None:
        """Set up criteria for CATALOGUED -> TRUSTED promotion."""
        self.criteria = [
            PromotionCriteria(
                name="production_deployments",
                description="5+ production deployments",
                validator=lambda b: (
                    b.get("production_deployments", 0) >= 5,
                    f"Production deployments: {b.get('production_deployments', 0)} (need 5+)"
                ),
                required=True,
                weight=3.0
            ),
            PromotionCriteria(
                name="days_without_bugs",
                description="30 days zero critical bugs",
                validator=lambda b: (
                    b.get("days_without_critical_bugs", 0) >= 30,
                    f"Days without critical bugs: {b.get('days_without_critical_bugs', 0)} (need 30+)"
                ),
                required=True,
                weight=3.0
            ),
            PromotionCriteria(
                name="sla_defined",
                description="SLA guarantee defined (99.9%)",
                validator=lambda b: (
                    b.get("metadata", {}).get("sla_defined", False),
                    "SLA: " + ("defined" if b.get("metadata", {}).get("sla_defined") else "not defined")
                ),
                required=True,
                weight=2.0
            ),
            PromotionCriteria(
                name="platform_maintained",
                description="Platform team maintenance commitment",
                validator=lambda b: (
                    b.get("metadata", {}).get("platform_maintained", False),
                    "Platform maintenance: " + ("committed" if b.get("metadata", {}).get("platform_maintained") else "not committed")
                ),
                required=False,
                weight=1.0
            )
        ]

    def _setup_approvers(self) -> None:
        """Set up required approvers for CATALOGUED -> TRUSTED."""
        self.required_approvers = [
            ApproverRole.PLATFORM_TEAM,
            ApproverRole.PLATFORM_TEAM  # 2 platform team members
        ]
        self.require_all_approvers = False  # Majority rule for platform team


# ============================================================================
# PROMOTION HISTORY - AC-4: Audit trail tracking
# ============================================================================

class PromotionHistoryTracker:
    """
    Tracks all promotion attempts for audit trail.

    Provides:
    - Recording of all promotion attempts
    - Query by block, status, date range
    - Statistics on promotion success rates
    """

    def __init__(self):
        """Initialize the history tracker."""
        self._history: Dict[str, List[PromotionAttempt]] = {}
        self._by_id: Dict[str, PromotionAttempt] = {}

    def record_attempt(self, attempt: PromotionAttempt) -> None:
        """
        Record a promotion attempt.

        Args:
            attempt: The PromotionAttempt to record
        """
        if attempt.block_id not in self._history:
            self._history[attempt.block_id] = []

        self._history[attempt.block_id].append(attempt)
        self._by_id[attempt.attempt_id] = attempt

        logger.info(
            f"Recorded promotion attempt {attempt.attempt_id} for block {attempt.block_id}: "
            f"{attempt.from_status.value} -> {attempt.to_status.value} "
            f"({'success' if attempt.success else 'failed'})"
        )

    def get_by_id(self, attempt_id: str) -> Optional[PromotionAttempt]:
        """Get a specific attempt by ID."""
        return self._by_id.get(attempt_id)

    def get_by_block(self, block_id: str) -> List[PromotionAttempt]:
        """Get all attempts for a specific block."""
        return self._history.get(block_id, [])

    def get_successful_promotions(self, block_id: str) -> List[PromotionAttempt]:
        """Get all successful promotions for a block."""
        return [a for a in self.get_by_block(block_id) if a.success]

    def get_failed_promotions(self, block_id: str) -> List[PromotionAttempt]:
        """Get all failed promotions for a block."""
        return [a for a in self.get_by_block(block_id) if not a.success]

    def get_emergency_overrides(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[PromotionAttempt]:
        """
        Get all emergency override promotions within a date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of emergency override attempts
        """
        overrides = []
        for attempts in self._history.values():
            for attempt in attempts:
                if not attempt.is_emergency_override:
                    continue
                if start_date and attempt.started_at < start_date:
                    continue
                if end_date and attempt.started_at > end_date:
                    continue
                overrides.append(attempt)

        return sorted(overrides, key=lambda a: a.started_at)

    def get_statistics(self, block_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get promotion statistics.

        Args:
            block_id: Optional block ID to filter by

        Returns:
            Dictionary with statistics
        """
        if block_id:
            attempts = self.get_by_block(block_id)
        else:
            attempts = list(self._by_id.values())

        if not attempts:
            return {
                "total_attempts": 0,
                "success_rate": 0.0,
                "by_transition": {}
            }

        successful = sum(1 for a in attempts if a.success)
        by_transition: Dict[str, Dict[str, int]] = {}

        for attempt in attempts:
            key = f"{attempt.from_status.value}->{attempt.to_status.value}"
            if key not in by_transition:
                by_transition[key] = {"total": 0, "success": 0, "failed": 0}
            by_transition[key]["total"] += 1
            if attempt.success:
                by_transition[key]["success"] += 1
            else:
                by_transition[key]["failed"] += 1

        return {
            "total_attempts": len(attempts),
            "successful": successful,
            "failed": len(attempts) - successful,
            "success_rate": successful / len(attempts) * 100,
            "emergency_overrides": sum(1 for a in attempts if a.is_emergency_override),
            "by_transition": by_transition
        }


# ============================================================================
# BLOCK PROMOTION PIPELINE - Main orchestrator
# ============================================================================

class BlockPromotionPipeline:
    """
    Main orchestrator for the block promotion pipeline.

    Handles:
    - Sequential promotion through levels
    - Gate evaluation and approval management
    - Emergency override capability (AC-5)
    - History tracking for audit
    """

    # Define the promotion order
    PROMOTION_ORDER = [
        BlockStatus.NEW,
        BlockStatus.SHARABLE,
        BlockStatus.CATALOGUED,
        BlockStatus.TRUSTED
    ]

    def __init__(self):
        """Initialize the promotion pipeline."""
        self.gates: Dict[str, PromotionGate] = {
            "new_to_sharable": NewToSharableGate(),
            "sharable_to_catalogued": SharableToCataloguedGate(),
            "catalogued_to_trusted": CataloguedToTrustedGate()
        }
        self.history = PromotionHistoryTracker()
        self._pending_approvals: Dict[str, PromotionAttempt] = {}

    def get_next_status(self, current_status: BlockStatus) -> Optional[BlockStatus]:
        """
        Get the next status in the promotion chain.

        Args:
            current_status: The current block status

        Returns:
            The next status, or None if already at TRUSTED
        """
        try:
            current_index = self.PROMOTION_ORDER.index(current_status)
            if current_index < len(self.PROMOTION_ORDER) - 1:
                return self.PROMOTION_ORDER[current_index + 1]
        except ValueError:
            pass
        return None

    def get_gate(self, from_status: BlockStatus, to_status: BlockStatus) -> Optional[PromotionGate]:
        """
        Get the gate for a specific transition.

        Args:
            from_status: Starting status
            to_status: Target status

        Returns:
            The PromotionGate for this transition, or None
        """
        gate_key = f"{from_status.value}_to_{to_status.value}"
        return self.gates.get(gate_key)

    def can_promote(self, block_info: BlockInfo, to_status: BlockStatus) -> tuple:
        """
        Check if a block can be promoted to the specified status.

        Args:
            block_info: Information about the block
            to_status: Target status

        Returns:
            Tuple of (can_promote, reason)
        """
        current = block_info.current_status

        # Check if already at or past target
        try:
            current_idx = self.PROMOTION_ORDER.index(current)
            target_idx = self.PROMOTION_ORDER.index(to_status)
        except ValueError:
            return False, "Invalid status"

        if current_idx >= target_idx:
            return False, f"Block is already at {current.value} (target: {to_status.value})"

        # Check if trying to skip levels
        if target_idx > current_idx + 1:
            return False, "Cannot skip promotion levels"

        # Get the gate and check basic criteria
        gate = self.get_gate(current, to_status)
        if not gate:
            return False, f"No gate defined for {current.value} -> {to_status.value}"

        return True, "Promotion possible"

    def request_promotion(
        self,
        block_info: BlockInfo,
        requester_id: str,
        requester_name: str
    ) -> PromotionAttempt:
        """
        Request a promotion to the next level.

        Args:
            block_info: Information about the block
            requester_id: ID of the requester
            requester_name: Name of the requester

        Returns:
            PromotionAttempt object tracking this request
        """
        next_status = self.get_next_status(block_info.current_status)
        if not next_status:
            attempt = PromotionAttempt(
                block_id=block_info.block_id,
                block_version=block_info.version,
                from_status=block_info.current_status,
                to_status=block_info.current_status,
                requester_id=requester_id,
                requester_name=requester_name,
                success=False,
                failure_reason="Block is already at TRUSTED level",
                completed_at=datetime.utcnow()
            )
            self.history.record_attempt(attempt)
            return attempt

        can_promote, reason = self.can_promote(block_info, next_status)
        if not can_promote:
            attempt = PromotionAttempt(
                block_id=block_info.block_id,
                block_version=block_info.version,
                from_status=block_info.current_status,
                to_status=next_status,
                requester_id=requester_id,
                requester_name=requester_name,
                success=False,
                failure_reason=reason,
                completed_at=datetime.utcnow()
            )
            self.history.record_attempt(attempt)
            return attempt

        # Create the promotion attempt
        attempt = PromotionAttempt(
            block_id=block_info.block_id,
            block_version=block_info.version,
            from_status=block_info.current_status,
            to_status=next_status,
            requester_id=requester_id,
            requester_name=requester_name
        )

        # Evaluate the gate with empty approvals (initial evaluation)
        gate = self.get_gate(block_info.current_status, next_status)
        evaluation = gate.evaluate(block_info, [])
        attempt.gate_evaluations.append(evaluation)

        if evaluation.result == GateResult.FAILED:
            attempt.success = False
            attempt.failure_reason = evaluation.notes
            attempt.completed_at = datetime.utcnow()
        elif evaluation.result == GateResult.PENDING_APPROVAL:
            # Store for later approval processing
            self._pending_approvals[attempt.attempt_id] = attempt

        self.history.record_attempt(attempt)
        return attempt

    def submit_approval(
        self,
        attempt_id: str,
        approver_role: ApproverRole,
        approver_id: str,
        approver_name: str,
        approved: bool,
        notes: Optional[str] = None
    ) -> Optional[PromotionAttempt]:
        """
        Submit an approval for a pending promotion.

        Args:
            attempt_id: ID of the promotion attempt
            approver_role: Role of the approver
            approver_id: ID of the approver
            approver_name: Name of the approver
            approved: Whether the promotion is approved
            notes: Optional notes from the approver

        Returns:
            Updated PromotionAttempt, or None if not found
        """
        attempt = self._pending_approvals.get(attempt_id)
        if not attempt:
            return None

        # Create the approval
        approval = HumanApproval(
            role=approver_role,
            approver_id=approver_id,
            approver_name=approver_name,
            status=ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED,
            notes=notes,
            approved_at=datetime.utcnow()
        )

        # Add to the latest gate evaluation
        if attempt.gate_evaluations:
            attempt.gate_evaluations[-1].human_approvals.append(approval)

            # Re-evaluate the gate with the new approval
            gate = self.get_gate(attempt.from_status, attempt.to_status)
            if gate:
                # Create BlockInfo from attempt (simplified)
                block_info = BlockInfo(
                    block_id=attempt.block_id,
                    name=attempt.block_id,
                    version=attempt.block_version,
                    current_status=attempt.from_status
                )

                all_approvals = attempt.gate_evaluations[-1].human_approvals
                all_approved, missing, rejected = gate.check_approvals(all_approvals)

                if rejected:
                    attempt.gate_evaluations[-1].result = GateResult.FAILED
                    attempt.gate_evaluations[-1].notes = f"Rejected by: {', '.join(r.value for r in rejected)}"
                    attempt.success = False
                    attempt.failure_reason = attempt.gate_evaluations[-1].notes
                    attempt.completed_at = datetime.utcnow()
                    del self._pending_approvals[attempt_id]
                elif all_approved:
                    attempt.gate_evaluations[-1].result = GateResult.PASSED
                    attempt.gate_evaluations[-1].notes = "All approvals received"
                    attempt.success = True
                    attempt.completed_at = datetime.utcnow()
                    del self._pending_approvals[attempt_id]
                else:
                    attempt.gate_evaluations[-1].notes = f"Awaiting: {', '.join(r.value for r in missing)}"

        return attempt

    def emergency_override(
        self,
        block_info: BlockInfo,
        target_status: BlockStatus,
        platform_lead_id: str,
        platform_lead_name: str,
        justification: str
    ) -> PromotionAttempt:
        """
        Emergency override promotion to TRUSTED (AC-5).

        Only Platform Lead can perform this action.
        All overrides are logged with justification.

        Args:
            block_info: Information about the block
            target_status: Must be TRUSTED
            platform_lead_id: ID of the platform lead
            platform_lead_name: Name of the platform lead
            justification: Documented justification for override

        Returns:
            PromotionAttempt recording this override
        """
        if target_status != BlockStatus.TRUSTED:
            attempt = PromotionAttempt(
                block_id=block_info.block_id,
                block_version=block_info.version,
                from_status=block_info.current_status,
                to_status=target_status,
                requester_id=platform_lead_id,
                requester_name=platform_lead_name,
                success=False,
                failure_reason="Emergency override only allowed for TRUSTED status",
                is_emergency_override=True,
                override_justification=justification,
                completed_at=datetime.utcnow()
            )
            self.history.record_attempt(attempt)
            return attempt

        if not justification or len(justification) < 20:
            attempt = PromotionAttempt(
                block_id=block_info.block_id,
                block_version=block_info.version,
                from_status=block_info.current_status,
                to_status=target_status,
                requester_id=platform_lead_id,
                requester_name=platform_lead_name,
                success=False,
                failure_reason="Justification must be at least 20 characters",
                is_emergency_override=True,
                override_justification=justification,
                completed_at=datetime.utcnow()
            )
            self.history.record_attempt(attempt)
            return attempt

        # Create successful emergency override
        attempt = PromotionAttempt(
            block_id=block_info.block_id,
            block_version=block_info.version,
            from_status=block_info.current_status,
            to_status=BlockStatus.TRUSTED,
            requester_id=platform_lead_id,
            requester_name=platform_lead_name,
            success=True,
            is_emergency_override=True,
            override_justification=justification,
            completed_at=datetime.utcnow()
        )

        # Add gate evaluation noting the override
        attempt.gate_evaluations.append(GateEvaluation(
            gate_name="emergency_override",
            from_status=block_info.current_status,
            to_status=BlockStatus.TRUSTED,
            result=GateResult.PASSED,
            notes=f"Emergency override by {platform_lead_name}: {justification}"
        ))

        logger.warning(
            f"EMERGENCY OVERRIDE: Block {block_info.block_id} promoted to TRUSTED "
            f"by {platform_lead_name}. Justification: {justification}"
        )

        self.history.record_attempt(attempt)
        return attempt

    def get_quarterly_override_report(
        self,
        quarter_start: datetime,
        quarter_end: datetime
    ) -> Dict[str, Any]:
        """
        Generate quarterly report of emergency overrides (AC-5).

        Args:
            quarter_start: Start of the quarter
            quarter_end: End of the quarter

        Returns:
            Report dictionary
        """
        overrides = self.history.get_emergency_overrides(quarter_start, quarter_end)

        return {
            "quarter_start": quarter_start.isoformat(),
            "quarter_end": quarter_end.isoformat(),
            "total_overrides": len(overrides),
            "successful_overrides": sum(1 for o in overrides if o.success),
            "overrides": [
                {
                    "attempt_id": o.attempt_id,
                    "block_id": o.block_id,
                    "requester": o.requester_name,
                    "justification": o.override_justification,
                    "timestamp": o.started_at.isoformat(),
                    "success": o.success
                }
                for o in overrides
            ]
        }

    def get_pending_approvals(self) -> List[PromotionAttempt]:
        """Get all promotion attempts awaiting approval."""
        return list(self._pending_approvals.values())

    def get_promotion_status(self, attempt_id: str) -> Optional[PromotionAttempt]:
        """Get the status of a specific promotion attempt."""
        # Check pending first
        if attempt_id in self._pending_approvals:
            return self._pending_approvals[attempt_id]
        # Then check history
        return self.history.get_by_id(attempt_id)


# ============================================================================
# CRITERIA VALIDATORS - Helper functions
# ============================================================================

def create_default_criteria_validators() -> Dict[str, Callable]:
    """Create default validators for common criteria."""
    return {
        "projects_used": lambda b, min_count: (
            b.get("projects_used", 0) >= min_count,
            f"Used in {b.get('projects_used', 0)} projects (need {min_count}+)"
        ),
        "test_coverage": lambda b, min_coverage: (
            b.get("test_coverage", 0) >= min_coverage,
            f"Coverage: {b.get('test_coverage', 0):.1f}% (need {min_coverage}%+)"
        ),
        "production_deployments": lambda b, min_deployments: (
            b.get("production_deployments", 0) >= min_deployments,
            f"Deployments: {b.get('production_deployments', 0)} (need {min_deployments}+)"
        ),
        "security_review": lambda b, _: (
            b.get("security_review_passed", False),
            "Security review: " + ("passed" if b.get("security_review_passed") else "not passed")
        )
    }


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "BlockStatus",
    "ApproverRole",
    "ApprovalStatus",
    "GateResult",
    # Data classes
    "PromotionCriteria",
    "CriteriaResult",
    "HumanApproval",
    "PromotionLevelConfig",
    "GateEvaluation",
    "PromotionAttempt",
    "BlockInfo",
    # Gates
    "PromotionGate",
    "NewToSharableGate",
    "SharableToCataloguedGate",
    "CataloguedToTrustedGate",
    # Main classes
    "PromotionHistoryTracker",
    "BlockPromotionPipeline",
    # Utilities
    "create_default_criteria_validators",
]
