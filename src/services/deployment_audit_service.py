#!/usr/bin/env python3
"""
Deployment Audit Trail Service for MD-1812

Implements comprehensive audit trail for deployment compliance:
- Log all deployment actions (deploy, rollback, cancel)
- Track who/what/when/why for each action
- Enable export of audit logs (JSON, CSV)
- Enforce retention policy

Requirements:
- All deployment actions are logged
- Immutable audit records
- Queryable by time range, user, environment, action type
- Export capability for compliance reporting
"""

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

# Try to import Prometheus metrics
try:
    from prometheus_client import Counter, Histogram

    AUDIT_EVENTS = Counter(
        "maestro_deployment_audit_events_total",
        "Total deployment audit events",
        ["action", "environment", "status"]
    )
    AUDIT_QUERY_LATENCY = Histogram(
        "maestro_deployment_audit_query_latency_seconds",
        "Audit query latency",
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0]
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

    class StubMetric:
        def inc(self): pass
        def observe(self, value): pass
        def labels(self, **kwargs): return self

    AUDIT_EVENTS = StubMetric()
    AUDIT_QUERY_LATENCY = StubMetric()

logger = logging.getLogger("deployment_audit_service")


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class AuditAction(str, Enum):
    """Types of auditable deployment actions."""
    DEPLOYMENT_TRIGGERED = "deployment_triggered"
    DEPLOYMENT_STARTED = "deployment_started"
    DEPLOYMENT_COMPLETED = "deployment_completed"
    DEPLOYMENT_FAILED = "deployment_failed"
    DEPLOYMENT_CANCELLED = "deployment_cancelled"
    ROLLBACK_TRIGGERED = "rollback_triggered"
    ROLLBACK_COMPLETED = "rollback_completed"
    ROLLBACK_FAILED = "rollback_failed"
    HEALTH_CHECK_PASSED = "health_check_passed"
    HEALTH_CHECK_FAILED = "health_check_failed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    CONFIG_CHANGED = "config_changed"
    ENVIRONMENT_CREATED = "environment_created"
    ENVIRONMENT_UPDATED = "environment_updated"
    ENVIRONMENT_DELETED = "environment_deleted"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ExportFormat(str, Enum):
    """Supported export formats."""
    JSON = "json"
    CSV = "csv"
    JSONL = "jsonl"  # JSON Lines format


# Default retention period (90 days)
DEFAULT_RETENTION_DAYS = 90


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class AuditEvent:
    """Represents a single audit event."""
    id: str
    timestamp: datetime
    action: AuditAction
    severity: AuditSeverity
    environment: str
    user_id: str
    user_email: Optional[str]
    deployment_id: Optional[str]
    version: Optional[str]
    previous_version: Optional[str]
    reason: Optional[str]
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "severity": self.severity.value,
            "environment": self.environment,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "deployment_id": self.deployment_id,
            "version": self.version,
            "previous_version": self.previous_version,
            "reason": self.reason,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEvent":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            action=AuditAction(data["action"]),
            severity=AuditSeverity(data["severity"]),
            environment=data["environment"],
            user_id=data["user_id"],
            user_email=data.get("user_email"),
            deployment_id=data.get("deployment_id"),
            version=data.get("version"),
            previous_version=data.get("previous_version"),
            reason=data.get("reason"),
            details=data.get("details", {}),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
            request_id=data.get("request_id"),
            correlation_id=data.get("correlation_id"),
        )


@dataclass
class AuditQuery:
    """Query parameters for audit log search."""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    actions: Optional[List[AuditAction]] = None
    environments: Optional[List[str]] = None
    user_ids: Optional[List[str]] = None
    severities: Optional[List[AuditSeverity]] = None
    deployment_id: Optional[str] = None
    correlation_id: Optional[str] = None
    limit: int = 100
    offset: int = 0


@dataclass
class AuditQueryResult:
    """Result of an audit query."""
    events: List[AuditEvent]
    total: int
    limit: int
    offset: int
    has_more: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "events": [e.to_dict() for e in self.events],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "has_more": self.has_more,
        }


@dataclass
class RetentionPolicy:
    """Audit log retention policy."""
    retention_days: int = DEFAULT_RETENTION_DAYS
    archive_enabled: bool = False
    archive_location: Optional[str] = None
    compress_archives: bool = True


# ============================================================================
# SERVICE IMPLEMENTATION
# ============================================================================

