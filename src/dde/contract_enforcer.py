#!/usr/bin/env python3
"""
ContractEnforcer - Interface Contract Validation

Prevents interface contract violations during execution.

MD-2101: [DDE-5] Add contract lockdown enforcement

Features:
- Input/output validation at node boundaries
- Drift detection with detailed diff
- Configurable enforcement modes (warn/soft/strict)
- Audit log for all violations
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)

# Optional Prometheus metrics
try:
    from prometheus_client import Counter, Histogram
    PROMETHEUS_AVAILABLE = True

    CONTRACT_VALIDATIONS = Counter(
        "dde_contract_validations_total",
        "Total contract validations",
        ["result", "enforcement_mode"]
    )
    DRIFT_DETECTIONS = Counter(
        "dde_contract_drift_total",
        "Contract drift detections",
        ["drift_type"]
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    CONTRACT_VALIDATIONS = None
    DRIFT_DETECTIONS = None


class EnforcementMode(Enum):
    """Contract enforcement modes."""
    WARN = "warn"       # Log violations but continue
    SOFT = "soft"       # Block on critical violations only
    STRICT = "strict"   # Block on any violation


class ValidationSeverity(Enum):
    """Severity of validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DriftType(Enum):
    """Types of contract drift."""
    FIELD_ADDED = "field_added"
    FIELD_REMOVED = "field_removed"
    TYPE_CHANGED = "type_changed"
    REQUIRED_CHANGED = "required_changed"
    VERSION_MISMATCH = "version_mismatch"


@dataclass
class ValidationIssue:
    """A single validation issue."""
    field_name: str
    issue_type: str
    severity: ValidationSeverity
    message: str
    expected_value: Any = None
    actual_value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "issue_type": self.issue_type,
            "severity": self.severity.value,
            "message": self.message,
            "expected_value": str(self.expected_value) if self.expected_value is not None else None,
            "actual_value": str(self.actual_value) if self.actual_value is not None else None,
        }


@dataclass
class ValidationResult:
    """Result of contract validation."""
    valid: bool
    node_id: str
    direction: str  # "input" or "output"
    issues: List[ValidationIssue] = field(default_factory=list)
    validated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def has_critical_issues(self) -> bool:
        return any(i.severity == ValidationSeverity.CRITICAL for i in self.issues)

    @property
    def has_errors(self) -> bool:
        return any(i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL) for i in self.issues)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "node_id": self.node_id,
            "direction": self.direction,
            "issues": [i.to_dict() for i in self.issues],
            "validated_at": self.validated_at.isoformat(),
            "has_critical_issues": self.has_critical_issues,
            "has_errors": self.has_errors,
        }


@dataclass
class Drift:
    """Detected contract drift."""
    drift_id: str
    node_id: str
    drift_type: DriftType
    field_name: Optional[str]
    expected: Any
    actual: Any
    detected_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drift_id": self.drift_id,
            "node_id": self.node_id,
            "drift_type": self.drift_type.value,
            "field_name": self.field_name,
            "expected": str(self.expected),
            "actual": str(self.actual),
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class ContractLock:
    """A locked contract version."""
    node_id: str
    version: str
    locked_at: datetime
    locked_by: str
    contract_hash: str


# Import from routing_engine for contract definitions
try:
    from .routing_engine import InterfaceContract, InterfaceField, FieldType
except ImportError:
    # Fallback definitions if not available
    from enum import Enum as EnumBase

    class FieldType(EnumBase):
        STRING = "string"
        NUMBER = "number"
        BOOLEAN = "boolean"
        OBJECT = "object"
        ARRAY = "array"
        FILE = "file"
        ANY = "any"

    @dataclass
    class InterfaceField:
        name: str
        field_type: FieldType
        required: bool = True
        description: Optional[str] = None
        default_value: Any = None

    @dataclass
    class InterfaceContract:
        node_id: str
        version: str
        required_inputs: List[InterfaceField] = field(default_factory=list)
        optional_inputs: List[InterfaceField] = field(default_factory=list)
        produced_outputs: List[InterfaceField] = field(default_factory=list)


