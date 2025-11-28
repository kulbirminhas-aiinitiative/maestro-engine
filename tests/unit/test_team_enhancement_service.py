#!/usr/bin/env python3
"""
Unit tests for Team Enhancement Rationale & Override Service
Epic: MD-1819 [ME-800] Team Enhancement Rationale & Override

Tests cover all Acceptance Criteria:
- AC-1: Persona additions include rationale and confidence
- AC-2: Users can lock base team; backend respects lock
- AC-3: Audit logs include before/after diffs
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from services.team_enhancement_service import (
    TeamEnhancementService,
    PersonaEnhancement,
    AuditLogEntry,
    TeamEnhancementReport,
    EnhancementReason,
    OverrideAction,
    AuditEventType,
    get_team_enhancement_service,
)


class TestTeamEnhancementService:
    """Tests for TeamEnhancementService."""

    @pytest.fixture
    def service(self):
        """Create a fresh service instance for testing."""
        return TeamEnhancementService()

    @pytest.fixture
    def session_id(self):
        """Return a test session ID."""
        return "test_session_001"

    # ========================================================================
    # AC-1: Persona additions include rationale and confidence
    # ========================================================================

    def test_propose_enhancement_with_rationale(self, service, session_id):
        """AC-1: Persona additions include rationale."""
        enhancement = service.propose_enhancement(
            session_id=session_id,
            persona_id="security_specialist",
            persona_name="Security Specialist",
            reason=EnhancementReason.SECURITY_REQUIREMENT,
            rationale="Project requires PCI-DSS compliance review",
            confidence=0.85,
        )

        assert enhancement.rationale == "Project requires PCI-DSS compliance review"
        assert enhancement.reason == EnhancementReason.SECURITY_REQUIREMENT

    def test_propose_enhancement_with_confidence(self, service, session_id):
        """AC-1: Persona additions include confidence score."""
        enhancement = service.propose_enhancement(
            session_id=session_id,
            persona_id="qa_engineer",
            persona_name="QA Engineer",
            reason=EnhancementReason.QUALITY_ASSURANCE,
            rationale="Complex testing requirements detected",
            confidence=0.92,
        )

        assert enhancement.confidence == 0.92
        assert 0.0 <= enhancement.confidence <= 1.0

    def test_confidence_clamped_to_valid_range(self, service, session_id):
        """AC-1: Confidence is clamped to 0-1 range."""
        enhancement = service.propose_enhancement(
            session_id=session_id,
            persona_id="test_persona",
            persona_name="Test Persona",
            reason=EnhancementReason.SKILL_GAP,
            rationale="Test rationale",
            confidence=1.5,  # Over 1.0
        )

        assert enhancement.confidence == 1.0

    def test_get_enhancement_rationale(self, service, session_id):
        """AC-1: Can retrieve rationale for enhancements."""
        service.propose_enhancement(
            session_id=session_id,
            persona_id="architect",
            persona_name="Solution Architect",
            reason=EnhancementReason.ARCHITECTURE_NEED,
            rationale="Microservices architecture requires expert guidance",
            confidence=0.88,
        )

        enhancements = service.get_enhancement_rationale(session_id)
        assert len(enhancements) == 1
        assert enhancements[0].rationale == "Microservices architecture requires expert guidance"

    def test_get_enhancement_rationale_by_persona(self, service, session_id):
        """AC-1: Can filter rationale by persona."""
        service.propose_enhancement(
            session_id=session_id,
            persona_id="persona_a",
            persona_name="Persona A",
            reason=EnhancementReason.SKILL_GAP,
            rationale="Rationale A",
            confidence=0.7,
        )
        service.propose_enhancement(
            session_id=session_id,
            persona_id="persona_b",
            persona_name="Persona B",
            reason=EnhancementReason.DOMAIN_EXPERTISE,
            rationale="Rationale B",
            confidence=0.8,
        )

        enhancements = service.get_enhancement_rationale(session_id, persona_id="persona_a")
        assert len(enhancements) == 1
        assert enhancements[0].persona_id == "persona_a"

    def test_enhancement_has_all_required_fields(self, service, session_id):
        """AC-1: Enhancement has all required fields."""
        enhancement = service.propose_enhancement(
            session_id=session_id,
            persona_id="devops_engineer",
            persona_name="DevOps Engineer",
            reason=EnhancementReason.INTEGRATION_NEED,
            rationale="CI/CD pipeline setup required",
            confidence=0.75,
            proposed_by="system",
        )

        assert enhancement.enhancement_id is not None
        assert enhancement.persona_id == "devops_engineer"
        assert enhancement.persona_name == "DevOps Engineer"
        assert enhancement.reason == EnhancementReason.INTEGRATION_NEED
        assert enhancement.rationale == "CI/CD pipeline setup required"
        assert enhancement.confidence == 0.75
        assert enhancement.proposed_at is not None
        assert enhancement.proposed_by == "system"
        assert enhancement.status == "pending"

    # ========================================================================
    # AC-2: Users can lock base team; backend respects lock
    # ========================================================================

    def test_lock_team(self, service, session_id):
        """AC-2: Users can lock base team."""
        service.create_report(session_id, ["developer", "tester"])

        result = service.lock_team(
            session_id=session_id,
            locked_by="user_123",
            reason="Team finalized for sprint",
        )

        assert result is True
        assert service.is_team_locked(session_id) is True

    def test_unlock_team(self, service, session_id):
        """AC-2: Users can unlock team."""
        service.create_report(session_id, ["developer"])
        service.lock_team(session_id, "user_123")

        result = service.unlock_team(
            session_id=session_id,
            unlocked_by="user_123",
            reason="Need to add more personas",
        )

        assert result is True
        assert service.is_team_locked(session_id) is False

    def test_locked_team_blocks_enhancements(self, service, session_id):
        """AC-2: Backend respects lock - blocks enhancements."""
        service.create_report(session_id, ["developer"])
        service.lock_team(session_id, "user_123")

        with pytest.raises(ValueError, match="Team is locked"):
            service.propose_enhancement(
                session_id=session_id,
                persona_id="new_persona",
                persona_name="New Persona",
                reason=EnhancementReason.SKILL_GAP,
                rationale="Cannot add to locked team",
                confidence=0.9,
            )

    def test_get_team_lock_status(self, service, session_id):
        """AC-2: Can get detailed lock status."""
        service.create_report(session_id, ["developer"])
        service.lock_team(session_id, "user_123", "Sprint started")

        status = service.get_team_lock_status(session_id)

        assert status["is_locked"] is True
        assert status["locked_by"] == "user_123"
        assert status["lock_reason"] == "Sprint started"
        assert status["locked_at"] is not None

    def test_lock_status_for_nonexistent_session(self, service):
        """AC-2: Lock status for nonexistent session."""
        status = service.get_team_lock_status("nonexistent_session")

        assert status["is_locked"] is False
        assert status["session_exists"] is False

    # ========================================================================
    # AC-3: Audit logs include before/after diffs
    # ========================================================================

    def test_audit_log_on_enhancement_proposed(self, service, session_id):
        """AC-3: Audit log created when enhancement proposed."""
        service.propose_enhancement(
            session_id=session_id,
            persona_id="persona_1",
            persona_name="Persona 1",
            reason=EnhancementReason.SKILL_GAP,
            rationale="Test rationale",
            confidence=0.8,
        )

        audit_trail = service.get_audit_trail(session_id)
        assert len(audit_trail) >= 1

        # Find the enhancement proposed event
        proposed_events = [a for a in audit_trail if a.event_type == AuditEventType.ENHANCEMENT_PROPOSED]
        assert len(proposed_events) >= 1

    def test_audit_log_includes_before_after(self, service, session_id):
        """AC-3: Audit logs include before/after states."""
        service.create_report(session_id, ["developer"])
        service.lock_team(session_id, "user_123")

        audit_trail = service.get_audit_trail(session_id)
        lock_event = next(a for a in audit_trail if a.event_type == AuditEventType.TEAM_LOCKED)

        assert "before_state" in lock_event.to_dict()
        assert "after_state" in lock_event.to_dict()
        assert lock_event.before_state["is_locked"] is False
        assert lock_event.after_state["is_locked"] is True

    def test_audit_log_includes_diff(self, service, session_id):
        """AC-3: Audit logs include diffs."""
        service.create_report(session_id, ["developer"])
        service.lock_team(session_id, "user_123", "Sprint lock")

        audit_trail = service.get_audit_trail(session_id)
        lock_event = next(a for a in audit_trail if a.event_type == AuditEventType.TEAM_LOCKED)

        assert "diff" in lock_event.to_dict()
        assert lock_event.diff["action"] == "lock"

    def test_get_audit_diff_by_id(self, service, session_id):
        """AC-3: Can get diff by audit ID."""
        service.create_report(session_id, ["developer"])

        audit_trail = service.get_audit_trail(session_id)
        audit_id = audit_trail[0].audit_id

        diff = service.get_audit_diff(session_id, audit_id)

        assert diff is not None
        assert "before" in diff
        assert "after" in diff
        assert "diff" in diff

    def test_audit_trail_filter_by_event_type(self, service, session_id):
        """AC-3: Audit trail can be filtered by event type."""
        service.create_report(session_id, ["developer"])
        service.lock_team(session_id, "user_123")
        service.unlock_team(session_id, "user_123")

        lock_events = service.get_audit_trail(session_id, event_type=AuditEventType.TEAM_LOCKED)
        assert all(a.event_type == AuditEventType.TEAM_LOCKED for a in lock_events)

    def test_audit_trail_sorted_by_timestamp(self, service, session_id):
        """AC-3: Audit trail sorted by timestamp (newest first)."""
        service.create_report(session_id, ["developer"])
        service.lock_team(session_id, "user_123")
        service.unlock_team(session_id, "user_123")

        audit_trail = service.get_audit_trail(session_id)

        for i in range(len(audit_trail) - 1):
            assert audit_trail[i].timestamp >= audit_trail[i + 1].timestamp

    # ========================================================================
    # Enhancement Report Tests
    # ========================================================================

    def test_create_report(self, service, session_id):
        """Test creating enhancement report."""
        report = service.create_report(
            session_id=session_id,
            base_team=["developer", "tester", "designer"],
        )

        assert report.session_id == session_id
        assert report.base_team == ["developer", "tester", "designer"]
        assert report.enhanced_team == ["developer", "tester", "designer"]
        assert report.is_locked is False

    def test_get_report(self, service, session_id):
        """Test getting enhancement report."""
        service.create_report(session_id, ["developer"])

        report = service.get_report(session_id)

        assert report is not None
        assert report.session_id == session_id

    def test_get_report_nonexistent(self, service):
        """Test getting nonexistent report."""
        report = service.get_report("nonexistent_session")
        assert report is None

    def test_accept_enhancement(self, service, session_id):
        """Test accepting enhancement."""
        service.create_report(session_id, ["developer"])
        enhancement = service.propose_enhancement(
            session_id=session_id,
            persona_id="qa_engineer",
            persona_name="QA Engineer",
            reason=EnhancementReason.QUALITY_ASSURANCE,
            rationale="Need QA coverage",
            confidence=0.85,
        )

        result = service.accept_enhancement(
            session_id=session_id,
            enhancement_id=enhancement.enhancement_id,
            accepted_by="user_123",
        )

        assert result is True
        assert enhancement.status == "accepted"

        report = service.get_report(session_id)
        assert "qa_engineer" in report.enhanced_team

    def test_reject_enhancement(self, service, session_id):
        """Test rejecting enhancement."""
        service.create_report(session_id, ["developer"])
        enhancement = service.propose_enhancement(
            session_id=session_id,
            persona_id="persona_x",
            persona_name="Persona X",
            reason=EnhancementReason.SKILL_GAP,
            rationale="Suggested persona",
            confidence=0.6,
        )

        result = service.reject_enhancement(
            session_id=session_id,
            enhancement_id=enhancement.enhancement_id,
            rejected_by="user_123",
            rejection_reason="Not needed for this project",
        )

        assert result is True
        assert enhancement.status == "rejected"
        assert enhancement.rejection_reason == "Not needed for this project"

    def test_add_persona_override(self, service, session_id):
        """Test user override to add persona."""
        service.create_report(session_id, ["developer"])

        result = service.add_persona_override(
            session_id=session_id,
            persona_id="security_expert",
            persona_name="Security Expert",
            added_by="user_123",
            reason="Manual addition for security review",
        )

        assert result is True

        report = service.get_report(session_id)
        assert "security_expert" in report.enhanced_team

    def test_remove_persona_override(self, service, session_id):
        """Test user override to remove persona."""
        service.create_report(session_id, ["developer", "tester"])

        result = service.remove_persona_override(
            session_id=session_id,
            persona_id="tester",
            removed_by="user_123",
            reason="Tester not needed for this task",
        )

        assert result is True

        report = service.get_report(session_id)
        assert "tester" not in report.enhanced_team

    # ========================================================================
    # UI Badge Tests
    # ========================================================================

    def test_get_ui_badge_info_no_enhancements(self, service, session_id):
        """Test UI badge with no enhancements."""
        service.create_report(session_id, ["developer"])

        badge = service.get_ui_badge_info(session_id)

        assert badge["show_badge"] is False
        assert badge["enhanced"] is False
        assert badge["enhancement_count"] == 0

    def test_get_ui_badge_info_with_enhancements(self, service, session_id):
        """Test UI badge with enhancements."""
        service.create_report(session_id, ["developer"])
        enhancement = service.propose_enhancement(
            session_id=session_id,
            persona_id="qa_engineer",
            persona_name="QA Engineer",
            reason=EnhancementReason.QUALITY_ASSURANCE,
            rationale="Need QA",
            confidence=0.9,
        )
        service.accept_enhancement(session_id, enhancement.enhancement_id, "user_123")

        badge = service.get_ui_badge_info(session_id)

        assert badge["show_badge"] is True
        assert badge["enhanced"] is True
        assert badge["enhancement_count"] == 1
        assert "QA Engineer" in badge["added_personas"]

    def test_get_ui_badge_nonexistent_session(self, service):
        """Test UI badge for nonexistent session."""
        badge = service.get_ui_badge_info("nonexistent")

        assert badge["show_badge"] is False
        assert badge["enhanced"] is False

    # ========================================================================
    # Serialization Tests
    # ========================================================================

    def test_enhancement_to_dict(self, service, session_id):
        """Test enhancement serialization."""
        enhancement = service.propose_enhancement(
            session_id=session_id,
            persona_id="test_persona",
            persona_name="Test Persona",
            reason=EnhancementReason.SKILL_GAP,
            rationale="Test rationale",
            confidence=0.75,
        )

        data = enhancement.to_dict()

        assert "enhancement_id" in data
        assert "persona_id" in data
        assert "rationale" in data
        assert "confidence" in data
        assert data["confidence"] == 0.75

    def test_audit_entry_to_dict(self, service, session_id):
        """Test audit entry serialization."""
        service.create_report(session_id, ["developer"])

        audit_trail = service.get_audit_trail(session_id)
        data = audit_trail[0].to_dict()

        assert "audit_id" in data
        assert "event_type" in data
        assert "before_state" in data
        assert "after_state" in data
        assert "diff" in data

    def test_report_to_dict(self, service, session_id):
        """Test report serialization."""
        report = service.create_report(session_id, ["developer", "tester"])

        data = report.to_dict()

        assert "report_id" in data
        assert "session_id" in data
        assert "base_team" in data
        assert "enhanced_team" in data
        assert "enhancements" in data
        assert "enhancement_count" in data
        assert "accepted_count" in data

    # ========================================================================
    # Singleton Tests
    # ========================================================================

    def test_singleton_instance(self):
        """Test singleton pattern."""
        service1 = get_team_enhancement_service()
        service2 = get_team_enhancement_service()

        assert service1 is service2

    def test_service_info(self, service, session_id):
        """Test service info."""
        service.create_report(session_id, ["developer"])

        info = service.get_service_info()

        assert info["service"] == "team_enhancement_service"
        assert info["version"] == "1.0.0"
        assert info["total_reports"] >= 1


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
