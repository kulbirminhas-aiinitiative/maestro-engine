"""
MAESTRO Configuration Module

Centralized configuration management using environment variables and config files.
"""

from .settings import Settings, get_settings
from .workflow_config import WorkflowConfig, get_workflow_config

# Configuration for team_execution.py from shared folder
# These configs are required by AutonomousSDLCEngineV3_1_Resumable
CLAUDE_CONFIG = {
    "model": "claude-sonnet-4-20250514",
    "permission_mode": "acceptEdits",  # Auto-accept file edits
    "timeout": 600000,  # 10 minutes
    "max_retries": 3,
}

OUTPUT_CONFIG = {
    "default_output_dir": "./generated_project_v2",
    "preserve_history": True,  # Keep execution history
    "create_summary": True,  # Generate summary report
    "verbose": True,  # Detailed logging
}

__all__ = [
    "get_settings",
    "Settings",
    "get_workflow_config",
    "WorkflowConfig",
    "CLAUDE_CONFIG",
    "OUTPUT_CONFIG",
]
