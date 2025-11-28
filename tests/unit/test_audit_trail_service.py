#!/usr/bin/env python3
"""
Unit tests for AuditTrailService

Tests cover:
- Event recording and persistence
- Cryptographic integrity chain
- Query and filtering
- Evidence pack export
- Override tracking
- Statistics and reporting
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from services.audit_trail_service import (
    AuditTrailService,
    AuditEvent,
    AuditEventType,
    AuditCategory,
    ReasonCode,
    EvidencePack,
    get_audit_trail_service,
)


@pytest.fixture
def service():
    """Create a fresh AuditTrailService instance for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    svc = AuditTrailService(db_path=db_path)
    yield svc

    # Cleanup
    svc.reset()
    try:
        os.unlink(db_path)
    except:
        pass


class TestEventRecording:
    """Tests for event recording."""

    def test_record_basic_event(self, service):
        """Test recording a basic audit event."""
        event = service.record(
            event_type=AuditEventType.ML_ROUTE_DECISION,
            actor_id="ml_router_v1",
            actor_type="system",
            decision="route_to_backend",
        )

        assert event.event_id.startswith("audit_")
        assert event.event_type == AuditEventType.ML_ROUTE_DECISION
        assert event.actor_id == "ml_router_v1"
        assert event.actor_type == "system"
        assert event.decision == "route_to_backend"
        assert event.checksum is not None

    def test_record_with_full_context(self, service):
        """Test recording with full context."""
        event = service.record(
            event_type=AuditEventType.USER_ROUTE_OVERRIDE,
            actor_id="user_123",
            actor_type="user",
            actor_name="John Doe",
            workflow_id="wf_456",
            phase_id="phase_001",
            session_id="sess_789",
            correlation_id="corr_abc",
            decision="override_to_frontend",
            reason_code=ReasonCode.MANUAL_OVERRIDE,
            justification="User requested frontend execution for UI testing",
            previous_state={"route": "backend"},
            new_state={"route": "frontend"},
            metadata={"priority": "high"},
            tags=["override", "ui-testing"],
        )

        assert event.workflow_id == "wf_456"
        assert event.phase_id == "phase_001"
        assert event.reason_code == ReasonCode.MANUAL_OVERRIDE
        assert event.previous_state == {"route": "backend"}
        assert event.new_state == {"route": "frontend"}
        assert "override" in event.tags

    def test_category_inference(self, service):
        """Test automatic category inference from event type."""
        routing_event = service.record(
            event_type=AuditEventType.ML_ROUTE_DECISION,
            actor_id="system",
            actor_type="system",
        )
        assert routing_event.category == AuditCategory.ROUTING

        team_event = service.record(
            event_type=AuditEventType.TEAM_MEMBER_ADDED,
            actor_id="system",
            actor_type="system",
        )
        assert team_event.category == AuditCategory.TEAM

        approval_event = service.record(
            event_type=AuditEventType.APPROVAL_GRANTED,
            actor_id="approver",
            actor_type="user",
        )
        assert approval_event.category == AuditCategory.APPROVAL

    def test_explicit_category(self, service):
        """Test explicit category overrides inference."""
        event = service.record(
            event_type=AuditEventType.CONFIG_CHANGED,
            actor_id="admin",
            actor_type="user",
            category=AuditCategory.SECURITY,
        )
        assert event.category == AuditCategory.SECURITY


class TestIntegrityChain:
    """Tests for cryptographic integrity chain."""

    def test_checksum_computation(self, service):
        """Test checksum is computed for each event."""
        event1 = service.record(
            event_type=AuditEventType.PHASE_STARTED,
            actor_id="system",
            actor_type="system",
        )

        assert event1.checksum is not None
        assert len(event1.checksum) == 64  # SHA-256 hex

    def test_chain_linking(self, service):
        """Test events are linked in a chain."""
        event1 = service.record(
            event_type=AuditEventType.PHASE_STARTED,
            actor_id="system",
            actor_type="system",
        )

        event2 = service.record(
            event_type=AuditEventType.PHASE_COMPLETED,
            actor_id="system",
            actor_type="system",
        )

        assert event2.previous_checksum == event1.checksum

    def test_integrity_verification_passes(self, service):
        """Test integrity verification on valid chain."""
        for i in range(5):
            service.record(
                event_type=AuditEventType.GATE_CHECK_PASSED,
                actor_id="system",
                actor_type="system",
                metadata={"gate": i},
            )

        result = service.verify_integrity()
        assert result["verified"] is True
        assert result["total_events"] == 5
        assert len(result["broken_links"]) == 0


