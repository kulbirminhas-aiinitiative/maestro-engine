"""
Core audit logger implementation
"""

import hashlib
import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import AuditConfig
from .models import (
    AuditError,
    AuditSession,
    ChatInteraction,
    FileOperation,
    PerformanceMetric,
    PersonaActivity,
    ToolUsage,
)

logger = logging.getLogger(__name__)


class AuditLogger:
    """Comprehensive audit logging for AI workflows and chat interactions"""

    def __init__(self, config: AuditConfig):
        """Initialize audit logger with configuration"""
        self.config = config
        self.session = AuditSession(
            session_id=config.session_id,
            start_time=datetime.now(timezone.utc).isoformat(),
            project_path=str(config.project_path),
            full_content_logging=config.full_content_logging,
            python_version=f"{__import__('sys').version_info.major}.{__import__('sys').version_info.minor}",
            custom_metadata=config.custom_metadata or {},
        )

        # Setup directory structure
        self.audit_path = config.project_path / config.audit_dir_name
        self.audit_path.mkdir(exist_ok=True)

        self.full_interactions_path = self.audit_path / config.full_interactions_dir_name
        if config.full_content_logging:
            self.full_interactions_path.mkdir(exist_ok=True)

        # Initialize log files
        self._setup_log_files()

        # In-memory collections for fast access
        self.chat_interactions: List[ChatInteraction] = []
        self.persona_activities: List[PersonaActivity] = []
        self.tool_usages: List[ToolUsage] = []
        self.file_operations: List[FileOperation] = []
        self.performance_metrics: List[PerformanceMetric] = []
        self.errors: List[AuditError] = []

        logger.info(f"🔍 Audit logger initialized for session: {config.session_id}")
        logger.info(
            f"📋 Full content logging: {'ENABLED' if config.full_content_logging else 'DISABLED'}"
        )

    def _setup_log_files(self):
        """Setup log file paths"""
        session_id = self.config.session_id
        self.chat_log_file = self.audit_path / f"chat_interactions_{session_id}.jsonl"
        self.persona_log_file = self.audit_path / f"persona_activities_{session_id}.jsonl"
        self.tool_log_file = self.audit_path / f"tool_usage_{session_id}.jsonl"
        self.file_log_file = self.audit_path / f"file_operations_{session_id}.jsonl"
        self.performance_log_file = self.audit_path / f"performance_metrics_{session_id}.jsonl"
        self.errors_log_file = self.audit_path / f"errors_{session_id}.jsonl"
        self.session_file = self.audit_path / f"session_{session_id}.json"

    def log_chat_interaction(
        self,
        interaction_type: str,
        prompt: str = None,
        response: str = None,
        model: str = None,
        tokens_used: int = None,
        duration_seconds: float = None,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """Log chat interactions with Claude API"""

        interaction = ChatInteraction(
            session_id=self.config.session_id,
            interaction_type=interaction_type,
            model=model,
            tokens_used=tokens_used,
            duration_seconds=duration_seconds,
            metadata=metadata or {},
            store_full_content=self.config.full_content_logging,
        )

        # Process content
        if prompt:
            interaction.prompt_length = len(prompt)
            interaction.prompt_hash = (
                hashlib.sha256(prompt.encode()).hexdigest()
                if self.config.store_content_hashes
                else None
            )
            interaction.prompt_preview = (
                prompt[: self.config.max_preview_length] + "..."
                if len(prompt) > self.config.max_preview_length
                else prompt
            )

            if self.config.full_content_logging:
                interaction.prompt_full = prompt

        if response:
            interaction.response_length = len(response)
            interaction.response_hash = (
                hashlib.sha256(response.encode()).hexdigest()
                if self.config.store_content_hashes
                else None
            )
            interaction.response_preview = (
                response[: self.config.max_preview_length] + "..."
                if len(response) > self.config.max_preview_length
                else response
            )

            if self.config.full_content_logging:
                interaction.response_full = response

        # Store interaction
        self.chat_interactions.append(interaction)
        self._write_log_entry(self.chat_log_file, interaction.to_dict())

        # Save full content to separate files if enabled
        if self.config.full_content_logging and (prompt or response):
            self._save_full_interaction_content(interaction, prompt, response)

        # Update session statistics
        self.session.chat_interactions_count += 1

        logger.info(
            f"💬 Chat interaction logged: {interaction_type} ({interaction.interaction_id[:8]}) [Full: {self.config.full_content_logging}]"
        )
        return interaction.interaction_id

    def log_persona_activity(
        self,
        persona: str,
        activity: str,
        details: Dict[str, Any] = None,
        duration_seconds: float = None,
    ) -> str:
        """Log persona-specific activities"""

        activity_log = PersonaActivity(
            session_id=self.config.session_id,
            persona=persona,
            activity=activity,
            details=details or {},
            duration_seconds=duration_seconds,
        )

        self.persona_activities.append(activity_log)
        self._write_log_entry(self.persona_log_file, activity_log.to_dict())

        # Update session statistics
        self.session.persona_activities_count += 1

        logger.info(f"👤 Persona activity logged: {persona} - {activity}")
        return activity_log.activity_id

    def log_tool_usage(
        self,
        tool_name: str,
        operation: str,
        parameters: Dict[str, Any] = None,
        result: Dict[str, Any] = None,
        success: bool = True,
        error: str = None,
        duration_seconds: float = None,
    ) -> str:
        """Log tool usage and API calls"""

        # Create result summary
        result_summary = {"success": success, "result_size": len(str(result)) if result else 0}

        if result and self.config.store_content_hashes:
            result_summary["result_hash"] = hashlib.sha256(str(result).encode()).hexdigest()

        tool_log = ToolUsage(
            session_id=self.config.session_id,
            tool_name=tool_name,
            operation=operation,
            parameters=parameters or {},
            result_summary=result_summary,
            success=success,
            error=error,
            duration_seconds=duration_seconds,
        )

        self.tool_usages.append(tool_log)
        self._write_log_entry(self.tool_log_file, tool_log.to_dict())

        # Update session statistics
        self.session.tool_usages_count += 1

        status = "✅" if success else "❌"
        logger.info(f"🔧 Tool usage logged: {status} {tool_name}.{operation}")
        return tool_log.usage_id

    def log_file_operation(
        self,
        operation: str,
        file_path: str,
        file_size: int = None,
        file_hash: str = None,
        success: bool = True,
        error: str = None,
    ) -> str:
        """Log file creation, modification, and deletion operations"""

        file_log = FileOperation(
            session_id=self.config.session_id,
            operation=operation,
            file_path=file_path,
            file_size=file_size,
            file_hash=file_hash,
            success=success,
            error=error,
        )

        self.file_operations.append(file_log)
        self._write_log_entry(self.file_log_file, file_log.to_dict())

        # Update session statistics
        self.session.file_operations_count += 1

        status = "✅" if success else "❌"
        logger.info(f"📁 File operation logged: {status} {operation} - {Path(file_path).name}")
        return file_log.operation_id

    def log_performance_metric(
        self, metric_name: str, value: float, unit: str = "seconds", context: Dict[str, Any] = None
    ) -> str:
        """Log performance metrics and timing information"""

        metric = PerformanceMetric(
            session_id=self.config.session_id,
            metric_name=metric_name,
            value=value,
            unit=unit,
            context=context or {},
        )

        self.performance_metrics.append(metric)
        self._write_log_entry(self.performance_log_file, metric.to_dict())

        # Update session statistics
        self.session.performance_metrics_count += 1

        logger.info(f"📊 Performance metric logged: {metric_name} = {value} {unit}")
        return metric.metric_id

    def log_error(
        self,
        error_type: str,
        error_message: str,
        stack_trace: str = None,
        context: Dict[str, Any] = None,
    ) -> str:
        """Log errors and exceptions"""

        error_log = AuditError(
            session_id=self.config.session_id,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
            context=context or {},
        )

        self.errors.append(error_log)
        self._write_log_entry(self.errors_log_file, error_log.to_dict())

        # Update session statistics
        self.session.errors_count += 1

        logger.error(f"❌ Error logged: {error_type} - {error_message}")
        return error_log.error_id

    def _save_full_interaction_content(
        self, interaction: ChatInteraction, prompt: str = None, response: str = None
    ):
        """Save full interaction content to separate secure files"""

        interaction_id = interaction.interaction_id
        timestamp = interaction.timestamp

        # Save full prompt if provided
        if prompt:
            prompt_file = self.full_interactions_path / f"prompt_{interaction_id}.txt"
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(f"Interaction ID: {interaction_id}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"Type: {interaction.interaction_type}\n")
                f.write(f"Session: {self.config.session_id}\n")
                f.write("=" * 80 + "\n")
                f.write(prompt)

            # Log the secure file creation
            self.log_file_operation(
                operation="create_secure",
                file_path=str(prompt_file),
                file_size=len(prompt.encode("utf-8")),
                file_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                success=True,
            )

        # Save full response if provided
        if response:
            response_file = self.full_interactions_path / f"response_{interaction_id}.txt"
            with open(response_file, "w", encoding="utf-8") as f:
                f.write(f"Interaction ID: {interaction_id}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"Type: {interaction.interaction_type}\n")
                f.write(f"Session: {self.config.session_id}\n")
                f.write("=" * 80 + "\n")
                f.write(response)

            # Log the secure file creation
            self.log_file_operation(
                operation="create_secure",
                file_path=str(response_file),
                file_size=len(response.encode("utf-8")),
                file_hash=hashlib.sha256(response.encode("utf-8")).hexdigest(),
                success=True,
            )

        # Create interaction manifest
        manifest_file = self.full_interactions_path / f"manifest_{interaction_id}.json"
        manifest = {
            "interaction_id": interaction_id,
            "timestamp": timestamp,
            "type": interaction.interaction_type,
            "session_id": self.config.session_id,
            "prompt_file": f"prompt_{interaction_id}.txt" if prompt else None,
            "response_file": f"response_{interaction_id}.txt" if response else None,
            "prompt_size": len(prompt) if prompt else 0,
            "response_size": len(response) if response else 0,
            "model": interaction.model,
            "duration_seconds": interaction.duration_seconds,
            "metadata": interaction.metadata,
        }

        with open(manifest_file, "w") as f:
            json.dump(manifest, f, indent=2)

    def _write_log_entry(self, log_file: Path, entry: Dict[str, Any]):
        """Write a single log entry to the specified file"""
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log entry: {e}")

    def finalize_session(self) -> Dict[str, Any]:
        """Finalize the audit session and create summary"""

        session_end_time = datetime.now(timezone.utc)
        self.session.end_time = session_end_time.isoformat()
        self.session.duration_seconds = (
            session_end_time
            - datetime.fromisoformat(self.session.start_time.replace("Z", "+00:00"))
        ).total_seconds()

        # Calculate summaries
        chat_summary = self._calculate_chat_summary()
        persona_summary = self._calculate_persona_summary()
        tool_summary = self._calculate_tool_summary()
        file_summary = self._calculate_file_summary()

        # Create comprehensive audit summary
        audit_summary = {
            **self.session.to_dict(),
            "chat_summary": chat_summary,
            "persona_summary": persona_summary,
            "tool_summary": tool_summary,
            "file_summary": file_summary,
        }

        # Save session data
        with open(self.session_file, "w") as f:
            json.dump(audit_summary, f, indent=2)

        logger.info(f"📋 Audit session finalized: {self.session.duration_seconds:.2f}s total")
        logger.info(f"📊 Session data saved to: {self.session_file}")

        return audit_summary

    def _calculate_chat_summary(self) -> Dict[str, Any]:
        """Calculate chat interaction summary"""
        if not self.chat_interactions:
            return {"total_interactions": 0}

        return {
            "total_interactions": len(self.chat_interactions),
            "total_prompt_chars": sum(i.prompt_length for i in self.chat_interactions),
            "total_response_chars": sum(i.response_length for i in self.chat_interactions),
            "total_tokens": sum(i.tokens_used or 0 for i in self.chat_interactions),
            "average_response_time": sum(i.duration_seconds or 0 for i in self.chat_interactions)
            / len(self.chat_interactions),
        }

    def _calculate_persona_summary(self) -> Dict[str, Any]:
        """Calculate persona activity summary"""
        if not self.persona_activities:
            return {"total_activities": 0}

        personas = list(set(a.persona for a in self.persona_activities))
        activities_by_persona = {}
        for activity in self.persona_activities:
            persona = activity.persona
            if persona not in activities_by_persona:
                activities_by_persona[persona] = 0
            activities_by_persona[persona] += 1

        return {
            "active_personas": personas,
            "total_activities": len(self.persona_activities),
            "activities_by_persona": activities_by_persona,
        }

    def _calculate_tool_summary(self) -> Dict[str, Any]:
        """Calculate tool usage summary"""
        if not self.tool_usages:
            return {"total_operations": 0}

        tools = list(set(t.tool_name for t in self.tool_usages))
        success_count = sum(1 for t in self.tool_usages if t.success)

        return {
            "tools_used": tools,
            "total_operations": len(self.tool_usages),
            "success_rate": success_count / len(self.tool_usages),
        }

    def _calculate_file_summary(self) -> Dict[str, Any]:
        """Calculate file operations summary"""
        if not self.file_operations:
            return {"total_operations": 0}

        operations_by_type = {}
        total_size = 0
        files_created = []

        for operation in self.file_operations:
            op_type = operation.operation
            if op_type not in operations_by_type:
                operations_by_type[op_type] = 0
            operations_by_type[op_type] += 1

            if operation.file_size:
                total_size += operation.file_size

            if operation.operation == "create" and operation.success:
                files_created.append(operation.file_path)

        return {
            "total_operations": len(self.file_operations),
            "operations_by_type": operations_by_type,
            "files_created": files_created,
            "total_file_size": total_size,
        }
