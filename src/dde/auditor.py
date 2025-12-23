#!/usr/bin/env python3
"""
DDEAuditor - PostgreSQL-Backed Audit Trail

Provides DDE-specific audit logging with PostgreSQL persistence.

MD-2098: [DDE-4] Complete auditor integration with PostgreSQL

Features:
- PostgreSQL persistence via psycopg2
- Chain integrity via hash linking
- Query API for audit trails
- Evidence pack export for compliance
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Optional database drivers
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logger.warning("psycopg2 not available - using in-memory fallback")

# Optional Prometheus metrics
try:
    from prometheus_client import Counter, Histogram
    PROMETHEUS_AVAILABLE = True

    AUDIT_EVENTS_TOTAL = Counter(
        "dde_audit_events_total",
        "Total DDE audit events",
        ["event_type", "category"]
    )
    AUDIT_QUERY_DURATION = Histogram(
        "dde_audit_query_duration_seconds",
        "Audit query duration",
        ["query_type"]
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    AUDIT_EVENTS_TOTAL = None
    AUDIT_QUERY_DURATION = None


class DDEAuditEventType(Enum):
    """Types of DDE audit events."""
    # Execution events
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    NODE_SKIPPED = "node_skipped"
    NODE_RETRIED = "node_retried"

    # Routing events
    ROUTING_DECISION = "routing_decision"
    SCHEDULE_GENERATED = "schedule_generated"
    BATCH_SELECTED = "batch_selected"

    # Artifact events
    ARTIFACT_CREATED = "artifact_created"
    ARTIFACT_VERIFIED = "artifact_verified"
    ARTIFACT_CORRUPTED = "artifact_corrupted"

    # Contract events
    CONTRACT_REGISTERED = "contract_registered"
    CONTRACT_VALIDATED = "contract_validated"
    CONTRACT_VIOLATED = "contract_violated"
    CONTRACT_DRIFT_DETECTED = "contract_drift_detected"

    # Circuit breaker events
    CIRCUIT_OPENED = "circuit_opened"
    CIRCUIT_CLOSED = "circuit_closed"
    CIRCUIT_HALF_OPENED = "circuit_half_opened"
    FALLBACK_INVOKED = "fallback_invoked"

    # Workflow events
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_RESUMED = "workflow_resumed"


class DDEAuditCategory(Enum):
    """Categories of DDE audit events."""
    EXECUTION = "execution"
    ROUTING = "routing"
    ARTIFACT = "artifact"
    CONTRACT = "contract"
    CIRCUIT_BREAKER = "circuit_breaker"
    WORKFLOW = "workflow"


@dataclass
class DDEAuditEvent:
    """
    A DDE audit event with chain integrity.
    """
    event_id: str
    workflow_id: str
    event_type: DDEAuditEventType
    category: DDEAuditCategory
    timestamp: datetime
    actor_id: str
    actor_type: str  # "user", "system", "agent"
    node_id: Optional[str] = None
    execution_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    previous_hash: Optional[str] = None
    hash: Optional[str] = None

    def __post_init__(self):
        if not self.hash:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash for chain integrity."""
        data = {
            "event_id": self.event_id,
            "workflow_id": self.workflow_id,
            "event_type": self.event_type.value,
            "category": self.category.value,
            "timestamp": self.timestamp.isoformat(),
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "node_id": self.node_id,
            "execution_id": self.execution_id,
            "payload": self.payload,
            "previous_hash": self.previous_hash,
        }
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "workflow_id": self.workflow_id,
            "event_type": self.event_type.value,
            "category": self.category.value,
            "timestamp": self.timestamp.isoformat(),
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "node_id": self.node_id,
            "execution_id": self.execution_id,
            "payload": self.payload,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DDEAuditEvent":
        return cls(
            event_id=data["event_id"],
            workflow_id=data["workflow_id"],
            event_type=DDEAuditEventType(data["event_type"]),
            category=DDEAuditCategory(data["category"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            actor_id=data["actor_id"],
            actor_type=data["actor_type"],
            node_id=data.get("node_id"),
            execution_id=data.get("execution_id"),
            payload=data.get("payload", {}),
            previous_hash=data.get("previous_hash"),
            hash=data.get("hash"),
        )


@dataclass
class ComplianceReport:
    """Compliance report for audit trail."""
    workflow_id: str
    generated_at: datetime
    total_events: int
    chain_integrity: bool
    broken_links: List[str]
    events_by_type: Dict[str, int]
    events_by_category: Dict[str, int]
    timeline: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "generated_at": self.generated_at.isoformat(),
            "total_events": self.total_events,
            "chain_integrity": self.chain_integrity,
            "broken_links": self.broken_links,
            "events_by_type": self.events_by_type,
            "events_by_category": self.events_by_category,
            "timeline": self.timeline,
        }


@dataclass
class EvidencePack:
    """Evidence pack for compliance export."""
    workflow_id: str
    generated_at: datetime
    events: List[DDEAuditEvent]
    chain_hashes: List[str]
    integrity_verified: bool
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "generated_at": self.generated_at.isoformat(),
            "events": [e.to_dict() for e in self.events],
            "chain_hashes": self.chain_hashes,
            "integrity_verified": self.integrity_verified,
            "metadata": self.metadata,
        }