class TestPersistence:
    """Tests for event persistence."""

    def test_event_survives_restart(self):
        """Test events persist across service instances."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            service1 = AuditTrailService(db_path=db_path)
            event = service1.record(
                event_type=AuditEventType.ACCESS_GRANTED,
                actor_id="user_1",
                actor_type="user",
                decision="granted",
            )
            event_id = event.event_id

            # New service instance
            service2 = AuditTrailService(db_path=db_path)
            recovered = service2.get_event(event_id)

            assert recovered is not None
            assert recovered.event_id == event_id
            assert recovered.event_type == AuditEventType.ACCESS_GRANTED
            assert recovered.decision == "granted"
        finally:
            os.unlink(db_path)

    def test_get_nonexistent_event(self, service):
        """Test getting non-existent event returns None."""
        event = service.get_event("nonexistent_id")
        assert event is None


class TestQuerying:
    """Tests for query capabilities."""

    def test_query_by_event_type(self, service):
        """Test filtering by event type."""
        service.record(event_type=AuditEventType.APPROVAL_REQUESTED, actor_id="u1", actor_type="user")
        service.record(event_type=AuditEventType.APPROVAL_GRANTED, actor_id="u2", actor_type="user")
        service.record(event_type=AuditEventType.ACCESS_DENIED, actor_id="u3", actor_type="user")

        results = service.query(event_types=[AuditEventType.APPROVAL_REQUESTED, AuditEventType.APPROVAL_GRANTED])

        assert len(results) == 2
        assert all(e.event_type in [AuditEventType.APPROVAL_REQUESTED, AuditEventType.APPROVAL_GRANTED] for e in results)

    def test_query_by_category(self, service):
        """Test filtering by category."""
        service.record(event_type=AuditEventType.ML_ROUTE_DECISION, actor_id="sys", actor_type="system")
        service.record(event_type=AuditEventType.APPROVAL_GRANTED, actor_id="u1", actor_type="user")
        service.record(event_type=AuditEventType.TEAM_MEMBER_ADDED, actor_id="u2", actor_type="user")

        results = service.query(categories=[AuditCategory.ROUTING, AuditCategory.TEAM])

        assert len(results) == 2

    def test_query_by_actor(self, service):
        """Test filtering by actor ID."""
        service.record(event_type=AuditEventType.ACCESS_GRANTED, actor_id="user_123", actor_type="user")
        service.record(event_type=AuditEventType.ACCESS_GRANTED, actor_id="user_456", actor_type="user")
        service.record(event_type=AuditEventType.ACCESS_GRANTED, actor_id="user_123", actor_type="user")

        results = service.query(actor_id="user_123")

        assert len(results) == 2
        assert all(e.actor_id == "user_123" for e in results)

    def test_query_by_workflow(self, service):
        """Test filtering by workflow ID."""
        service.record(
            event_type=AuditEventType.PHASE_STARTED,
            actor_id="sys",
            actor_type="system",
            workflow_id="wf_001",
        )
        service.record(
            event_type=AuditEventType.PHASE_COMPLETED,
            actor_id="sys",
            actor_type="system",
            workflow_id="wf_001",
        )
        service.record(
            event_type=AuditEventType.PHASE_STARTED,
            actor_id="sys",
            actor_type="system",
            workflow_id="wf_002",
        )

        results = service.query(workflow_id="wf_001")

        assert len(results) == 2
        assert all(e.workflow_id == "wf_001" for e in results)

    def test_query_by_time_range(self, service):
        """Test filtering by time range."""
        # Record some events
        for i in range(3):
            service.record(
                event_type=AuditEventType.GATE_CHECK_PASSED,
                actor_id="sys",
                actor_type="system",
            )

        now = datetime.utcnow()
        results = service.query(
            start_time=now - timedelta(minutes=5),
            end_time=now + timedelta(minutes=5),
        )

        assert len(results) == 3

    def test_query_with_pagination(self, service):
        """Test query pagination."""
        for i in range(10):
            service.record(
                event_type=AuditEventType.CONFIG_CHANGED,
                actor_id="admin",
                actor_type="user",
                metadata={"change": i},
            )

        page1 = service.query(limit=3, offset=0)
        page2 = service.query(limit=3, offset=3)

        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0].event_id != page2[0].event_id


class TestDecisionHistory:
    """Tests for decision history tracking."""

    def test_get_decision_history(self, service):
        """Test getting decision history for a workflow."""
        workflow_id = "wf_test_001"

        service.record(
            event_type=AuditEventType.ML_ROUTE_DECISION,
            actor_id="ml_router",
            actor_type="system",
            workflow_id=workflow_id,
            decision="backend",
        )
        service.record(
            event_type=AuditEventType.USER_ROUTE_OVERRIDE,
            actor_id="user_1",
            actor_type="user",
            workflow_id=workflow_id,
            decision="frontend",
        )
        service.record(
            event_type=AuditEventType.PHASE_STARTED,
            actor_id="sys",
            actor_type="system",
            workflow_id=workflow_id,
        )

        history = service.get_decision_history(workflow_id)

        assert len(history) == 2
        assert any(e.event_type == AuditEventType.ML_ROUTE_DECISION for e in history)
        assert any(e.event_type == AuditEventType.USER_ROUTE_OVERRIDE for e in history)

    def test_get_override_history(self, service):
        """Test getting override history."""
        service.record(
            event_type=AuditEventType.USER_ROUTE_OVERRIDE,
            actor_id="user_1",
            actor_type="user",
            reason_code=ReasonCode.MANUAL_OVERRIDE,
        )
        service.record(
            event_type=AuditEventType.TEAM_COMPOSITION_OVERRIDE,
            actor_id="user_2",
            actor_type="user",
            reason_code=ReasonCode.ESCALATION,
        )
        service.record(
            event_type=AuditEventType.ML_ROUTE_DECISION,
            actor_id="sys",
            actor_type="system",
        )

        overrides = service.get_override_history()

        assert len(overrides) == 2
        assert all(e.event_type in [AuditEventType.USER_ROUTE_OVERRIDE, AuditEventType.TEAM_COMPOSITION_OVERRIDE] for e in overrides)


class TestEvidencePack:
    """Tests for evidence pack export."""

    def test_export_evidence_pack(self, service):
        """Test exporting an evidence pack."""
        workflow_id = "wf_evidence_test"

        for i in range(5):
            service.record(
                event_type=AuditEventType.GATE_CHECK_PASSED,
                actor_id="sys",
                actor_type="system",
                workflow_id=workflow_id,
            )

        pack = service.export_evidence_pack(
            workflow_id=workflow_id,
            description="Test evidence pack",
            created_by="test_user",
        )

        assert pack.pack_id.startswith("evid_")
        assert len(pack.events) == 5
        assert pack.summary["total_events"] == 5
        assert pack.checksum is not None

    def test_evidence_pack_summary(self, service):
        """Test evidence pack summary generation."""
        service.record(event_type=AuditEventType.PHASE_STARTED, actor_id="sys", actor_type="system")
        service.record(event_type=AuditEventType.PHASE_COMPLETED, actor_id="sys", actor_type="system")
        service.record(event_type=AuditEventType.APPROVAL_GRANTED, actor_id="user_1", actor_type="user")

        pack = service.export_evidence_pack(description="Summary test")

        assert "by_type" in pack.summary
        assert "by_category" in pack.summary
        assert "actors" in pack.summary
        assert "sys" in pack.summary["actors"]
        assert "user_1" in pack.summary["actors"]

    def test_evidence_pack_records_export_event(self, service):
        """Test that exporting records an audit event."""
        service.record(event_type=AuditEventType.CONFIG_CHANGED, actor_id="admin", actor_type="user")

        initial_count = len(service.query())

        pack = service.export_evidence_pack(description="Export test", created_by="exporter")

        # Should have one more event (the export itself)
        final_count = len(service.query())
        assert final_count == initial_count + 1

        export_events = service.query(event_types=[AuditEventType.DATA_EXPORTED])
        assert len(export_events) == 1
        assert export_events[0].metadata["pack_id"] == pack.pack_id


class TestStatistics:
    """Tests for statistics and reporting."""

    def test_get_statistics(self, service):
        """Test getting audit statistics."""
        service.record(event_type=AuditEventType.ML_ROUTE_DECISION, actor_id="sys", actor_type="system")
        service.record(event_type=AuditEventType.USER_ROUTE_OVERRIDE, actor_id="user", actor_type="user")
        service.record(event_type=AuditEventType.APPROVAL_GRANTED, actor_id="approver", actor_type="user")
        service.record(event_type=AuditEventType.SECURITY_EVENT, actor_id="sys", actor_type="system")

        stats = service.get_statistics()

        assert stats["total_events"] == 4
        assert stats["overrides_count"] == 1
        assert stats["security_events_count"] == 1
        assert "routing" in stats["by_category"]
        assert "approval" in stats["by_category"]

    def test_statistics_with_time_range(self, service):
        """Test statistics with time filtering."""
        for i in range(3):
            service.record(
                event_type=AuditEventType.PHASE_STARTED,
                actor_id="sys",
                actor_type="system",
            )

        now = datetime.utcnow()
        stats = service.get_statistics(
            start_time=now - timedelta(minutes=5),
            end_time=now + timedelta(minutes=5),
        )

        assert stats["total_events"] == 3


class TestCallbacks:
    """Tests for event callbacks."""

    def test_event_callback(self, service):
        """Test callback is triggered on new events."""
        callback = MagicMock()
        service.set_event_callback(callback)

        event = service.record(
            event_type=AuditEventType.ACCESS_GRANTED,
            actor_id="user",
            actor_type="user",
        )

        callback.assert_called_once()
        assert callback.call_args[0][0].event_id == event.event_id


class TestEventSerialization:
    """Tests for event serialization."""

    def test_event_to_dict_and_back(self):
        """Test event serialization round-trip."""
        event = AuditEvent(
            event_id="test_123",
            event_type=AuditEventType.APPROVAL_GRANTED,
            category=AuditCategory.APPROVAL,
            timestamp=datetime.utcnow(),
            actor_id="approver_1",
            actor_type="user",
            actor_name="Jane Approver",
            decision="approved",
            reason_code=ReasonCode.REQUIREMENTS_MET,
            previous_state={"status": "pending"},
            new_state={"status": "approved"},
            metadata={"priority": "high"},
            tags=["urgent", "reviewed"],
            checksum="abc123",
        )

        data = event.to_dict()
        restored = AuditEvent.from_dict(data)

        assert restored.event_id == event.event_id
        assert restored.event_type == event.event_type
        assert restored.category == event.category
        assert restored.reason_code == event.reason_code
        assert restored.previous_state == event.previous_state
        assert restored.tags == event.tags


class TestSingletonPattern:
    """Tests for singleton pattern."""

    def test_singleton_instance(self):
        """Test singleton returns same instance."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Reset global singleton
            import services.audit_trail_service as module
            module._audit_trail_service = None

            service1 = get_audit_trail_service(db_path)
            service2 = get_audit_trail_service(db_path)

            assert service1 is service2
        finally:
            os.unlink(db_path)


class TestReset:
    """Tests for reset functionality."""

    def test_reset_clears_state(self, service):
        """Test reset clears all state."""
        service.record(
            event_type=AuditEventType.CONFIG_CHANGED,
            actor_id="admin",
            actor_type="user",
        )
        callback = MagicMock()
        service.set_event_callback(callback)

        service.reset()

        assert len(service._recent_events) == 0
        assert service._on_event is None
        assert service._last_checksum is None

        stats = service.get_statistics()
        assert stats["total_events"] == 0


class TestReasonCodes:
    """Tests for reason code handling."""

    def test_various_reason_codes(self, service):
        """Test recording events with different reason codes."""
        codes = [
            ReasonCode.ML_CONFIDENCE_HIGH,
            ReasonCode.MANUAL_OVERRIDE,
            ReasonCode.EMERGENCY,
            ReasonCode.REQUIREMENTS_MET,
        ]

        for code in codes:
            event = service.record(
                event_type=AuditEventType.USER_ROUTE_OVERRIDE,
                actor_id="user",
                actor_type="user",
                reason_code=code,
            )
            assert event.reason_code == code

        # Query and verify persistence
        events = service.query()
        assert len(events) == 4
        for event in events:
            assert event.reason_code in codes