class DeploymentAuditService:
    """
    Deployment Audit Trail Service

    Provides comprehensive audit logging for deployment compliance.
    """

    def __init__(
        self,
        retention_policy: Optional[RetentionPolicy] = None,
    ):
        self.retention_policy = retention_policy or RetentionPolicy()

        # In-memory storage (would be database in production)
        self._events: List[AuditEvent] = []
        self._archived_events: List[AuditEvent] = []

        logger.info(
            f"DeploymentAuditService initialized with "
            f"{self.retention_policy.retention_days} day retention"
        )

    # ========================================================================
    # CORE AUDIT LOGGING
    # ========================================================================

    def log_event(
        self,
        action: AuditAction,
        environment: str,
        user_id: str,
        user_email: Optional[str] = None,
        deployment_id: Optional[str] = None,
        version: Optional[str] = None,
        previous_version: Optional[str] = None,
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: Optional[AuditSeverity] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> AuditEvent:
        """
        Log an audit event.

        This is the primary method for recording deployment actions.
        Events are immutable once created.

        Args:
            action: Type of action being logged
            environment: Environment name (e.g., "production", "beta")
            user_id: ID of user performing the action
            user_email: Email of user (for display purposes)
            deployment_id: Related deployment ID if applicable
            version: Version being deployed/rolled back to
            previous_version: Previous version (for rollbacks)
            reason: Human-readable reason for the action
            details: Additional structured details
            severity: Event severity (auto-determined if not provided)
            ip_address: Client IP address
            user_agent: Client user agent
            request_id: Request tracking ID
            correlation_id: Correlation ID for related events

        Returns:
            Created AuditEvent
        """
        # Auto-determine severity if not provided
        if severity is None:
            severity = self._determine_severity(action)

        event = AuditEvent(
            id=str(uuid4()),
            timestamp=datetime.utcnow(),
            action=action,
            severity=severity,
            environment=environment,
            user_id=user_id,
            user_email=user_email,
            deployment_id=deployment_id,
            version=version,
            previous_version=previous_version,
            reason=reason,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            correlation_id=correlation_id,
        )

        self._events.append(event)

        # Update metrics
        AUDIT_EVENTS.labels(
            action=action.value,
            environment=environment,
            status="logged"
        ).inc()

        logger.info(
            f"Audit event logged: {action.value} on {environment} "
            f"by {user_id} (id: {event.id})"
        )

        return event

    def _determine_severity(self, action: AuditAction) -> AuditSeverity:
        """Determine severity based on action type."""
        critical_actions = {
            AuditAction.DEPLOYMENT_FAILED,
            AuditAction.ROLLBACK_FAILED,
            AuditAction.HEALTH_CHECK_FAILED,
        }
        warning_actions = {
            AuditAction.DEPLOYMENT_CANCELLED,
            AuditAction.APPROVAL_DENIED,
            AuditAction.ROLLBACK_TRIGGERED,
        }

        if action in critical_actions:
            return AuditSeverity.CRITICAL
        elif action in warning_actions:
            return AuditSeverity.WARNING
        else:
            return AuditSeverity.INFO

    # ========================================================================
    # CONVENIENCE LOGGING METHODS
    # ========================================================================

    def log_deployment_triggered(
        self,
        environment: str,
        user_id: str,
        version: str,
        deployment_id: str,
        **kwargs
    ) -> AuditEvent:
        """Log when a deployment is triggered."""
        return self.log_event(
            action=AuditAction.DEPLOYMENT_TRIGGERED,
            environment=environment,
            user_id=user_id,
            version=version,
            deployment_id=deployment_id,
            **kwargs
        )

    def log_deployment_completed(
        self,
        environment: str,
        user_id: str,
        version: str,
        deployment_id: str,
        duration_seconds: Optional[float] = None,
        **kwargs
    ) -> AuditEvent:
        """Log when a deployment completes successfully."""
        details = kwargs.pop("details", {})
        if duration_seconds:
            details["duration_seconds"] = duration_seconds
        return self.log_event(
            action=AuditAction.DEPLOYMENT_COMPLETED,
            environment=environment,
            user_id=user_id,
            version=version,
            deployment_id=deployment_id,
            details=details,
            **kwargs
        )

    def log_deployment_failed(
        self,
        environment: str,
        user_id: str,
        version: str,
        deployment_id: str,
        error_message: str,
        **kwargs
    ) -> AuditEvent:
        """Log when a deployment fails."""
        details = kwargs.pop("details", {})
        details["error_message"] = error_message
        return self.log_event(
            action=AuditAction.DEPLOYMENT_FAILED,
            environment=environment,
            user_id=user_id,
            version=version,
            deployment_id=deployment_id,
            details=details,
            severity=AuditSeverity.CRITICAL,
            **kwargs
        )

    def log_rollback_triggered(
        self,
        environment: str,
        user_id: str,
        version: str,
        previous_version: str,
        deployment_id: str,
        reason: str,
        **kwargs
    ) -> AuditEvent:
        """Log when a rollback is triggered."""
        return self.log_event(
            action=AuditAction.ROLLBACK_TRIGGERED,
            environment=environment,
            user_id=user_id,
            version=version,
            previous_version=previous_version,
            deployment_id=deployment_id,
            reason=reason,
            **kwargs
        )

    def log_rollback_completed(
        self,
        environment: str,
        user_id: str,
        version: str,
        deployment_id: str,
        **kwargs
    ) -> AuditEvent:
        """Log when a rollback completes successfully."""
        return self.log_event(
            action=AuditAction.ROLLBACK_COMPLETED,
            environment=environment,
            user_id=user_id,
            version=version,
            deployment_id=deployment_id,
            **kwargs
        )

    def log_approval_requested(
        self,
        environment: str,
        user_id: str,
        version: str,
        approvers: List[str],
        **kwargs
    ) -> AuditEvent:
        """Log when approval is requested."""
        details = kwargs.pop("details", {})
        details["approvers"] = approvers
        return self.log_event(
            action=AuditAction.APPROVAL_REQUESTED,
            environment=environment,
            user_id=user_id,
            version=version,
            details=details,
            **kwargs
        )

    def log_approval_decision(
        self,
        environment: str,
        user_id: str,
        version: str,
        approved: bool,
        reason: Optional[str] = None,
        **kwargs
    ) -> AuditEvent:
        """Log approval decision."""
        action = AuditAction.APPROVAL_GRANTED if approved else AuditAction.APPROVAL_DENIED
        return self.log_event(
            action=action,
            environment=environment,
            user_id=user_id,
            version=version,
            reason=reason,
            **kwargs
        )

    # ========================================================================
    # QUERY API
    # ========================================================================

    def query_events(self, query: AuditQuery) -> AuditQueryResult:
        """
        Query audit events with filters.

        Args:
            query: Query parameters

        Returns:
            AuditQueryResult with matching events
        """
        import time
        start_time = time.time()

        filtered = self._events.copy()

        # Apply filters
        if query.start_date:
            filtered = [e for e in filtered if e.timestamp >= query.start_date]

        if query.end_date:
            filtered = [e for e in filtered if e.timestamp <= query.end_date]

        if query.actions:
            filtered = [e for e in filtered if e.action in query.actions]

        if query.environments:
            filtered = [e for e in filtered if e.environment in query.environments]

        if query.user_ids:
            filtered = [e for e in filtered if e.user_id in query.user_ids]

        if query.severities:
            filtered = [e for e in filtered if e.severity in query.severities]

        if query.deployment_id:
            filtered = [e for e in filtered if e.deployment_id == query.deployment_id]

        if query.correlation_id:
            filtered = [e for e in filtered if e.correlation_id == query.correlation_id]

        # Sort by timestamp descending (newest first)
        filtered.sort(key=lambda e: e.timestamp, reverse=True)

        total = len(filtered)

        # Apply pagination
        paginated = filtered[query.offset:query.offset + query.limit]
        has_more = (query.offset + query.limit) < total

        latency = time.time() - start_time
        AUDIT_QUERY_LATENCY.observe(latency)

        return AuditQueryResult(
            events=paginated,
            total=total,
            limit=query.limit,
            offset=query.offset,
            has_more=has_more,
        )

    def get_event_by_id(self, event_id: str) -> Optional[AuditEvent]:
        """Get a specific audit event by ID."""
        for event in self._events:
            if event.id == event_id:
                return event
        return None

    def get_events_for_deployment(self, deployment_id: str) -> List[AuditEvent]:
        """Get all audit events for a specific deployment."""
        return [e for e in self._events if e.deployment_id == deployment_id]

    def get_events_by_correlation_id(self, correlation_id: str) -> List[AuditEvent]:
        """Get all audit events with the same correlation ID."""
        return [e for e in self._events if e.correlation_id == correlation_id]

    # ========================================================================
    # EXPORT API
    # ========================================================================

    def export_events(
        self,
        query: AuditQuery,
        format: ExportFormat = ExportFormat.JSON,
    ) -> str:
        """
        Export audit events in the specified format.

        Args:
            query: Query to filter events for export
            format: Export format (JSON, CSV, JSONL)

        Returns:
            Exported data as string
        """
        # Get all matching events (no pagination limit for export)
        query.limit = 10000  # Set high limit for export
        query.offset = 0
        result = self.query_events(query)
        events = result.events

        if format == ExportFormat.JSON:
            return self._export_json(events)
        elif format == ExportFormat.CSV:
            return self._export_csv(events)
        elif format == ExportFormat.JSONL:
            return self._export_jsonl(events)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _export_json(self, events: List[AuditEvent]) -> str:
        """Export as JSON."""
        return json.dumps(
            {
                "exported_at": datetime.utcnow().isoformat(),
                "total_events": len(events),
                "events": [e.to_dict() for e in events],
            },
            indent=2
        )

    def _export_csv(self, events: List[AuditEvent]) -> str:
        """Export as CSV."""
        output = io.StringIO()

        fieldnames = [
            "id", "timestamp", "action", "severity", "environment",
            "user_id", "user_email", "deployment_id", "version",
            "previous_version", "reason", "ip_address"
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for event in events:
            row = {
                "id": event.id,
                "timestamp": event.timestamp.isoformat(),
                "action": event.action.value,
                "severity": event.severity.value,
                "environment": event.environment,
                "user_id": event.user_id,
                "user_email": event.user_email or "",
                "deployment_id": event.deployment_id or "",
                "version": event.version or "",
                "previous_version": event.previous_version or "",
                "reason": event.reason or "",
                "ip_address": event.ip_address or "",
            }
            writer.writerow(row)

        return output.getvalue()

    def _export_jsonl(self, events: List[AuditEvent]) -> str:
        """Export as JSON Lines."""
        lines = [json.dumps(e.to_dict()) for e in events]
        return "\n".join(lines)

    # ========================================================================
    # RETENTION MANAGEMENT
    # ========================================================================

    def apply_retention_policy(self) -> Dict[str, int]:
        """
        Apply retention policy to audit events.

        Events older than retention period are archived or deleted.

        Returns:
            Dictionary with counts of archived/deleted events
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_policy.retention_days)

        expired_events = [e for e in self._events if e.timestamp < cutoff_date]
        retained_events = [e for e in self._events if e.timestamp >= cutoff_date]

        archived_count = 0
        deleted_count = 0

        if self.retention_policy.archive_enabled:
            self._archived_events.extend(expired_events)
            archived_count = len(expired_events)
            logger.info(f"Archived {archived_count} expired audit events")
        else:
            deleted_count = len(expired_events)
            logger.info(f"Deleted {deleted_count} expired audit events")

        self._events = retained_events

        return {
            "archived": archived_count,
            "deleted": deleted_count,
            "retained": len(retained_events),
        }

    def get_retention_status(self) -> Dict[str, Any]:
        """Get current retention status."""
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_policy.retention_days)

        expired_count = len([e for e in self._events if e.timestamp < cutoff_date])

        return {
            "total_events": len(self._events),
            "archived_events": len(self._archived_events),
            "expired_pending": expired_count,
            "retention_days": self.retention_policy.retention_days,
            "archive_enabled": self.retention_policy.archive_enabled,
        }

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get audit statistics for dashboard/reporting.

        Args:
            start_date: Start of period (defaults to 30 days ago)
            end_date: End of period (defaults to now)

        Returns:
            Dictionary with various statistics
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        period_events = [
            e for e in self._events
            if start_date <= e.timestamp <= end_date
        ]

        # Count by action
        action_counts = {}
        for event in period_events:
            action_counts[event.action.value] = action_counts.get(event.action.value, 0) + 1

        # Count by environment
        environment_counts = {}
        for event in period_events:
            environment_counts[event.environment] = environment_counts.get(event.environment, 0) + 1

        # Count by severity
        severity_counts = {}
        for event in period_events:
            severity_counts[event.severity.value] = severity_counts.get(event.severity.value, 0) + 1

        # Count by user
        user_counts = {}
        for event in period_events:
            user_counts[event.user_id] = user_counts.get(event.user_id, 0) + 1

        # Calculate deployment metrics
        deployments_triggered = action_counts.get("deployment_triggered", 0)
        deployments_completed = action_counts.get("deployment_completed", 0)
        deployments_failed = action_counts.get("deployment_failed", 0)
        rollbacks = action_counts.get("rollback_triggered", 0)

        success_rate = 0
        if deployments_triggered > 0:
            success_rate = deployments_completed / deployments_triggered

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total_events": len(period_events),
            "by_action": action_counts,
            "by_environment": environment_counts,
            "by_severity": severity_counts,
            "by_user": user_counts,
            "deployments": {
                "triggered": deployments_triggered,
                "completed": deployments_completed,
                "failed": deployments_failed,
                "rollbacks": rollbacks,
                "success_rate": round(success_rate, 3),
            },
        }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_service_instance: Optional[DeploymentAuditService] = None


def get_deployment_audit_service() -> DeploymentAuditService:
    """Get or create the singleton service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = DeploymentAuditService()
    return _service_instance


# For convenience
deployment_audit_service = get_deployment_audit_service()