class DDEAuditor:
    """
    DDE-specific audit logging with PostgreSQL persistence.

    Provides:
    - Event logging with chain integrity
    - PostgreSQL persistence
    - Query API for audit trails
    - Compliance reports and evidence packs
    """

    # SQL statements
    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS dde_audit_log (
        event_id VARCHAR(64) PRIMARY KEY,
        workflow_id VARCHAR(64) NOT NULL,
        event_type VARCHAR(64) NOT NULL,
        category VARCHAR(32) NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        actor_id VARCHAR(64) NOT NULL,
        actor_type VARCHAR(32) NOT NULL,
        node_id VARCHAR(64),
        execution_id VARCHAR(128),
        payload JSONB,
        previous_hash VARCHAR(64),
        hash VARCHAR(64) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_dde_audit_workflow ON dde_audit_log(workflow_id, timestamp);
    CREATE INDEX IF NOT EXISTS idx_dde_audit_event_type ON dde_audit_log(event_type);
    CREATE INDEX IF NOT EXISTS idx_dde_audit_node ON dde_audit_log(node_id);
    """

    INSERT_EVENT_SQL = """
    INSERT INTO dde_audit_log (
        event_id, workflow_id, event_type, category, timestamp,
        actor_id, actor_type, node_id, execution_id, payload,
        previous_hash, hash
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        use_memory_fallback: bool = True,
    ):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self.use_memory_fallback = use_memory_fallback
        self._connection = None
        self._memory_store: Dict[str, List[DDEAuditEvent]] = {}
        self._last_hash: Dict[str, str] = {}  # workflow_id -> last hash

        if POSTGRES_AVAILABLE and self.database_url:
            try:
                self._init_database()
            except Exception as e:
                logger.warning(f"Failed to initialize PostgreSQL: {e}")
                if not use_memory_fallback:
                    raise

        logger.info("DDEAuditor initialized")

    def _init_database(self) -> None:
        """Initialize PostgreSQL connection and schema."""
        self._connection = psycopg2.connect(self.database_url)
        with self._connection.cursor() as cursor:
            cursor.execute(self.CREATE_TABLE_SQL)
        self._connection.commit()
        logger.info("PostgreSQL audit schema initialized")

    def _get_connection(self):
        """Get database connection, reconnecting if needed."""
        if not POSTGRES_AVAILABLE or not self.database_url:
            return None

        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(self.database_url)

        return self._connection

    def _log_event(
        self,
        workflow_id: str,
        event_type: DDEAuditEventType,
        category: DDEAuditCategory,
        actor_id: str,
        actor_type: str = "system",
        node_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> DDEAuditEvent:
        """Internal method to log an audit event."""
        # Get previous hash for chain integrity
        previous_hash = self._last_hash.get(workflow_id)

        # Create event
        event = DDEAuditEvent(
            event_id=str(uuid4()),
            workflow_id=workflow_id,
            event_type=event_type,
            category=category,
            timestamp=datetime.utcnow(),
            actor_id=actor_id,
            actor_type=actor_type,
            node_id=node_id,
            execution_id=execution_id,
            payload=payload or {},
            previous_hash=previous_hash,
        )

        # Update last hash
        self._last_hash[workflow_id] = event.hash

        # Persist to PostgreSQL
        conn = self._get_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        self.INSERT_EVENT_SQL,
                        (
                            event.event_id,
                            event.workflow_id,
                            event.event_type.value,
                            event.category.value,
                            event.timestamp,
                            event.actor_id,
                            event.actor_type,
                            event.node_id,
                            event.execution_id,
                            Json(event.payload),
                            event.previous_hash,
                            event.hash,
                        )
                    )
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to persist audit event: {e}")
                conn.rollback()
                if not self.use_memory_fallback:
                    raise

        # Also store in memory (for quick access and fallback)
        if workflow_id not in self._memory_store:
            self._memory_store[workflow_id] = []
        self._memory_store[workflow_id].append(event)

        # Metrics
        if PROMETHEUS_AVAILABLE and AUDIT_EVENTS_TOTAL:
            AUDIT_EVENTS_TOTAL.labels(
                event_type=event_type.value,
                category=category.value
            ).inc()

        logger.debug(f"Audit event: {event_type.value} for workflow {workflow_id}")
        return event

    # Node execution logging
    def log_node_started(
        self,
        workflow_id: str,
        node_id: str,
        execution_id: str,
        inputs: Optional[Dict[str, Any]] = None,
        actor_id: str = "system",
    ) -> DDEAuditEvent:
        return self._log_event(
            workflow_id=workflow_id,
            event_type=DDEAuditEventType.NODE_STARTED,
            category=DDEAuditCategory.EXECUTION,
            actor_id=actor_id,
            node_id=node_id,
            execution_id=execution_id,
            payload={"inputs": inputs or {}},
        )

    def log_node_completed(
        self,
        workflow_id: str,
        node_id: str,
        execution_id: str,
        outputs: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
        actor_id: str = "system",
    ) -> DDEAuditEvent:
        return self._log_event(
            workflow_id=workflow_id,
            event_type=DDEAuditEventType.NODE_COMPLETED,
            category=DDEAuditCategory.EXECUTION,
            actor_id=actor_id,
            node_id=node_id,
            execution_id=execution_id,
            payload={"outputs": outputs or {}, "duration_ms": duration_ms},
        )

    def log_node_failed(
        self,
        workflow_id: str,
        node_id: str,
        execution_id: str,
        error: str,
        error_type: Optional[str] = None,
        recoverable: bool = False,
        actor_id: str = "system",
    ) -> DDEAuditEvent:
        return self._log_event(
            workflow_id=workflow_id,
            event_type=DDEAuditEventType.NODE_FAILED,
            category=DDEAuditCategory.EXECUTION,
            actor_id=actor_id,
            node_id=node_id,
            execution_id=execution_id,
            payload={
                "error": error,
                "error_type": error_type,
                "recoverable": recoverable,
            },
        )

    # Routing logging
    def log_routing_decision(
        self,
        workflow_id: str,
        node_id: str,
        decision: str,
        readiness_score: float,
        reason: str,
        actor_id: str = "system",
    ) -> DDEAuditEvent:
        return self._log_event(
            workflow_id=workflow_id,
            event_type=DDEAuditEventType.ROUTING_DECISION,
            category=DDEAuditCategory.ROUTING,
            actor_id=actor_id,
            node_id=node_id,
            payload={
                "decision": decision,
                "readiness_score": readiness_score,
                "reason": reason,
            },
        )

    # Contract logging
    def log_contract_violation(
        self,
        workflow_id: str,
        node_id: str,
        execution_id: str,
        violation_type: str,
        details: Dict[str, Any],
        actor_id: str = "system",
    ) -> DDEAuditEvent:
        return self._log_event(
            workflow_id=workflow_id,
            event_type=DDEAuditEventType.CONTRACT_VIOLATED,
            category=DDEAuditCategory.CONTRACT,
            actor_id=actor_id,
            node_id=node_id,
            execution_id=execution_id,
            payload={
                "violation_type": violation_type,
                "details": details,
            },
        )

    # Circuit breaker logging
    def log_circuit_breaker_event(
        self,
        workflow_id: str,
        node_id: str,
        event_type: DDEAuditEventType,
        failure_count: int,
        threshold: int,
        actor_id: str = "system",
    ) -> DDEAuditEvent:
        return self._log_event(
            workflow_id=workflow_id,
            event_type=event_type,
            category=DDEAuditCategory.CIRCUIT_BREAKER,
            actor_id=actor_id,
            node_id=node_id,
            payload={
                "failure_count": failure_count,
                "threshold": threshold,
            },
        )

    # Query methods
    def get_execution_audit_trail(
        self,
        workflow_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[DDEAuditEvent]:
        """Get audit trail for a workflow execution."""
        # Try database first
        conn = self._get_connection()
        if conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    sql = """
                    SELECT * FROM dde_audit_log
                    WHERE workflow_id = %s
                    """
                    params = [workflow_id]

                    if start_time:
                        sql += " AND timestamp >= %s"
                        params.append(start_time)
                    if end_time:
                        sql += " AND timestamp <= %s"
                        params.append(end_time)

                    sql += " ORDER BY timestamp ASC"

                    cursor.execute(sql, params)
                    rows = cursor.fetchall()

                    return [DDEAuditEvent.from_dict(dict(row)) for row in rows]
            except Exception as e:
                logger.error(f"Database query failed: {e}")

        # Fallback to memory store
        events = self._memory_store.get(workflow_id, [])
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]
        return events

    def get_compliance_report(
        self,
        workflow_id: str,
    ) -> ComplianceReport:
        """Generate compliance report for a workflow."""
        events = self.get_execution_audit_trail(workflow_id)

        # Check chain integrity
        broken_links = []
        prev_hash = None
        for event in events:
            if event.previous_hash != prev_hash:
                broken_links.append(event.event_id)
            prev_hash = event.hash

        # Count by type and category
        events_by_type = {}
        events_by_category = {}
        for event in events:
            events_by_type[event.event_type.value] = events_by_type.get(event.event_type.value, 0) + 1
            events_by_category[event.category.value] = events_by_category.get(event.category.value, 0) + 1

        # Build timeline
        timeline = [
            {
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type.value,
                "node_id": e.node_id,
                "actor": e.actor_id,
            }
            for e in events
        ]

        return ComplianceReport(
            workflow_id=workflow_id,
            generated_at=datetime.utcnow(),
            total_events=len(events),
            chain_integrity=len(broken_links) == 0,
            broken_links=broken_links,
            events_by_type=events_by_type,
            events_by_category=events_by_category,
            timeline=timeline,
        )

    def export_evidence_pack(
        self,
        workflow_id: str,
    ) -> EvidencePack:
        """Export evidence pack for compliance."""
        events = self.get_execution_audit_trail(workflow_id)
        chain_hashes = [e.hash for e in events if e.hash]

        # Verify integrity
        integrity_verified = True
        prev_hash = None
        for event in events:
            if event.previous_hash != prev_hash:
                integrity_verified = False
                break
            prev_hash = event.hash

        return EvidencePack(
            workflow_id=workflow_id,
            generated_at=datetime.utcnow(),
            events=events,
            chain_hashes=chain_hashes,
            integrity_verified=integrity_verified,
            metadata={
                "total_events": len(events),
                "first_event": events[0].timestamp.isoformat() if events else None,
                "last_event": events[-1].timestamp.isoformat() if events else None,
            },
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get auditor statistics."""
        total_events = sum(len(events) for events in self._memory_store.values())
        return {
            "total_events": total_events,
            "workflows_tracked": len(self._memory_store),
            "postgres_available": POSTGRES_AVAILABLE and self._connection is not None,
        }

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
        logger.info("DDEAuditor closed")
