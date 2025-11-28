#!/usr/bin/env python3
"""
Comprehensive Audit Trail Service for MAESTRO Engine

Provides immutable audit logging for decisions, overrides, and governance.
TC-ORCH-021: Comprehensive audit trail for decisions and overrides

Features:
- Immutable audit records with cryptographic integrity
- Decision tracking (ML routes, user overrides, approvals)
- Evidence pack export for compliance
- Reason codes and justifications
- Query and reporting capabilities
"""

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Optional Prometheus metrics
try:
    from prometheus_client import Counter, Histogram
    PROMETHEUS_AVAILABLE = True

    # Module-level metrics (registered once)
    _AUDIT_EVENTS_COUNTER = Counter(
        "audit_trail_events_total",
        "Total audit events recorded",
        ["event_type", "category"]
    )
    _AUDIT_QUERY_HISTOGRAM = Histogram(
        "audit_trail_query_duration_seconds",
        "Audit query duration",
        ["query_type"]
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    _AUDIT_EVENTS_COUNTER = None
    _AUDIT_QUERY_HISTOGRAM = None


class AuditEventType(Enum):
    """Types of audit events."""
    # Routing decisions
    ML_ROUTE_DECISION = "ml_route_decision"
    USER_ROUTE_OVERRIDE = "user_route_override"
    EXECUTION_PATH_SELECTED = "execution_path_selected"

    # Team composition
    TEAM_COMPOSITION_PROPOSED = "team_composition_proposed"
    TEAM_COMPOSITION_OVERRIDE = "team_composition_override"
    TEAM_MEMBER_ADDED = "team_member_added"
    TEAM_MEMBER_REMOVED = "team_member_removed"

    # Phase management
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PHASE_ROLLBACK = "phase_rollback"
    GATE_CHECK_PASSED = "gate_check_passed"
    GATE_CHECK_FAILED = "gate_check_failed"

    # Approvals
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    APPROVAL_TIMEOUT = "approval_timeout"

    # Access control
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGED = "permission_changed"

    # Data governance
    DATA_ACCESSED = "data_accessed"
    DATA_EXPORTED = "data_exported"
    PII_REDACTED = "pii_redacted"

    # System events
    CONFIG_CHANGED = "config_changed"
    POLICY_APPLIED = "policy_applied"
    SECURITY_EVENT = "security_event"


class AuditCategory(Enum):
    """Categories for audit events."""
    ROUTING = "routing"
    TEAM = "team"
    PHASE = "phase"
    APPROVAL = "approval"
    ACCESS = "access"
    DATA = "data"
    SYSTEM = "system"
    SECURITY = "security"


class ReasonCode(Enum):
    """Standard reason codes for decisions."""
    # ML routing reasons
    ML_CONFIDENCE_HIGH = "ml_confidence_high"
    ML_CONFIDENCE_LOW = "ml_confidence_low"
    POLICY_CONSTRAINT = "policy_constraint"
    USER_PREFERENCE = "user_preference"

    # Override reasons
    MANUAL_OVERRIDE = "manual_override"
    ESCALATION = "escalation"
    EMERGENCY = "emergency"
    TESTING = "testing"

    # Approval reasons
    REQUIREMENTS_MET = "requirements_met"
    REQUIREMENTS_NOT_MET = "requirements_not_met"
    INSUFFICIENT_INFO = "insufficient_info"
    TIMEOUT_EXCEEDED = "timeout_exceeded"

    # Security reasons
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_FAILURE = "authorization_failure"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


@dataclass
class AuditEvent:
    """Immutable audit event record."""
    event_id: str
    event_type: AuditEventType
    category: AuditCategory
    timestamp: datetime

    # Actor information
    actor_id: str
    actor_type: str  # user, system, ml_model, service
    actor_name: Optional[str] = None

    # Context
    workflow_id: Optional[str] = None
    phase_id: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None

    # Decision details
    decision: Optional[str] = None
    reason_code: Optional[ReasonCode] = None
    justification: Optional[str] = None

    # Before/after state
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None

    # Additional data
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    # Integrity
    checksum: Optional[str] = None
    previous_checksum: Optional[str] = None

    def compute_checksum(self, previous_checksum: Optional[str] = None) -> str:
        """Compute cryptographic checksum for integrity."""
        data = {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "actor_id": self.actor_id,
            "decision": self.decision,
            "previous_checksum": previous_checksum or "",
        }
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["category"] = self.category.value
        data["timestamp"] = self.timestamp.isoformat()
        if self.reason_code:
            data["reason_code"] = self.reason_code.value
        data["previous_state"] = json.dumps(self.previous_state) if self.previous_state else None
        data["new_state"] = json.dumps(self.new_state) if self.new_state else None
        data["metadata"] = json.dumps(self.metadata)
        data["tags"] = json.dumps(self.tags)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEvent":
        """Create from dictionary."""
        data = data.copy()
        data["event_type"] = AuditEventType(data["event_type"])
        data["category"] = AuditCategory(data["category"])
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if data.get("reason_code"):
            data["reason_code"] = ReasonCode(data["reason_code"])
        if isinstance(data.get("previous_state"), str):
            data["previous_state"] = json.loads(data["previous_state"]) if data["previous_state"] else None
        if isinstance(data.get("new_state"), str):
            data["new_state"] = json.loads(data["new_state"]) if data["new_state"] else None
        if isinstance(data.get("metadata"), str):
            data["metadata"] = json.loads(data["metadata"])
        if isinstance(data.get("tags"), str):
            data["tags"] = json.loads(data["tags"])
        return cls(**data)


@dataclass
class EvidencePack:
    """Evidence pack for compliance export."""
    pack_id: str
    created_at: datetime
    created_by: str
    description: str

    # Scope
    workflow_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Contents
    events: List[AuditEvent] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    # Integrity
    checksum: Optional[str] = None

    def compute_checksum(self) -> str:
        """Compute checksum for entire evidence pack."""
        data = {
            "pack_id": self.pack_id,
            "created_at": self.created_at.isoformat(),
            "event_count": len(self.events),
            "event_checksums": [e.checksum for e in self.events],
        }
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


class AuditTrailService:
    """
    Comprehensive audit trail with immutable records.

    Features:
    - SQLite persistence with integrity chain
    - Cryptographic checksums for tamper detection
    - Rich querying capabilities
    - Evidence pack export
    """

    def __init__(self, db_path: str = "audit_trail.db"):
        self.db_path = db_path

        # In-memory cache for recent events
        self._recent_events: List[AuditEvent] = []
        self._max_cache_size = 1000

        # Last checksum for chain integrity
        self._last_checksum: Optional[str] = None

        # Callbacks
        self._on_event: Optional[Callable[[AuditEvent], None]] = None

        # Initialize database
        self._init_database()

        # Load last checksum
        self._load_last_checksum()

    def _init_database(self) -> None:
        """Initialize SQLite database with schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Audit events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                category TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor_name TEXT,
                workflow_id TEXT,
                phase_id TEXT,
                session_id TEXT,
                correlation_id TEXT,
                decision TEXT,
                reason_code TEXT,
                justification TEXT,
                previous_state TEXT,
                new_state TEXT,
                metadata TEXT,
                tags TEXT,
                checksum TEXT NOT NULL,
                previous_checksum TEXT
            )
        """)

        # Evidence packs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence_packs (
                pack_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                description TEXT NOT NULL,
                workflow_id TEXT,
                start_time TEXT,
                end_time TEXT,
                event_ids TEXT NOT NULL,
                summary TEXT,
                checksum TEXT NOT NULL
            )
        """)

        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_category ON audit_events(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_workflow ON audit_events(workflow_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_events(actor_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_correlation ON audit_events(correlation_id)")

        conn.commit()
        conn.close()

        logger.info(f"Audit trail database initialized: {self.db_path}")

    def _load_last_checksum(self) -> None:
        """Load the last checksum from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT checksum FROM audit_events ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()

        if row:
            self._last_checksum = row[0]

    def record(
        self,
        event_type: AuditEventType,
        actor_id: str,
        actor_type: str,
        category: Optional[AuditCategory] = None,
        actor_name: Optional[str] = None,
        workflow_id: Optional[str] = None,
        phase_id: Optional[str] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        decision: Optional[str] = None,
        reason_code: Optional[ReasonCode] = None,
        justification: Optional[str] = None,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> AuditEvent:
        """
        Record an audit event.

        Args:
            event_type: Type of event
            actor_id: ID of actor (user, system, etc.)
            actor_type: Type of actor
            category: Event category (inferred from type if not provided)
            actor_name: Human-readable actor name
            workflow_id: Associated workflow
            phase_id: Associated phase
            session_id: Session identifier
            correlation_id: Correlation ID for tracing
            decision: Decision made
            reason_code: Standard reason code
            justification: Human-readable justification
            previous_state: State before event
            new_state: State after event
            metadata: Additional metadata
            tags: Tags for filtering

        Returns:
            The recorded AuditEvent
        """
        # Infer category from event type if not provided
        if category is None:
            category = self._infer_category(event_type)

        event = AuditEvent(
            event_id=f"audit_{uuid4().hex[:12]}",
            event_type=event_type,
            category=category,
            timestamp=datetime.utcnow(),
            actor_id=actor_id,
            actor_type=actor_type,
            actor_name=actor_name,
            workflow_id=workflow_id,
            phase_id=phase_id,
            session_id=session_id,
            correlation_id=correlation_id,
            decision=decision,
            reason_code=reason_code,
            justification=justification,
            previous_state=previous_state,
            new_state=new_state,
            metadata=metadata or {},
            tags=tags or [],
        )

        # Compute checksum with chain
        event.previous_checksum = self._last_checksum
        event.checksum = event.compute_checksum(self._last_checksum)
        self._last_checksum = event.checksum

        # Persist to database
        self._save_event(event)

        # Update cache
        self._recent_events.append(event)
        if len(self._recent_events) > self._max_cache_size:
            self._recent_events = self._recent_events[-self._max_cache_size:]

        # Update metrics
        if PROMETHEUS_AVAILABLE:
            _AUDIT_EVENTS_COUNTER.labels(
                event_type=event_type.value,
                category=category.value
            ).inc()

        # Callback
        if self._on_event:
            try:
                self._on_event(event)
            except Exception as e:
                logger.error(f"Audit event callback error: {e}")

        logger.info(f"Recorded audit event: {event.event_id} type={event_type.value}")
        return event

    def _infer_category(self, event_type: AuditEventType) -> AuditCategory:
        """Infer category from event type."""
        mapping = {
            AuditEventType.ML_ROUTE_DECISION: AuditCategory.ROUTING,
            AuditEventType.USER_ROUTE_OVERRIDE: AuditCategory.ROUTING,
            AuditEventType.EXECUTION_PATH_SELECTED: AuditCategory.ROUTING,
            AuditEventType.TEAM_COMPOSITION_PROPOSED: AuditCategory.TEAM,
            AuditEventType.TEAM_COMPOSITION_OVERRIDE: AuditCategory.TEAM,
            AuditEventType.TEAM_MEMBER_ADDED: AuditCategory.TEAM,
            AuditEventType.TEAM_MEMBER_REMOVED: AuditCategory.TEAM,
            AuditEventType.PHASE_STARTED: AuditCategory.PHASE,
            AuditEventType.PHASE_COMPLETED: AuditCategory.PHASE,
            AuditEventType.PHASE_ROLLBACK: AuditCategory.PHASE,
            AuditEventType.GATE_CHECK_PASSED: AuditCategory.PHASE,
            AuditEventType.GATE_CHECK_FAILED: AuditCategory.PHASE,
            AuditEventType.APPROVAL_REQUESTED: AuditCategory.APPROVAL,
            AuditEventType.APPROVAL_GRANTED: AuditCategory.APPROVAL,
            AuditEventType.APPROVAL_DENIED: AuditCategory.APPROVAL,
            AuditEventType.APPROVAL_TIMEOUT: AuditCategory.APPROVAL,
            AuditEventType.ACCESS_GRANTED: AuditCategory.ACCESS,
            AuditEventType.ACCESS_DENIED: AuditCategory.ACCESS,
            AuditEventType.PERMISSION_CHANGED: AuditCategory.ACCESS,
            AuditEventType.DATA_ACCESSED: AuditCategory.DATA,
            AuditEventType.DATA_EXPORTED: AuditCategory.DATA,
            AuditEventType.PII_REDACTED: AuditCategory.DATA,
            AuditEventType.CONFIG_CHANGED: AuditCategory.SYSTEM,
            AuditEventType.POLICY_APPLIED: AuditCategory.SYSTEM,
            AuditEventType.SECURITY_EVENT: AuditCategory.SECURITY,
        }
        return mapping.get(event_type, AuditCategory.SYSTEM)

    def _save_event(self, event: AuditEvent) -> None:
        """Persist event to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        data = event.to_dict()
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        values = list(data.values())

        cursor.execute(
            f"INSERT INTO audit_events ({columns}) VALUES ({placeholders})",
            values
        )

        conn.commit()
        conn.close()

    def get_event(self, event_id: str) -> Optional[AuditEvent]:
        """Get a single audit event by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM audit_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return AuditEvent.from_dict(dict(row))
        return None

    def query(
        self,
        event_types: Optional[List[AuditEventType]] = None,
        categories: Optional[List[AuditCategory]] = None,
        actor_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEvent]:
        """
        Query audit events with filters.

        Args:
            event_types: Filter by event types
            categories: Filter by categories
            actor_id: Filter by actor
            workflow_id: Filter by workflow
            correlation_id: Filter by correlation ID
            start_time: Events after this time
            end_time: Events before this time
            tags: Filter by tags (any match)
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            List of matching AuditEvent objects
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        conditions = []
        params = []

        if event_types:
            placeholders = ", ".join(["?" for _ in event_types])
            conditions.append(f"event_type IN ({placeholders})")
            params.extend([t.value for t in event_types])

        if categories:
            placeholders = ", ".join(["?" for _ in categories])
            conditions.append(f"category IN ({placeholders})")
            params.extend([c.value for c in categories])

        if actor_id:
            conditions.append("actor_id = ?")
            params.append(actor_id)

        if workflow_id:
            conditions.append("workflow_id = ?")
            params.append(workflow_id)

        if correlation_id:
            conditions.append("correlation_id = ?")
            params.append(correlation_id)

        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())

        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT * FROM audit_events
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        events = [AuditEvent.from_dict(dict(row)) for row in rows]

        # Filter by tags in memory if specified
        if tags:
            events = [e for e in events if any(t in e.tags for t in tags)]

        return events

    def get_decision_history(
        self,
        workflow_id: str,
        include_overrides: bool = True,
    ) -> List[AuditEvent]:
        """Get decision history for a workflow."""
        event_types = [
            AuditEventType.ML_ROUTE_DECISION,
            AuditEventType.EXECUTION_PATH_SELECTED,
        ]

        if include_overrides:
            event_types.extend([
                AuditEventType.USER_ROUTE_OVERRIDE,
                AuditEventType.TEAM_COMPOSITION_OVERRIDE,
            ])

        return self.query(
            workflow_id=workflow_id,
            event_types=event_types,
            limit=1000,
        )

    def get_override_history(
        self,
        actor_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[AuditEvent]:
        """Get all override events."""
        return self.query(
            event_types=[
                AuditEventType.USER_ROUTE_OVERRIDE,
                AuditEventType.TEAM_COMPOSITION_OVERRIDE,
            ],
            actor_id=actor_id,
            start_time=start_time,
            end_time=end_time,
            limit=1000,
        )

    def export_evidence_pack(
        self,
        workflow_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        description: str = "Evidence pack export",
        created_by: str = "system",
    ) -> EvidencePack:
        """
        Export an evidence pack for compliance.

        Args:
            workflow_id: Filter to specific workflow
            start_time: Include events after this time
            end_time: Include events before this time
            description: Pack description
            created_by: User creating the pack

        Returns:
            EvidencePack with all matching events
        """
        events = self.query(
            workflow_id=workflow_id,
            start_time=start_time,
            end_time=end_time,
            limit=10000,  # Large limit for export
        )

        # Compute summary
        summary = {
            "total_events": len(events),
            "by_type": {},
            "by_category": {},
            "actors": set(),
            "workflows": set(),
        }

        for event in events:
            summary["by_type"][event.event_type.value] = summary["by_type"].get(event.event_type.value, 0) + 1
            summary["by_category"][event.category.value] = summary["by_category"].get(event.category.value, 0) + 1
            summary["actors"].add(event.actor_id)
            if event.workflow_id:
                summary["workflows"].add(event.workflow_id)

        summary["actors"] = list(summary["actors"])
        summary["workflows"] = list(summary["workflows"])

        pack = EvidencePack(
            pack_id=f"evid_{uuid4().hex[:12]}",
            created_at=datetime.utcnow(),
            created_by=created_by,
            description=description,
            workflow_id=workflow_id,
            start_time=start_time,
            end_time=end_time,
            events=events,
            summary=summary,
        )
        pack.checksum = pack.compute_checksum()

        # Save evidence pack metadata
        self._save_evidence_pack(pack)

        # Record the export as an audit event
        self.record(
            event_type=AuditEventType.DATA_EXPORTED,
            actor_id=created_by,
            actor_type="user",
            workflow_id=workflow_id,
            decision="Evidence pack exported",
            metadata={
                "pack_id": pack.pack_id,
                "event_count": len(events),
                "checksum": pack.checksum,
            },
        )

        logger.info(f"Exported evidence pack: {pack.pack_id} with {len(events)} events")
        return pack

    def _save_evidence_pack(self, pack: EvidencePack) -> None:
        """Save evidence pack metadata."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO evidence_packs
            (pack_id, created_at, created_by, description, workflow_id,
             start_time, end_time, event_ids, summary, checksum)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pack.pack_id,
            pack.created_at.isoformat(),
            pack.created_by,
            pack.description,
            pack.workflow_id,
            pack.start_time.isoformat() if pack.start_time else None,
            pack.end_time.isoformat() if pack.end_time else None,
            json.dumps([e.event_id for e in pack.events]),
            json.dumps(pack.summary),
            pack.checksum,
        ))

        conn.commit()
        conn.close()

    def verify_integrity(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Verify the integrity of the audit chain.

        Returns:
            Verification result with any broken links
        """
        events = self.query(
            start_time=start_time,
            end_time=end_time,
            limit=100000,
        )

        # Sort by timestamp ascending
        events.sort(key=lambda e: e.timestamp)

        result = {
            "verified": True,
            "total_events": len(events),
            "broken_links": [],
            "verified_at": datetime.utcnow().isoformat(),
        }

        prev_checksum = None
        for event in events:
            # Verify event checksum
            computed = event.compute_checksum(prev_checksum)
            if computed != event.checksum:
                result["verified"] = False
                result["broken_links"].append({
                    "event_id": event.event_id,
                    "expected": event.checksum,
                    "computed": computed,
                    "timestamp": event.timestamp.isoformat(),
                })

            # Verify chain link
            if prev_checksum and event.previous_checksum != prev_checksum:
                result["verified"] = False
                result["broken_links"].append({
                    "event_id": event.event_id,
                    "chain_break": True,
                    "expected_previous": prev_checksum,
                    "actual_previous": event.previous_checksum,
                })

            prev_checksum = event.checksum

        logger.info(f"Integrity verification: verified={result['verified']}, events={len(events)}")
        return result

    def get_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get audit trail statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        time_filter = ""
        params = []
        if start_time:
            time_filter += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        if end_time:
            time_filter += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        stats = {
            "total_events": 0,
            "by_type": {},
            "by_category": {},
            "by_actor_type": {},
            "overrides_count": 0,
            "security_events_count": 0,
        }

        # Total events
        cursor.execute(f"SELECT COUNT(*) FROM audit_events WHERE 1=1 {time_filter}", params)
        stats["total_events"] = cursor.fetchone()[0]

        # By type
        cursor.execute(
            f"SELECT event_type, COUNT(*) FROM audit_events WHERE 1=1 {time_filter} GROUP BY event_type",
            params
        )
        for row in cursor.fetchall():
            stats["by_type"][row[0]] = row[1]

        # By category
        cursor.execute(
            f"SELECT category, COUNT(*) FROM audit_events WHERE 1=1 {time_filter} GROUP BY category",
            params
        )
        for row in cursor.fetchall():
            stats["by_category"][row[0]] = row[1]

        # By actor type
        cursor.execute(
            f"SELECT actor_type, COUNT(*) FROM audit_events WHERE 1=1 {time_filter} GROUP BY actor_type",
            params
        )
        for row in cursor.fetchall():
            stats["by_actor_type"][row[0]] = row[1]

        # Overrides
        cursor.execute(
            f"SELECT COUNT(*) FROM audit_events WHERE event_type IN ('user_route_override', 'team_composition_override') {time_filter}",
            params
        )
        stats["overrides_count"] = cursor.fetchone()[0]

        # Security events
        cursor.execute(
            f"SELECT COUNT(*) FROM audit_events WHERE category = 'security' {time_filter}",
            params
        )
        stats["security_events_count"] = cursor.fetchone()[0]

        conn.close()
        return stats

    def set_event_callback(self, callback: Callable[[AuditEvent], None]) -> None:
        """Set callback for new audit events."""
        self._on_event = callback

    def reset(self) -> None:
        """Reset service state (for testing)."""
        self._recent_events.clear()
        self._last_checksum = None
        self._on_event = None

        # Clear database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM audit_events")
        cursor.execute("DELETE FROM evidence_packs")
        conn.commit()
        conn.close()

        logger.info("AuditTrailService reset")


# Singleton instance
_audit_trail_service: Optional[AuditTrailService] = None


def get_audit_trail_service(db_path: str = "audit_trail.db") -> AuditTrailService:
    """Get the singleton AuditTrailService instance."""
    global _audit_trail_service
    if _audit_trail_service is None:
        _audit_trail_service = AuditTrailService(db_path=db_path)
    return _audit_trail_service
