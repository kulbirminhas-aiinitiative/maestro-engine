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

# RAG Template System Configuration
RAG_CONFIG = {
    # Template Registry
    "registry_base_url": "http://localhost:9600",
    "templates_base_path": "/home/ec2-user/projects/maestro-platform/maestro-templates/storage/templates",

    # Cache Settings
    "enable_cache": True,
    "cache_ttl_hours": 24,  # Cache templates for 24 hours
    "cache_dir": "/tmp/maestro_rag_cache",

    # Relevance Thresholds
    "high_relevance_threshold": 0.80,  # Show full template code
    "medium_relevance_threshold": 0.60,  # Show as inspiration
    "min_relevance_threshold": 0.40,  # Minimum to show at all

    # Search Parameters
    "max_templates_to_show": 5,  # Top N templates in prompt
    "max_templates_to_search": 20,  # Top N from search results
    "max_package_templates": 10,  # Max templates in package recommendation

    # Template Usage
    "enable_project_level_rag": True,  # Package recommendations
    "enable_persona_level_rag": True,  # Per-persona templates
    "include_template_code": True,  # Include full code for high relevance
    "require_usage_documentation": True,  # Personas must document template usage

    # Quality Filters
    "min_template_quality": 0.70,  # Minimum quality score to recommend
    "prefer_recent_templates": True,  # Weight recently used templates higher
    "prefer_high_usage_templates": True,  # Weight frequently used templates higher

    # Recommendation Engine
    "keyword_weight": 0.30,  # Weight for keyword matching
    "tag_weight": 0.20,  # Weight for tag matching
    "quality_weight": 0.20,  # Weight for template quality
    "tech_stack_weight": 0.20,  # Weight for tech stack compatibility
    "usage_stats_weight": 0.10,  # Weight for usage statistics
}

__all__ = [
    "get_settings",
    "Settings",
    "get_workflow_config",
    "WorkflowConfig",
    "CLAUDE_CONFIG",
    "OUTPUT_CONFIG",
    "RAG_CONFIG",
]
