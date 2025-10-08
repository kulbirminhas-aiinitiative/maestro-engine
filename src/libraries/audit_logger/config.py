"""
Configuration module for Audit Logger Library
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class AuditConfig:
    """Configuration class for audit logging"""

    # Basic configuration
    session_id: str
    project_path: Path
    full_content_logging: bool = True

    # File naming configuration
    audit_dir_name: str = "audit_logs"
    full_interactions_dir_name: str = "full_interactions"

    # Content storage configuration
    max_preview_length: int = 200
    store_content_hashes: bool = True
    compress_large_content: bool = False

    # Security configuration
    encrypt_sensitive_content: bool = False
    encryption_key: Optional[str] = None

    # Performance configuration
    async_logging: bool = False
    batch_write_size: int = 10
    max_memory_buffer: int = 1000  # Max entries in memory

    # Retention configuration
    max_log_age_days: int = 365
    auto_cleanup: bool = False

    # Export configuration
    default_export_format: str = "json"
    include_sensitive_data_in_exports: bool = False

    # Custom metadata
    custom_metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.encrypt_sensitive_content and not self.encryption_key:
            raise ValueError("encryption_key is required when encrypt_sensitive_content is True")

        if self.max_preview_length < 50:
            raise ValueError("max_preview_length must be at least 50 characters")

        if not isinstance(self.project_path, Path):
            self.project_path = Path(self.project_path)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "AuditConfig":
        """Create configuration from dictionary"""
        return cls(**config_dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "session_id": self.session_id,
            "project_path": str(self.project_path),
            "full_content_logging": self.full_content_logging,
            "audit_dir_name": self.audit_dir_name,
            "full_interactions_dir_name": self.full_interactions_dir_name,
            "max_preview_length": self.max_preview_length,
            "store_content_hashes": self.store_content_hashes,
            "compress_large_content": self.compress_large_content,
            "encrypt_sensitive_content": self.encrypt_sensitive_content,
            "async_logging": self.async_logging,
            "batch_write_size": self.batch_write_size,
            "max_memory_buffer": self.max_memory_buffer,
            "max_log_age_days": self.max_log_age_days,
            "auto_cleanup": self.auto_cleanup,
            "default_export_format": self.default_export_format,
            "include_sensitive_data_in_exports": self.include_sensitive_data_in_exports,
            "custom_metadata": self.custom_metadata,
        }


# Predefined configurations for common use cases
class PresetConfigs:
    """Predefined audit configurations for common scenarios"""

    @staticmethod
    def development(session_id: str, project_path: Path) -> AuditConfig:
        """Configuration for development environment"""
        return AuditConfig(
            session_id=session_id,
            project_path=project_path,
            full_content_logging=True,
            max_log_age_days=30,
            auto_cleanup=True,
        )

    @staticmethod
    def production(session_id: str, project_path: Path) -> AuditConfig:
        """Configuration for production environment"""
        return AuditConfig(
            session_id=session_id,
            project_path=project_path,
            full_content_logging=True,
            encrypt_sensitive_content=True,
            max_log_age_days=365,
            auto_cleanup=False,
            include_sensitive_data_in_exports=False,
        )

    @staticmethod
    def compliance(session_id: str, project_path: Path) -> AuditConfig:
        """Configuration for high-compliance environments"""
        return AuditConfig(
            session_id=session_id,
            project_path=project_path,
            full_content_logging=True,
            encrypt_sensitive_content=True,
            store_content_hashes=True,
            max_log_age_days=2555,  # 7 years
            auto_cleanup=False,
            include_sensitive_data_in_exports=False,
            custom_metadata={"compliance_level": "high", "retention_policy": "7_years"},
        )

    @staticmethod
    def minimal(session_id: str, project_path: Path) -> AuditConfig:
        """Minimal configuration for basic logging"""
        return AuditConfig(
            session_id=session_id,
            project_path=project_path,
            full_content_logging=False,
            store_content_hashes=False,
            max_log_age_days=7,
            auto_cleanup=True,
        )
