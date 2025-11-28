#!/usr/bin/env python3
"""
Unit Tests for Deployment Audit Trail Service (MD-1812)

Tests comprehensive audit logging for deployment compliance.
"""

import pytest
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from services.deployment_audit_service import (
    DeploymentAuditService,
    AuditEvent,
    AuditAction,
    AuditSeverity,
    AuditQuery,
    RetentionPolicy,
    ExportFormat,
    get_deployment_audit_service,
)


class TestDeploymentAuditService:
    """Tests for DeploymentAuditService."""

    @pytest.fixture
    def service(self):
        """Create a fresh service instance for testing."""
        return DeploymentAuditService()

    @pytest.fixture
    def service_with_events(self, service):
        """Create service with some pre-populated events."""
        # Add various events
        service.log_deployment_triggered(
            environment="production",
            user_id="user-001",
            user_email="dev@example.com",
            version="v1.2.0",
            deployment_id="deploy-001",
        )
        service.log_deployment_completed(
            environment="production",
            user_id="user-001",
            version="v1.2.0",
            deployment_id="deploy-001",
            duration_seconds=120.5,
        )
        service.log_deployment_triggered(
            environment="beta",
            user_id="user-002",
            version="v1.3.0",
            deployment_id="deploy-002",
        )
        service.log_deployment_failed(
            environment="beta",
            user_id="user-002",
            version="v1.3.0",
            deployment_id="deploy-002",
            error_message="Connection timeout",
        )
        service.log_rollback_triggered(
            environment="beta",
            user_id="user-002",
            version="v1.2.0",
            previous_version="v1.3.0",
            deployment_id="deploy-003",
            reason="Deployment failed, reverting to stable version",
        )
        return service

    # ========================================================================
    # Basic Logging Tests
    # ========================================================================

    def test_log_event_creates_event(self, service):
        """Test that log_event creates an audit event."""
        event = service.log_event(
            action=AuditAction.DEPLOYMENT_TRIGGERED,
            environment="production",
            user_id="test-user",
            version="v1.0.0",
        )

        assert event is not None
        assert event.id is not None
        assert event.action == AuditAction.DEPLOYMENT_TRIGGERED
        assert event.environment == "production"
        assert event.user_id == "test-user"
        assert event.version == "v1.0.0"

    def test_log_event_timestamp(self, service):
        """Test that events get proper timestamps."""
        before = datetime.utcnow()
        event = service.log_event(
            action=AuditAction.DEPLOYMENT_TRIGGERED,
            environment="production",
            user_id="test-user",
        )
        after = datetime.utcnow()

        assert before <= event.timestamp <= after

    def test_log_event_with_details(self, service):
        """Test logging event with additional details."""
        details = {"git_commit": "abc123", "branch": "main"}
        event = service.log_event(
            action=AuditAction.DEPLOYMENT_TRIGGERED,
            environment="production",
            user_id="test-user",
            details=details,
        )

        assert event.details == details
        assert event.details["git_commit"] == "abc123"

    def test_log_event_auto_severity(self, service):
        """Test that severity is auto-determined based on action."""
        # Critical action
        event_failed = service.log_event(
            action=AuditAction.DEPLOYMENT_FAILED,
            environment="production",
            user_id="test-user",
        )
        assert event_failed.severity == AuditSeverity.CRITICAL

        # Warning action
        event_cancelled = service.log_event(
            action=AuditAction.DEPLOYMENT_CANCELLED,
            environment="production",
            user_id="test-user",
        )
        assert event_cancelled.severity == AuditSeverity.WARNING

        # Info action
        event_completed = service.log_event(
            action=AuditAction.DEPLOYMENT_COMPLETED,
            environment="production",
            user_id="test-user",
        )
        assert event_completed.severity == AuditSeverity.INFO

    def test_log_event_with_correlation_id(self, service):
        """Test logging with correlation ID for related events."""
        correlation_id = "corr-12345"

        event1 = service.log_event(
            action=AuditAction.DEPLOYMENT_TRIGGERED,
            environment="production",
            user_id="test-user",
            correlation_id=correlation_id,
        )
        event2 = service.log_event(
            action=AuditAction.DEPLOYMENT_COMPLETED,
            environment="production",
            user_id="test-user",
            correlation_id=correlation_id,
        )

        assert event1.correlation_id == correlation_id
        assert event2.correlation_id == correlation_id

    # ========================================================================
    # Convenience Method Tests
    # ========================================================================

    def test_log_deployment_triggered(self, service):
        """Test deployment triggered logging."""
        event = service.log_deployment_triggered(
            environment="production",
            user_id="user-001",
            version="v1.0.0",
            deployment_id="deploy-001",
        )

        assert event.action == AuditAction.DEPLOYMENT_TRIGGERED
        assert event.deployment_id == "deploy-001"

    def test_log_deployment_completed(self, service):
        """Test deployment completed logging."""
        event = service.log_deployment_completed(
            environment="production",
            user_id="user-001",
            version="v1.0.0",
            deployment_id="deploy-001",
            duration_seconds=150.5,
        )

        assert event.action == AuditAction.DEPLOYMENT_COMPLETED
        assert event.details["duration_seconds"] == 150.5

    def test_log_deployment_failed(self, service):
        """Test deployment failed logging."""
        event = service.log_deployment_failed(
            environment="production",
            user_id="user-001",
            version="v1.0.0",
            deployment_id="deploy-001",
            error_message="Container failed to start",
        )

        assert event.action == AuditAction.DEPLOYMENT_FAILED
        assert event.severity == AuditSeverity.CRITICAL
        assert event.details["error_message"] == "Container failed to start"

    def test_log_rollback_triggered(self, service):
        """Test rollback triggered logging."""
        event = service.log_rollback_triggered(
            environment="production",
            user_id="user-001",
            version="v1.0.0",
            previous_version="v1.1.0",
            deployment_id="deploy-002",
            reason="Critical bug found",
        )

        assert event.action == AuditAction.ROLLBACK_TRIGGERED
        assert event.version == "v1.0.0"
        assert event.previous_version == "v1.1.0"
        assert event.reason == "Critical bug found"

    def test_log_approval_requested(self, service):
        """Test approval requested logging."""
        event = service.log_approval_requested(
            environment="production",
            user_id="user-001",
            version="v1.0.0",
            approvers=["manager-001", "lead-001"],
        )

        assert event.action == AuditAction.APPROVAL_REQUESTED
        assert event.details["approvers"] == ["manager-001", "lead-001"]

    def test_log_approval_decision_granted(self, service):
        """Test approval granted logging."""
        event = service.log_approval_decision(
            environment="production",
            user_id="manager-001",
            version="v1.0.0",
            approved=True,
            reason="Approved for release",
        )

        assert event.action == AuditAction.APPROVAL_GRANTED
        assert event.reason == "Approved for release"

    def test_log_approval_decision_denied(self, service):
        """Test approval denied logging."""
        event = service.log_approval_decision(
            environment="production",
            user_id="manager-001",
            version="v1.0.0",
            approved=False,
            reason="Needs more testing",
        )

        assert event.action == AuditAction.APPROVAL_DENIED

    # ========================================================================
    # Query Tests
    # ========================================================================

    def test_query_all_events(self, service_with_events):
        """Test querying all events."""
        result = service_with_events.query_events(AuditQuery())

        assert result.total == 5
        assert len(result.events) == 5

    def test_query_by_environment(self, service_with_events):
        """Test querying events by environment."""
        query = AuditQuery(environments=["production"])
        result = service_with_events.query_events(query)

        assert result.total == 2
        assert all(e.environment == "production" for e in result.events)

    def test_query_by_action(self, service_with_events):
        """Test querying events by action type."""
        query = AuditQuery(actions=[AuditAction.DEPLOYMENT_TRIGGERED])
        result = service_with_events.query_events(query)

        assert result.total == 2
        assert all(e.action == AuditAction.DEPLOYMENT_TRIGGERED for e in result.events)

    def test_query_by_user(self, service_with_events):
        """Test querying events by user."""
        query = AuditQuery(user_ids=["user-001"])
        result = service_with_events.query_events(query)

        assert result.total == 2
        assert all(e.user_id == "user-001" for e in result.events)

    def test_query_by_severity(self, service_with_events):
        """Test querying events by severity."""
        query = AuditQuery(severities=[AuditSeverity.CRITICAL])
        result = service_with_events.query_events(query)

        assert result.total == 1
        assert result.events[0].severity == AuditSeverity.CRITICAL

    def test_query_by_deployment_id(self, service_with_events):
        """Test querying events by deployment ID."""
        query = AuditQuery(deployment_id="deploy-001")
        result = service_with_events.query_events(query)

        assert result.total == 2
        assert all(e.deployment_id == "deploy-001" for e in result.events)

    def test_query_pagination(self, service_with_events):
        """Test query pagination."""
        # First page
        query1 = AuditQuery(limit=2, offset=0)
        result1 = service_with_events.query_events(query1)

        assert len(result1.events) == 2
        assert result1.has_more is True

        # Second page
        query2 = AuditQuery(limit=2, offset=2)
        result2 = service_with_events.query_events(query2)

        assert len(result2.events) == 2
        assert result2.has_more is True

        # Third page
        query3 = AuditQuery(limit=2, offset=4)
        result3 = service_with_events.query_events(query3)

        assert len(result3.events) == 1
        assert result3.has_more is False

    def test_query_date_range(self, service):
        """Test querying events by date range."""
        # Add events at different times
        old_event = service.log_event(
            action=AuditAction.DEPLOYMENT_TRIGGERED,
            environment="production",
            user_id="test-user",
        )
        # Manually set timestamp for testing
        old_event.timestamp = datetime.utcnow() - timedelta(days=10)

        new_event = service.log_event(
            action=AuditAction.DEPLOYMENT_COMPLETED,
            environment="production",
            user_id="test-user",
        )

        # Query last 5 days
        query = AuditQuery(
            start_date=datetime.utcnow() - timedelta(days=5),
            end_date=datetime.utcnow(),
        )
        result = service.query_events(query)

        assert result.total == 1
        assert result.events[0].action == AuditAction.DEPLOYMENT_COMPLETED

    def test_get_event_by_id(self, service):
        """Test getting event by ID."""
        event = service.log_event(
            action=AuditAction.DEPLOYMENT_TRIGGERED,
            environment="production",
            user_id="test-user",
        )

        retrieved = service.get_event_by_id(event.id)

        assert retrieved is not None
        assert retrieved.id == event.id

    def test_get_events_for_deployment(self, service_with_events):
        """Test getting all events for a deployment."""
        events = service_with_events.get_events_for_deployment("deploy-001")

        assert len(events) == 2
        assert all(e.deployment_id == "deploy-001" for e in events)

    # ========================================================================
    # Export Tests
    # ========================================================================

    def test_export_json(self, service_with_events):
        """Test JSON export."""
        query = AuditQuery()
        export = service_with_events.export_events(query, ExportFormat.JSON)

        import json
        data = json.loads(export)

        assert "exported_at" in data
        assert "total_events" in data
        assert data["total_events"] == 5
        assert len(data["events"]) == 5

    def test_export_csv(self, service_with_events):
        """Test CSV export."""
        query = AuditQuery()
        export = service_with_events.export_events(query, ExportFormat.CSV)

        lines = export.strip().split("\n")
        assert len(lines) == 6  # Header + 5 events

        # Check header
        assert "id,timestamp,action,severity,environment" in lines[0]

    def test_export_jsonl(self, service_with_events):
        """Test JSON Lines export."""
        query = AuditQuery()
        export = service_with_events.export_events(query, ExportFormat.JSONL)

        import json
        lines = export.strip().split("\n")
        assert len(lines) == 5

        # Each line should be valid JSON
        for line in lines:
            data = json.loads(line)
            assert "id" in data
            assert "action" in data

    def test_export_filtered(self, service_with_events):
        """Test exporting filtered events."""
        query = AuditQuery(environments=["production"])
        export = service_with_events.export_events(query, ExportFormat.JSON)

        import json
        data = json.loads(export)

        assert data["total_events"] == 2

    # ========================================================================
    # Retention Tests
    # ========================================================================

    def test_apply_retention_policy(self, service):
        """Test applying retention policy."""
        # Add old event
        old_event = service.log_event(
            action=AuditAction.DEPLOYMENT_TRIGGERED,
            environment="production",
            user_id="test-user",
        )
        old_event.timestamp = datetime.utcnow() - timedelta(days=100)

        # Add recent event
        service.log_event(
            action=AuditAction.DEPLOYMENT_COMPLETED,
            environment="production",
            user_id="test-user",
        )

        # Apply retention (default 90 days)
        result = service.apply_retention_policy()

        assert result["deleted"] == 1
        assert result["retained"] == 1

    def test_apply_retention_with_archive(self):
        """Test retention with archiving enabled."""
        policy = RetentionPolicy(
            retention_days=30,
            archive_enabled=True,
        )
        service = DeploymentAuditService(retention_policy=policy)

        # Add old event
        old_event = service.log_event(
            action=AuditAction.DEPLOYMENT_TRIGGERED,
            environment="production",
            user_id="test-user",
        )
        old_event.timestamp = datetime.utcnow() - timedelta(days=40)

        result = service.apply_retention_policy()

        assert result["archived"] == 1
        assert result["deleted"] == 0
        assert len(service._archived_events) == 1

    def test_get_retention_status(self, service):
        """Test getting retention status."""
        service.log_event(
            action=AuditAction.DEPLOYMENT_TRIGGERED,
            environment="production",
            user_id="test-user",
        )

        status = service.get_retention_status()

        assert status["total_events"] == 1
        assert status["retention_days"] == 90  # Default
        assert status["expired_pending"] == 0

    # ========================================================================
    # Statistics Tests
    # ========================================================================

    def test_get_statistics(self, service_with_events):
        """Test getting audit statistics."""
        stats = service_with_events.get_statistics()

        assert stats["total_events"] == 5
        assert "by_action" in stats
        assert "by_environment" in stats
        assert "by_severity" in stats
        assert "deployments" in stats

        # Check deployment metrics
        deployments = stats["deployments"]
        assert deployments["triggered"] == 2
        assert deployments["completed"] == 1
        assert deployments["failed"] == 1
        assert deployments["rollbacks"] == 1

    def test_get_statistics_success_rate(self, service):
        """Test deployment success rate calculation."""
        # Add some events
        for _ in range(8):
            service.log_deployment_triggered(
                environment="production",
                user_id="test-user",
                version="v1.0.0",
                deployment_id="deploy-001",
            )
        for _ in range(6):
            service.log_deployment_completed(
                environment="production",
                user_id="test-user",
                version="v1.0.0",
                deployment_id="deploy-001",
            )

        stats = service.get_statistics()

        assert stats["deployments"]["triggered"] == 8
        assert stats["deployments"]["completed"] == 6
        assert stats["deployments"]["success_rate"] == 0.75

    # ========================================================================
    # Serialization Tests
    # ========================================================================

    def test_event_to_dict(self, service):
        """Test event serialization."""
        event = service.log_event(
            action=AuditAction.DEPLOYMENT_TRIGGERED,
            environment="production",
            user_id="test-user",
            version="v1.0.0",
            deployment_id="deploy-001",
        )

        event_dict = event.to_dict()

        assert event_dict["id"] == event.id
        assert event_dict["action"] == "deployment_triggered"
        assert event_dict["environment"] == "production"
        assert event_dict["user_id"] == "test-user"

    def test_event_from_dict(self, service):
        """Test event deserialization."""
        event = service.log_event(
            action=AuditAction.DEPLOYMENT_TRIGGERED,
            environment="production",
            user_id="test-user",
        )

        event_dict = event.to_dict()
        restored = AuditEvent.from_dict(event_dict)

        assert restored.id == event.id
        assert restored.action == event.action
        assert restored.environment == event.environment

    def test_query_result_to_dict(self, service_with_events):
        """Test query result serialization."""
        result = service_with_events.query_events(AuditQuery(limit=2))
        result_dict = result.to_dict()

        assert result_dict["total"] == 5
        assert len(result_dict["events"]) == 2
        assert result_dict["has_more"] is True

    # ========================================================================
    # Singleton Tests
    # ========================================================================

    def test_singleton_instance(self):
        """Test singleton pattern."""
        service1 = get_deployment_audit_service()
        service2 = get_deployment_audit_service()

        assert service1 is service2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
