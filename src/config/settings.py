#!/usr/bin/env python3
"""
MAESTRO Settings Configuration

Centralized configuration using Pydantic Settings with environment variable support.
All hardcoded values should be moved here.
"""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized MAESTRO configuration

    All settings can be overridden via environment variables.
    Priority: Environment Variables > .env file > Defaults
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="allow"
    )

    # ==================== SERVICE CONFIGURATION ====================

    # MAESTRO Engine
    engine_host: str = Field(default="0.0.0.0", description="Engine host")
    engine_port: int = Field(default=5000, description="Engine port")
    engine_url: str = Field(default="http://localhost:5000", description="Engine URL")
    engine_reload: bool = Field(default=True, description="Enable auto-reload in dev")

    # Unified BFF Service
    bff_host: str = Field(default="0.0.0.0", description="BFF host")
    bff_port: int = Field(default=4001, description="BFF port")
    bff_url: str = Field(default="http://localhost:4001", description="BFF URL")
    bff_reload: bool = Field(default=True, description="Enable auto-reload in dev")

    # Frontend
    frontend_url: str = Field(default="http://localhost:4200", description="Frontend URL")
    frontend_port: int = Field(default=4200, description="Frontend port")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_ttl: int = Field(default=3600, description="Default Redis TTL (seconds)")

    # ==================== FILE PATHS ====================

    # Working directories
    projects_dir: Path = Field(
        default=Path("/tmp/maestro_projects"), description="Base directory for project workspaces"
    )
    output_dir: Path = Field(
        default=Path("/tmp/maestro_output"), description="Base directory for output files"
    )
    temp_dir: Path = Field(
        default=Path("/tmp/maestro_temp"), description="Temporary files directory"
    )

    # Log file paths
    engine_log_file: Path = Field(
        default=Path("/tmp/maestro_engine.log"), description="Engine log file path"
    )
    bff_log_file: Path = Field(
        default=Path("/tmp/bff_service.log"), description="BFF service log file path"
    )

    # PID file paths
    engine_pid_file: Path = Field(
        default=Path("/tmp/maestro_engine.pid"), description="Engine PID file path"
    )
    bff_pid_file: Path = Field(
        default=Path("/tmp/bff_service.pid"), description="BFF PID file path"
    )

    # Persona definitions
    personas_dir: Path = Field(
        default=Path(__file__).parent.parent / "personas" / "definitions",
        description="Directory containing persona JSON definitions",
    )

    # ==================== SERVICE INTEGRATION ====================

    # Quality Fabric
    quality_fabric_enabled: bool = Field(
        default=False, description="Enable Quality Fabric integration"
    )
    quality_fabric_url: str = Field(
        default="http://localhost:8000", description="Quality Fabric service URL"
    )

    # Template Registry
    template_registry_enabled: bool = Field(default=False, description="Enable Template Registry")
    template_registry_url: str = Field(
        default="http://localhost:9600", description="Template Registry service URL"
    )

    # RAG Service
    rag_enabled: bool = Field(default=False, description="Enable RAG context enhancement")
    rag_service_url: str = Field(default="http://localhost:9803", description="RAG service URL")
    chroma_persist_dir: Path = Field(
        default=Path("./chroma_db"), description="ChromaDB persistence directory"
    )
    rag_embedding_model: str = Field(default="all-MiniLM-L6-v2", description="RAG embedding model")

    # ==================== API & SECURITY ====================

    # API Keys
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    github_token: Optional[str] = Field(default=None, description="GitHub personal access token")

    # CORS
    cors_origins: List[str] = Field(default=["*"], description="Allowed CORS origins")

    # JWT Security
    jwt_secret_key: str = Field(
        default="change_this_in_production_use_secrets_manager", description="JWT secret key"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiry_minutes: int = Field(default=60, description="JWT token expiry in minutes")

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests: int = Field(default=100, description="Max requests per window")
    rate_limit_window: int = Field(default=60, description="Rate limit window (seconds)")

    # ==================== WORKFLOW CONFIGURATION ====================

    # Session management
    session_ttl: int = Field(default=3600, description="Session TTL (seconds)")
    max_concurrent_workflows: int = Field(
        default=10, description="Max concurrent workflow executions"
    )

    # Execution modes
    enable_parallel_execution: bool = Field(
        default=True, description="Enable parallel persona execution"
    )
    enable_hierarchical_mode: bool = Field(
        default=True, description="Enable hierarchical team organization"
    )
    enable_sequential_mode: bool = Field(default=True, description="Enable sequential execution")

    # Workflow defaults
    default_execution_mode: str = Field(
        default="dag", description="Default execution mode: dag, parallel, sequential, hierarchical"
    )
    workflow_timeout: int = Field(default=3600, description="Workflow execution timeout (seconds)")
    persona_timeout: int = Field(
        default=300, description="Single persona execution timeout (seconds)"
    )

    # MCP/UTCP
    enable_mcp: bool = Field(default=True, description="Enable MCP event emission")
    mcp_cache_dir: Path = Field(default=Path("/tmp/mcp_cache"), description="MCP cache directory")
    mcp_cache_ttl: int = Field(default=3600, description="MCP cache TTL (seconds)")

    # ==================== LOGGING & MONITORING ====================

    # Logging
    log_level: str = Field(
        default="INFO", description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    log_format: str = Field(default="json", description="Log format: json or text")
    enable_structured_logging: bool = Field(default=True, description="Enable structured logging")

    # Metrics & Monitoring
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    metrics_port: int = Field(default=9090, description="Metrics endpoint port")

    # OpenTelemetry
    otel_enabled: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    otel_service_name: str = Field(default="maestro-engine", description="OTEL service name")
    otel_exporter_endpoint: str = Field(
        default="http://localhost:4317", description="OTEL exporter endpoint"
    )

    # ==================== ENVIRONMENT ====================

    environment: str = Field(
        default="development", description="Environment: development, staging, production"
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    version: str = Field(default="3.0.0", description="MAESTRO version")

    # ==================== HELPER METHODS ====================

    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment.lower() == "development"

    def get_project_dir(self, session_id: str) -> Path:
        """Get project directory for a session"""
        project_dir = self.projects_dir / f"guardian_{session_id}"
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir

    def get_redis_connection_params(self) -> dict:
        """Get Redis connection parameters"""
        return {
            "host": self.redis_host,
            "port": self.redis_port,
            "db": self.redis_db,
            "decode_responses": True,
        }

    def ensure_directories(self):
        """Ensure all required directories exist"""
        directories = [
            self.projects_dir,
            self.output_dir,
            self.temp_dir,
            self.mcp_cache_dir,
            self.chroma_persist_dir.parent if self.chroma_persist_dir else None,
        ]

        for directory in directories:
            if directory:
                Path(directory).mkdir(parents=True, exist_ok=True)


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get or create settings singleton instance

    Returns:
        Settings: Global settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
        # Ensure required directories exist
        _settings.ensure_directories()
    return _settings


# Convenience function to reload settings
def reload_settings() -> Settings:
    """
    Reload settings from environment/config files

    Returns:
        Settings: Freshly loaded settings instance
    """
    global _settings
    _settings = None
    return get_settings()