class ContractEnforcer:
    """
    Enforces interface contracts at runtime.

    Provides:
    - Input/output validation at node boundaries
    - Drift detection with detailed diff
    - Configurable enforcement modes
    - Audit log for violations
    """

    def __init__(
        self,
        default_mode: EnforcementMode = EnforcementMode.SOFT,
        on_violation: Optional[Callable[[ValidationResult], None]] = None,
        on_drift: Optional[Callable[[Drift], None]] = None,
    ):
        self.default_mode = default_mode
        self._on_violation = on_violation
        self._on_drift = on_drift

        self._contracts: Dict[str, InterfaceContract] = {}
        self._locked_versions: Dict[str, ContractLock] = {}
        self._violation_history: List[ValidationResult] = []
        self._drift_history: List[Drift] = []
        self._node_modes: Dict[str, EnforcementMode] = {}

        logger.info(f"ContractEnforcer initialized with mode: {default_mode.value}")

    def register_contract(self, contract: InterfaceContract) -> None:
        """Register an interface contract."""
        self._contracts[contract.node_id] = contract
        logger.debug(f"Registered contract for {contract.node_id} v{contract.version}")

    def get_contract(self, node_id: str) -> Optional[InterfaceContract]:
        """Get contract for a node."""
        return self._contracts.get(node_id)

    def set_enforcement_mode(self, node_id: str, mode: EnforcementMode) -> None:
        """Set enforcement mode for a specific node."""
        self._node_modes[node_id] = mode

    def get_enforcement_mode(self, node_id: str) -> EnforcementMode:
        """Get enforcement mode for a node."""
        return self._node_modes.get(node_id, self.default_mode)

    def lock_contract(
        self,
        node_id: str,
        version: str,
        locked_by: str = "system",
    ) -> bool:
        """Lock a contract version to prevent changes."""
        contract = self._contracts.get(node_id)
        if not contract:
            logger.warning(f"Cannot lock - contract not found for {node_id}")
            return False

        if contract.version != version:
            logger.warning(f"Version mismatch: contract is {contract.version}, requested {version}")
            return False

        # Compute contract hash for integrity
        import hashlib
        import json
        contract_data = {
            "node_id": contract.node_id,
            "version": contract.version,
            "required_inputs": [f.name for f in contract.required_inputs],
            "produced_outputs": [f.name for f in contract.produced_outputs],
        }
        contract_hash = hashlib.sha256(json.dumps(contract_data, sort_keys=True).encode()).hexdigest()

        self._locked_versions[node_id] = ContractLock(
            node_id=node_id,
            version=version,
            locked_at=datetime.utcnow(),
            locked_by=locked_by,
            contract_hash=contract_hash,
        )

        logger.info(f"Contract locked: {node_id} v{version}")
        return True

    def get_locked_version(self, node_id: str) -> Optional[str]:
        """Get locked version for a node."""
        lock = self._locked_versions.get(node_id)
        return lock.version if lock else None

    def is_locked(self, node_id: str) -> bool:
        """Check if a contract is locked."""
        return node_id in self._locked_versions

    def validate_inputs(
        self,
        node_id: str,
        inputs: Dict[str, Any],
    ) -> ValidationResult:
        """Validate inputs against contract."""
        contract = self._contracts.get(node_id)
        issues = []

        if not contract:
            # No contract = no validation
            return ValidationResult(valid=True, node_id=node_id, direction="input")

        # Check required inputs
        for field in contract.required_inputs:
            if field.name not in inputs:
                if field.default_value is None:
                    issues.append(ValidationIssue(
                        field_name=field.name,
                        issue_type="missing_required",
                        severity=ValidationSeverity.ERROR,
                        message=f"Required input '{field.name}' is missing",
                        expected_value=f"<{field.field_type.value}>",
                        actual_value=None,
                    ))
            else:
                # Validate type
                value = inputs[field.name]
                if not self._validate_type(value, field.field_type):
                    issues.append(ValidationIssue(
                        field_name=field.name,
                        issue_type="type_mismatch",
                        severity=ValidationSeverity.ERROR,
                        message=f"Input '{field.name}' has wrong type",
                        expected_value=field.field_type.value,
                        actual_value=type(value).__name__,
                    ))

        # Check for unexpected inputs (warning only)
        expected_names = {f.name for f in contract.required_inputs + contract.optional_inputs}
        for key in inputs:
            if key not in expected_names:
                issues.append(ValidationIssue(
                    field_name=key,
                    issue_type="unexpected_input",
                    severity=ValidationSeverity.WARNING,
                    message=f"Unexpected input '{key}' not in contract",
                ))

        valid = not any(i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL) for i in issues)

        result = ValidationResult(
            valid=valid,
            node_id=node_id,
            direction="input",
            issues=issues,
        )

        self._handle_validation_result(result)
        return result

    def validate_outputs(
        self,
        node_id: str,
        outputs: Dict[str, Any],
    ) -> ValidationResult:
        """Validate outputs against contract."""
        contract = self._contracts.get(node_id)
        issues = []

        if not contract:
            return ValidationResult(valid=True, node_id=node_id, direction="output")

        # Check produced outputs
        for field in contract.produced_outputs:
            if field.name not in outputs:
                if field.required:
                    issues.append(ValidationIssue(
                        field_name=field.name,
                        issue_type="missing_output",
                        severity=ValidationSeverity.ERROR,
                        message=f"Required output '{field.name}' is missing",
                        expected_value=f"<{field.field_type.value}>",
                        actual_value=None,
                    ))
            else:
                value = outputs[field.name]
                if not self._validate_type(value, field.field_type):
                    issues.append(ValidationIssue(
                        field_name=field.name,
                        issue_type="type_mismatch",
                        severity=ValidationSeverity.ERROR,
                        message=f"Output '{field.name}' has wrong type",
                        expected_value=field.field_type.value,
                        actual_value=type(value).__name__,
                    ))

        valid = not any(i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL) for i in issues)

        result = ValidationResult(
            valid=valid,
            node_id=node_id,
            direction="output",
            issues=issues,
        )

        self._handle_validation_result(result)
        return result

    def _validate_type(self, value: Any, expected_type: FieldType) -> bool:
        """Validate value against expected type."""
        if expected_type == FieldType.ANY:
            return True

        type_map = {
            FieldType.STRING: str,
            FieldType.NUMBER: (int, float),
            FieldType.BOOLEAN: bool,
            FieldType.OBJECT: dict,
            FieldType.ARRAY: (list, tuple),
        }

        expected = type_map.get(expected_type, object)
        return isinstance(value, expected)

    def _handle_validation_result(self, result: ValidationResult) -> None:
        """Handle validation result based on enforcement mode."""
        if not result.valid:
            self._violation_history.append(result)

            mode = self.get_enforcement_mode(result.node_id)

            # Metrics
            if PROMETHEUS_AVAILABLE and CONTRACT_VALIDATIONS:
                CONTRACT_VALIDATIONS.labels(
                    result="invalid",
                    enforcement_mode=mode.value
                ).inc()

            # Callback
            if self._on_violation:
                self._on_violation(result)

            # Logging based on mode
            if mode == EnforcementMode.WARN:
                logger.warning(f"Contract violation (WARN mode): {result.node_id} - {len(result.issues)} issues")
            elif mode == EnforcementMode.SOFT and result.has_critical_issues:
                logger.error(f"Contract violation (SOFT mode, critical): {result.node_id}")
            elif mode == EnforcementMode.STRICT:
                logger.error(f"Contract violation (STRICT mode): {result.node_id}")
        else:
            if PROMETHEUS_AVAILABLE and CONTRACT_VALIDATIONS:
                CONTRACT_VALIDATIONS.labels(
                    result="valid",
                    enforcement_mode=self.get_enforcement_mode(result.node_id).value
                ).inc()

    def should_block(self, result: ValidationResult) -> bool:
        """Determine if execution should be blocked based on validation result."""
        if result.valid:
            return False

        mode = self.get_enforcement_mode(result.node_id)

        if mode == EnforcementMode.WARN:
            return False
        elif mode == EnforcementMode.SOFT:
            return result.has_critical_issues
        else:  # STRICT
            return result.has_errors

    def detect_drift(
        self,
        node_id: str,
        new_contract: InterfaceContract,
    ) -> List[Drift]:
        """Detect drift between registered and new contract."""
        old_contract = self._contracts.get(node_id)
        if not old_contract:
            return []

        drifts = []

        # Check version
        if old_contract.version != new_contract.version:
            drifts.append(Drift(
                drift_id=str(uuid4()),
                node_id=node_id,
                drift_type=DriftType.VERSION_MISMATCH,
                field_name=None,
                expected=old_contract.version,
                actual=new_contract.version,
            ))

        # Check inputs
        old_inputs = {f.name: f for f in old_contract.required_inputs}
        new_inputs = {f.name: f for f in new_contract.required_inputs}

        for name in old_inputs:
            if name not in new_inputs:
                drifts.append(Drift(
                    drift_id=str(uuid4()),
                    node_id=node_id,
                    drift_type=DriftType.FIELD_REMOVED,
                    field_name=name,
                    expected=f"input: {name}",
                    actual="<removed>",
                ))
            elif old_inputs[name].field_type != new_inputs[name].field_type:
                drifts.append(Drift(
                    drift_id=str(uuid4()),
                    node_id=node_id,
                    drift_type=DriftType.TYPE_CHANGED,
                    field_name=name,
                    expected=old_inputs[name].field_type.value,
                    actual=new_inputs[name].field_type.value,
                ))

        for name in new_inputs:
            if name not in old_inputs:
                drifts.append(Drift(
                    drift_id=str(uuid4()),
                    node_id=node_id,
                    drift_type=DriftType.FIELD_ADDED,
                    field_name=name,
                    expected="<none>",
                    actual=f"input: {name}",
                ))

        # Check outputs similarly
        old_outputs = {f.name: f for f in old_contract.produced_outputs}
        new_outputs = {f.name: f for f in new_contract.produced_outputs}

        for name in old_outputs:
            if name not in new_outputs:
                drifts.append(Drift(
                    drift_id=str(uuid4()),
                    node_id=node_id,
                    drift_type=DriftType.FIELD_REMOVED,
                    field_name=name,
                    expected=f"output: {name}",
                    actual="<removed>",
                ))

        for name in new_outputs:
            if name not in old_outputs:
                drifts.append(Drift(
                    drift_id=str(uuid4()),
                    node_id=node_id,
                    drift_type=DriftType.FIELD_ADDED,
                    field_name=name,
                    expected="<none>",
                    actual=f"output: {name}",
                ))

        # Store and handle drifts
        for drift in drifts:
            self._drift_history.append(drift)
            if PROMETHEUS_AVAILABLE and DRIFT_DETECTIONS:
                DRIFT_DETECTIONS.labels(drift_type=drift.drift_type.value).inc()
            if self._on_drift:
                self._on_drift(drift)

        if drifts:
            logger.warning(f"Detected {len(drifts)} contract drifts for {node_id}")

        return drifts

    def get_violation_history(
        self,
        node_id: Optional[str] = None,
    ) -> List[ValidationResult]:
        """Get violation history, optionally filtered by node."""
        if node_id:
            return [v for v in self._violation_history if v.node_id == node_id]
        return list(self._violation_history)

    def get_drift_history(
        self,
        node_id: Optional[str] = None,
    ) -> List[Drift]:
        """Get drift history, optionally filtered by node."""
        if node_id:
            return [d for d in self._drift_history if d.node_id == node_id]
        return list(self._drift_history)

    def get_stats(self) -> Dict[str, Any]:
        """Get enforcer statistics."""
        return {
            "contracts_registered": len(self._contracts),
            "contracts_locked": len(self._locked_versions),
            "total_violations": len(self._violation_history),
            "total_drifts": len(self._drift_history),
            "default_mode": self.default_mode.value,
        }

    def clear_history(self) -> None:
        """Clear violation and drift history."""
        self._violation_history.clear()
        self._drift_history.clear()
