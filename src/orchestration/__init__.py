"""
MAESTRO Orchestration Module

Integrates Schema v3.0 personas with autonomous SDLC engine and team workflows.

NOTE: The main workflow API now uses AutonomousSDLCEngineV3_1_Resumable from
/home/ec2-user/projects/shared/claude_team_sdk/examples/sdlc_team/team_execution.py
which includes V3.1 persona-level intelligent reuse capabilities.

This module's AutonomousSDLCEngineV3Resumable is maintained for backward
compatibility with existing test scripts and examples.
"""

from .autonomous_sdlc_engine_v3_resumable import AutonomousSDLCEngineV3Resumable
from .session_manager import SDLCSession, SessionManager
from .team_organization import TeamOrganization, get_deliverables_for_persona

__all__ = [
    "AutonomousSDLCEngineV3Resumable",
    "SessionManager",
    "SDLCSession",
    "TeamOrganization",
    "get_deliverables_for_persona",
]
