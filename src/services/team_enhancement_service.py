#!/usr/bin/env python3
"""
Team Enhancement Rationale & Override Service
Implements Epic MD-1819 [ME-800] Team Enhancement Rationale & Override

Features:
- Capture why backend adds personas with rationale and confidence
- Team lock flag implementation for user control
- Audit trail for all overrides with before/after diffs
- Support for UI badge for enhanced teams

Acceptance Criteria:
- AC-1: Persona additions include rationale and confidence
- AC-2: Users can lock base team; backend respects lock
- AC-3: Audit logs include before/after diffs
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

logger = logging.getLogger("team_enhancement_service")


class EnhancementReason(str, Enum):
    """Reasons for persona enhancement."""
    COMPLEXITY_REQUIREMENT = "complexity_requirement"
    SECURITY_REQUIREMENT = "security_requirement"
    PERFORMANCE_REQUIREMENT = "performance_requirement"
    COMPLIANCE_REQUIREMENT = "compliance_requirement"
    SKILL_GAP = "skill_gap"
    DOMAIN_EXPERTISE = "domain_expertise"
    QUALITY_ASSURANCE = "quality_assurance"
    ARCHITECTURE_NEED = "architecture_need"
    INTEGRATION_NEED = "integration_need"
    USER_REQUESTED = "user_requested"


class OverrideAction(str, Enum):
    """Actions that can be taken on enhancements."""
    ADD_PERSONA = "add_persona"
    REMOVE_PERSONA = "remove_persona"
    LOCK_TEAM = "lock_team"
    UNLOCK_TEAM = "unlock_team"
    ACCEPT_ENHANCEMENT = "accept_enhancement"
    REJECT_ENHANCEMENT = "reject_enhancement"
    MODIFY_RATIONALE = "modify_rationale"


class AuditEventType(str, Enum):
    """Types of audit events."""
    TEAM_CREATED = "team_created"
    ENHANCEMENT_PROPOSED = "enhancement_proposed"
    ENHANCEMENT_ACCEPTED = "enhancement_accepted"
    ENHANCEMENT_REJECTED = "enhancement_rejected"
    TEAM_LOCKED = "team_locked"
    TEAM_UNLOCKED = "team_unlocked"
    PERSONA_ADDED = "persona_added"
    PERSONA_REMOVED = "persona_removed"
    OVERRIDE_APPLIED = "override_applied"


@dataclass
class PersonaEnhancement:
    """
    Represents a persona enhancement with rationale.
    AC-1: Persona additions include rationale and confidence.
    """
    enhancement_id: str
    persona_id: str
    persona_name: str
    reason: EnhancementReason
    rationale: str
    confidence: float  # 0.0 to 1.0
    proposed_at: str
    proposed_by: str  # "system" or user_id
    status: str = "pending"  # pending, accepted, rejected
    accepted_at: Optional[str] = None
    rejected_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enhancement_id": self.enhancement_id,
            "persona_id": self.persona_id,
            "persona_name": self.persona_name,
            "reason": self.reason.value if isinstance(self.reason, EnhancementReason) else self.reason,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "proposed_at": self.proposed_at,
            "proposed_by": self.proposed_by,
            "status": self.status,
            "accepted_at": self.accepted_at,
            "rejected_at": self.rejected_at,
            "rejection_reason": self.rejection_reason,
            "metadata": self.metadata,
        }


@dataclass
class AuditLogEntry:
    """
    Audit log entry for team changes.
    AC-3: Audit logs include before/after diffs.
    """
    audit_id: str
    session_id: str
    event_type: AuditEventType
    timestamp: str
    actor: str  # user_id or "system"
    before_state: Dict[str, Any]
    after_state: Dict[str, Any]
    diff: Dict[str, Any]
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "audit_id": self.audit_id,
            "session_id": self.session_id,
            "event_type": self.event_type.value if isinstance(self.event_type, AuditEventType) else self.event_type,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "diff": self.diff,
            "reason": self.reason,
            "metadata": self.metadata,
        }


@dataclass
class TeamEnhancementReport:
    """
    Team enhancement report artifact.
    Contains all enhancements and their statuses.
    """
    report_id: str
    session_id: str
    created_at: str
    base_team: List[str]
    enhanced_team: List[str]
    enhancements: List[PersonaEnhancement]
    is_locked: bool
    locked_by: Optional[str] = None
    locked_at: Optional[str] = None
    lock_reason: Optional[str] = None
    total_confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "report_id": self.report_id,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "base_team": self.base_team,
            "enhanced_team": self.enhanced_team,
            "enhancements": [e.to_dict() for e in self.enhancements],
            "is_locked": self.is_locked,
            "locked_by": self.locked_by,
            "locked_at": self.locked_at,
            "lock_reason": self.lock_reason,
            "total_confidence": self.total_confidence,
            "enhancement_count": len(self.enhancements),
            "accepted_count": sum(1 for e in self.enhancements if e.status == "accepted"),
            "rejected_count": sum(1 for e in self.enhancements if e.status == "rejected"),
            "pending_count": sum(1 for e in self.enhancements if e.status == "pending"),
            "metadata": self.metadata,
        }


class TeamEnhancementService:
    """
    Service for managing team enhancement rationale and overrides.

    Implements ME-800 acceptance criteria:
    - AC-1: Persona additions include rationale and confidence
    - AC-2: Users can lock base team; backend respects lock
    - AC-3: Audit logs include before/after diffs
    """

    def __init__(self):
        """Initialize the service."""
        # In-memory storage for demo (would use database in production)
        self._reports: Dict[str, TeamEnhancementReport] = {}
        self._audit_logs: Dict[str, List[AuditLogEntry]] = {}
        self._team_locks: Dict[str, bool] = {}

    # ========================================================================
    # AC-1: Persona additions include rationale and confidence
    # ========================================================================

    def propose_enhancement(
        self,
        session_id: str,
        persona_id: str,
        persona_name: str,
        reason: EnhancementReason,
        rationale: str,
        confidence: float,
        proposed_by: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PersonaEnhancement:
        """
        Propose a persona enhancement with rationale.

        AC-1: Persona additions include rationale and confidence.
        """
        # Check if team is locked
        if self.is_team_locked(session_id):
            raise ValueError(f"Team is locked for session {session_id}. Cannot propose enhancements.")

        enhancement = PersonaEnhancement(
            enhancement_id=f"enh_{uuid4().hex[:12]}",
            persona_id=persona_id,
            persona_name=persona_name,
            reason=reason,
            rationale=rationale,
            confidence=max(0.0, min(1.0, confidence)),  # Clamp to 0-1
            proposed_at=datetime.now().isoformat(),
            proposed_by=proposed_by,
            status="pending",
            metadata=metadata or {},
        )

        # Add to report
        report = self._get_or_create_report(session_id)
        report.enhancements.append(enhancement)
        self._update_report_confidence(report)

        # Create audit log
        self._log_audit(
            session_id=session_id,
            event_type=AuditEventType.ENHANCEMENT_PROPOSED,
            actor=proposed_by,
            before_state={"enhanced_team": report.enhanced_team.copy()},
            after_state={"enhanced_team": report.enhanced_team + [persona_id]},
            diff={"added": persona_id, "reason": reason.value, "confidence": confidence},
            reason=rationale,
        )

        logger.info(f"Proposed enhancement: {persona_name} for session {session_id} with confidence {confidence}")
        return enhancement

    def get_enhancement_rationale(
        self,
        session_id: str,
        persona_id: Optional[str] = None,
    ) -> List[PersonaEnhancement]:
        """
        Get enhancement rationale for a session.

        AC-1: Persona additions include rationale and confidence.
        """
        report = self._reports.get(session_id)
        if not report:
            return []

        if persona_id:
            return [e for e in report.enhancements if e.persona_id == persona_id]
        return report.enhancements

    # ========================================================================
    # AC-2: Users can lock base team; backend respects lock
    # ========================================================================

    def lock_team(
        self,
        session_id: str,
        locked_by: str,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Lock the team to prevent further enhancements.

        AC-2: Users can lock base team; backend respects lock.
        """
        report = self._get_or_create_report(session_id)

        before_state = {
            "is_locked": report.is_locked,
            "locked_by": report.locked_by,
        }

        report.is_locked = True
        report.locked_by = locked_by
        report.locked_at = datetime.now().isoformat()
        report.lock_reason = reason
        self._team_locks[session_id] = True

        after_state = {
            "is_locked": report.is_locked,
            "locked_by": report.locked_by,
        }

        # Create audit log
        self._log_audit(
            session_id=session_id,
            event_type=AuditEventType.TEAM_LOCKED,
            actor=locked_by,
            before_state=before_state,
            after_state=after_state,
            diff={"action": "lock", "reason": reason},
            reason=reason,
        )

        logger.info(f"Team locked for session {session_id} by {locked_by}")
        return True

    def unlock_team(
        self,
        session_id: str,
        unlocked_by: str,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Unlock the team to allow enhancements.

        AC-2: Users can lock base team; backend respects lock.
        """
        report = self._reports.get(session_id)
        if not report:
            return False

        before_state = {
            "is_locked": report.is_locked,
            "locked_by": report.locked_by,
        }

        report.is_locked = False
        report.locked_by = None
        report.locked_at = None
        report.lock_reason = None
        self._team_locks[session_id] = False

        after_state = {
            "is_locked": report.is_locked,
            "locked_by": report.locked_by,
        }

        # Create audit log
        self._log_audit(
            session_id=session_id,
            event_type=AuditEventType.TEAM_UNLOCKED,
            actor=unlocked_by,
            before_state=before_state,
            after_state=after_state,
            diff={"action": "unlock", "reason": reason},
            reason=reason,
        )

        logger.info(f"Team unlocked for session {session_id} by {unlocked_by}")
        return True

    def is_team_locked(self, session_id: str) -> bool:
        """
        Check if team is locked.

        AC-2: Backend respects lock.
        """
        return self._team_locks.get(session_id, False)

    def get_team_lock_status(self, session_id: str) -> Dict[str, Any]:
        """Get detailed lock status."""
        report = self._reports.get(session_id)
        if not report:
            return {"is_locked": False, "session_exists": False}

        return {
            "is_locked": report.is_locked,
            "locked_by": report.locked_by,
            "locked_at": report.locked_at,
            "lock_reason": report.lock_reason,
            "session_exists": True,
        }

    # ========================================================================
    # AC-3: Audit logs include before/after diffs
    # ========================================================================

    def get_audit_trail(
        self,
        session_id: str,
        event_type: Optional[AuditEventType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLogEntry]:
        """
        Get audit trail for a session.

        AC-3: Audit logs include before/after diffs.
        """
        logs = self._audit_logs.get(session_id, [])

        if event_type:
            logs = [l for l in logs if l.event_type == event_type]

        # Sort by timestamp descending
        logs = sorted(logs, key=lambda x: x.timestamp, reverse=True)

        return logs[offset:offset + limit]

    def get_audit_diff(self, session_id: str, audit_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the diff for a specific audit entry.

        AC-3: Audit logs include before/after diffs.
        """
        logs = self._audit_logs.get(session_id, [])
        for log in logs:
            if log.audit_id == audit_id:
                return {
                    "before": log.before_state,
                    "after": log.after_state,
                    "diff": log.diff,
                    "timestamp": log.timestamp,
                    "actor": log.actor,
                }
        return None

    # ========================================================================
    # Enhancement Report Management
    # ========================================================================

    def create_report(
        self,
        session_id: str,
        base_team: List[str],
        created_by: str = "system",
    ) -> TeamEnhancementReport:
        """Create a new team enhancement report."""
        report = TeamEnhancementReport(
            report_id=f"rpt_{uuid4().hex[:12]}",
            session_id=session_id,
            created_at=datetime.now().isoformat(),
            base_team=base_team.copy(),
            enhanced_team=base_team.copy(),
            enhancements=[],
            is_locked=False,
        )
        self._reports[session_id] = report

        # Create audit log
        self._log_audit(
            session_id=session_id,
            event_type=AuditEventType.TEAM_CREATED,
            actor=created_by,
            before_state={},
            after_state={"base_team": base_team},
            diff={"created": base_team},
        )

        logger.info(f"Created enhancement report for session {session_id}")
        return report

    def get_report(self, session_id: str) -> Optional[TeamEnhancementReport]:
        """Get the enhancement report for a session."""
        return self._reports.get(session_id)

    def accept_enhancement(
        self,
        session_id: str,
        enhancement_id: str,
        accepted_by: str,
    ) -> bool:
        """Accept a proposed enhancement."""
        report = self._reports.get(session_id)
        if not report:
            return False

        for enhancement in report.enhancements:
            if enhancement.enhancement_id == enhancement_id:
                before_status = enhancement.status
                enhancement.status = "accepted"
                enhancement.accepted_at = datetime.now().isoformat()

                # Add to enhanced team if not already there
                if enhancement.persona_id not in report.enhanced_team:
                    report.enhanced_team.append(enhancement.persona_id)

                # Create audit log
                self._log_audit(
                    session_id=session_id,
                    event_type=AuditEventType.ENHANCEMENT_ACCEPTED,
                    actor=accepted_by,
                    before_state={"status": before_status, "enhanced_team": report.enhanced_team[:-1]},
                    after_state={"status": "accepted", "enhanced_team": report.enhanced_team},
                    diff={"accepted": enhancement.persona_id, "enhancement_id": enhancement_id},
                )

                logger.info(f"Enhancement {enhancement_id} accepted by {accepted_by}")
                return True

        return False

    def reject_enhancement(
        self,
        session_id: str,
        enhancement_id: str,
        rejected_by: str,
        rejection_reason: Optional[str] = None,
    ) -> bool:
        """Reject a proposed enhancement."""
        report = self._reports.get(session_id)
        if not report:
            return False

        for enhancement in report.enhancements:
            if enhancement.enhancement_id == enhancement_id:
                before_status = enhancement.status
                enhancement.status = "rejected"
                enhancement.rejected_at = datetime.now().isoformat()
                enhancement.rejection_reason = rejection_reason

                # Remove from enhanced team if present
                if enhancement.persona_id in report.enhanced_team:
                    report.enhanced_team.remove(enhancement.persona_id)

                # Create audit log
                self._log_audit(
                    session_id=session_id,
                    event_type=AuditEventType.ENHANCEMENT_REJECTED,
                    actor=rejected_by,
                    before_state={"status": before_status},
                    after_state={"status": "rejected", "rejection_reason": rejection_reason},
                    diff={"rejected": enhancement.persona_id, "reason": rejection_reason},
                    reason=rejection_reason,
                )

                logger.info(f"Enhancement {enhancement_id} rejected by {rejected_by}")
                return True

        return False

    def add_persona_override(
        self,
        session_id: str,
        persona_id: str,
        persona_name: str,
        added_by: str,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Override: Add a persona directly (user action).
        Creates an accepted enhancement.
        """
        report = self._get_or_create_report(session_id)

        before_team = report.enhanced_team.copy()

        if persona_id not in report.enhanced_team:
            report.enhanced_team.append(persona_id)

        # Create enhancement record for this override
        enhancement = PersonaEnhancement(
            enhancement_id=f"enh_{uuid4().hex[:12]}",
            persona_id=persona_id,
            persona_name=persona_name,
            reason=EnhancementReason.USER_REQUESTED,
            rationale=reason or "User override - persona added directly",
            confidence=1.0,  # User actions have full confidence
            proposed_at=datetime.now().isoformat(),
            proposed_by=added_by,
            status="accepted",
            accepted_at=datetime.now().isoformat(),
        )
        report.enhancements.append(enhancement)

        # Create audit log
        self._log_audit(
            session_id=session_id,
            event_type=AuditEventType.PERSONA_ADDED,
            actor=added_by,
            before_state={"enhanced_team": before_team},
            after_state={"enhanced_team": report.enhanced_team},
            diff={"added": persona_id, "action": "user_override"},
            reason=reason,
        )

        logger.info(f"Persona {persona_name} added by user override")
        return True

    def remove_persona_override(
        self,
        session_id: str,
        persona_id: str,
        removed_by: str,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Override: Remove a persona directly (user action).
        """
        report = self._reports.get(session_id)
        if not report:
            return False

        before_team = report.enhanced_team.copy()

        if persona_id in report.enhanced_team:
            report.enhanced_team.remove(persona_id)

            # Create audit log
            self._log_audit(
                session_id=session_id,
                event_type=AuditEventType.PERSONA_REMOVED,
                actor=removed_by,
                before_state={"enhanced_team": before_team},
                after_state={"enhanced_team": report.enhanced_team},
                diff={"removed": persona_id, "action": "user_override"},
                reason=reason,
            )

            logger.info(f"Persona {persona_id} removed by user override")
            return True

        return False

    # ========================================================================
    # UI Support
    # ========================================================================

    def get_ui_badge_info(self, session_id: str) -> Dict[str, Any]:
        """
        Get badge information for UI display.
        Shows if team has been enhanced.
        """
        report = self._reports.get(session_id)
        if not report:
            return {
                "show_badge": False,
                "enhanced": False,
                "enhancement_count": 0,
            }

        enhancements = [e for e in report.enhancements if e.status == "accepted"]

        return {
            "show_badge": len(enhancements) > 0,
            "enhanced": len(report.enhanced_team) > len(report.base_team),
            "enhancement_count": len(enhancements),
            "pending_count": sum(1 for e in report.enhancements if e.status == "pending"),
            "is_locked": report.is_locked,
            "base_team_size": len(report.base_team),
            "current_team_size": len(report.enhanced_team),
            "added_personas": [e.persona_name for e in enhancements],
        }

    # ========================================================================
    # Internal Helpers
    # ========================================================================

    def _get_or_create_report(self, session_id: str) -> TeamEnhancementReport:
        """Get existing report or create new one."""
        if session_id not in self._reports:
            return self.create_report(session_id, [], "system")
        return self._reports[session_id]

    def _update_report_confidence(self, report: TeamEnhancementReport) -> None:
        """Update total confidence score for report."""
        accepted = [e for e in report.enhancements if e.status == "accepted"]
        if accepted:
            report.total_confidence = sum(e.confidence for e in accepted) / len(accepted)
        else:
            report.total_confidence = 0.0

    def _log_audit(
        self,
        session_id: str,
        event_type: AuditEventType,
        actor: str,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any],
        diff: Dict[str, Any],
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntry:
        """Create an audit log entry."""
        entry = AuditLogEntry(
            audit_id=f"aud_{uuid4().hex[:12]}",
            session_id=session_id,
            event_type=event_type,
            timestamp=datetime.now().isoformat(),
            actor=actor,
            before_state=before_state,
            after_state=after_state,
            diff=diff,
            reason=reason,
            metadata=metadata or {},
        )

        if session_id not in self._audit_logs:
            self._audit_logs[session_id] = []
        self._audit_logs[session_id].append(entry)

        return entry

    def get_service_info(self) -> Dict[str, Any]:
        """Get service information."""
        return {
            "service": "team_enhancement_service",
            "version": "1.0.0",
            "total_reports": len(self._reports),
            "total_audit_entries": sum(len(logs) for logs in self._audit_logs.values()),
            "locked_teams": sum(1 for v in self._team_locks.values() if v),
        }


# Singleton instance
_service_instance: Optional[TeamEnhancementService] = None


def get_team_enhancement_service() -> TeamEnhancementService:
    """Get the singleton service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = TeamEnhancementService()
    return _service_instance
