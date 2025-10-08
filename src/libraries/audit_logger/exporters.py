"""
Audit data export functionality
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO

from .core import AuditLogger


class AuditExporter:
    """Export audit data in various formats"""

    def __init__(self, audit_logger: AuditLogger):
        """Initialize exporter with audit logger instance"""
        self.audit_logger = audit_logger
        self.config = audit_logger.config

    def export_to_json(
        self, output_path: Path, include_full_content: bool = False
    ) -> Dict[str, Any]:
        """Export all audit data to JSON format"""

        export_data = {
            "session": self.audit_logger.session.to_dict(),
            "chat_interactions": [i.to_dict() for i in self.audit_logger.chat_interactions],
            "persona_activities": [a.to_dict() for a in self.audit_logger.persona_activities],
            "tool_usages": [t.to_dict() for t in self.audit_logger.tool_usages],
            "file_operations": [f.to_dict() for f in self.audit_logger.file_operations],
            "performance_metrics": [m.to_dict() for m in self.audit_logger.performance_metrics],
            "errors": [e.to_dict() for e in self.audit_logger.errors],
            "export_metadata": {
                "export_timestamp": datetime.now().isoformat(),
                "export_type": "complete_json",
                "include_full_content": include_full_content,
                "total_records": (
                    len(self.audit_logger.chat_interactions)
                    + len(self.audit_logger.persona_activities)
                    + len(self.audit_logger.tool_usages)
                    + len(self.audit_logger.file_operations)
                    + len(self.audit_logger.performance_metrics)
                    + len(self.audit_logger.errors)
                ),
            },
        }

        # Include full content if requested and available
        if include_full_content and self.config.full_content_logging:
            full_content_index = self._create_full_content_index()
            export_data["full_content_index"] = full_content_index

        # Write export data
        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2)

        return export_data

    def export_chat_interactions_to_csv(self, output_path: Path) -> List[Dict[str, Any]]:
        """Export chat interactions to CSV format"""

        if not self.audit_logger.chat_interactions:
            return []

        fieldnames = [
            "interaction_id",
            "timestamp",
            "session_id",
            "interaction_type",
            "model",
            "prompt_length",
            "response_length",
            "tokens_used",
            "duration_seconds",
            "prompt_preview",
            "response_preview",
        ]

        with open(output_path, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for interaction in self.audit_logger.chat_interactions:
                row = {
                    "interaction_id": interaction.interaction_id,
                    "timestamp": interaction.timestamp,
                    "session_id": interaction.session_id,
                    "interaction_type": interaction.interaction_type,
                    "model": interaction.model,
                    "prompt_length": interaction.prompt_length,
                    "response_length": interaction.response_length,
                    "tokens_used": interaction.tokens_used,
                    "duration_seconds": interaction.duration_seconds,
                    "prompt_preview": interaction.prompt_preview,
                    "response_preview": interaction.response_preview,
                }
                writer.writerow(row)

        return [i.to_dict() for i in self.audit_logger.chat_interactions]

    def export_persona_activities_to_csv(self, output_path: Path) -> List[Dict[str, Any]]:
        """Export persona activities to CSV format"""

        if not self.audit_logger.persona_activities:
            return []

        fieldnames = [
            "activity_id",
            "timestamp",
            "session_id",
            "persona",
            "activity",
            "duration_seconds",
            "details_summary",
        ]

        with open(output_path, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for activity in self.audit_logger.persona_activities:
                row = {
                    "activity_id": activity.activity_id,
                    "timestamp": activity.timestamp,
                    "session_id": activity.session_id,
                    "persona": activity.persona,
                    "activity": activity.activity,
                    "duration_seconds": activity.duration_seconds,
                    "details_summary": (
                        str(activity.details)[:200] + "..."
                        if len(str(activity.details)) > 200
                        else str(activity.details)
                    ),
                }
                writer.writerow(row)

        return [a.to_dict() for a in self.audit_logger.persona_activities]

    def export_tool_usages_to_csv(self, output_path: Path) -> List[Dict[str, Any]]:
        """Export tool usages to CSV format"""

        if not self.audit_logger.tool_usages:
            return []

        fieldnames = [
            "usage_id",
            "timestamp",
            "session_id",
            "tool_name",
            "operation",
            "success",
            "duration_seconds",
            "error",
        ]

        with open(output_path, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for usage in self.audit_logger.tool_usages:
                row = {
                    "usage_id": usage.usage_id,
                    "timestamp": usage.timestamp,
                    "session_id": usage.session_id,
                    "tool_name": usage.tool_name,
                    "operation": usage.operation,
                    "success": usage.success,
                    "duration_seconds": usage.duration_seconds,
                    "error": usage.error,
                }
                writer.writerow(row)

        return [t.to_dict() for t in self.audit_logger.tool_usages]

    def export_file_operations_to_csv(self, output_path: Path) -> List[Dict[str, Any]]:
        """Export file operations to CSV format"""

        if not self.audit_logger.file_operations:
            return []

        fieldnames = [
            "operation_id",
            "timestamp",
            "session_id",
            "operation",
            "file_path",
            "file_size",
            "success",
            "error",
        ]

        with open(output_path, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for operation in self.audit_logger.file_operations:
                row = {
                    "operation_id": operation.operation_id,
                    "timestamp": operation.timestamp,
                    "session_id": operation.session_id,
                    "operation": operation.operation,
                    "file_path": operation.file_path,
                    "file_size": operation.file_size,
                    "success": operation.success,
                    "error": operation.error,
                }
                writer.writerow(row)

        return [f.to_dict() for f in self.audit_logger.file_operations]

    def export_performance_metrics_to_csv(self, output_path: Path) -> List[Dict[str, Any]]:
        """Export performance metrics to CSV format"""

        if not self.audit_logger.performance_metrics:
            return []

        fieldnames = [
            "metric_id",
            "timestamp",
            "session_id",
            "metric_name",
            "value",
            "unit",
            "context_summary",
        ]

        with open(output_path, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for metric in self.audit_logger.performance_metrics:
                row = {
                    "metric_id": metric.metric_id,
                    "timestamp": metric.timestamp,
                    "session_id": metric.session_id,
                    "metric_name": metric.metric_name,
                    "value": metric.value,
                    "unit": metric.unit,
                    "context_summary": (
                        str(metric.context)[:200] + "..."
                        if len(str(metric.context)) > 200
                        else str(metric.context)
                    ),
                }
                writer.writerow(row)

        return [m.to_dict() for m in self.audit_logger.performance_metrics]

    def export_errors_to_csv(self, output_path: Path) -> List[Dict[str, Any]]:
        """Export errors to CSV format"""

        if not self.audit_logger.errors:
            return []

        fieldnames = [
            "error_id",
            "timestamp",
            "session_id",
            "error_type",
            "error_message",
            "context_summary",
        ]

        with open(output_path, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for error in self.audit_logger.errors:
                row = {
                    "error_id": error.error_id,
                    "timestamp": error.timestamp,
                    "session_id": error.session_id,
                    "error_type": error.error_type,
                    "error_message": error.error_message,
                    "context_summary": (
                        str(error.context)[:200] + "..."
                        if len(str(error.context)) > 200
                        else str(error.context)
                    ),
                }
                writer.writerow(row)

        return [e.to_dict() for e in self.audit_logger.errors]

    def export_complete_audit_to_directory(
        self, output_dir: Path, include_full_content: bool = False
    ) -> Dict[str, Path]:
        """Export complete audit data to a directory with multiple formats"""

        output_dir.mkdir(parents=True, exist_ok=True)
        session_id = self.config.session_id

        export_files = {}

        # JSON export
        json_file = output_dir / f"complete_audit_{session_id}.json"
        self.export_to_json(json_file, include_full_content)
        export_files["complete_json"] = json_file

        # CSV exports
        csv_files = {
            "chat_interactions": output_dir / f"chat_interactions_{session_id}.csv",
            "persona_activities": output_dir / f"persona_activities_{session_id}.csv",
            "tool_usages": output_dir / f"tool_usages_{session_id}.csv",
            "file_operations": output_dir / f"file_operations_{session_id}.csv",
            "performance_metrics": output_dir / f"performance_metrics_{session_id}.csv",
            "errors": output_dir / f"errors_{session_id}.csv",
        }

        # Export each CSV if data exists
        if self.audit_logger.chat_interactions:
            self.export_chat_interactions_to_csv(csv_files["chat_interactions"])
            export_files["chat_interactions_csv"] = csv_files["chat_interactions"]

        if self.audit_logger.persona_activities:
            self.export_persona_activities_to_csv(csv_files["persona_activities"])
            export_files["persona_activities_csv"] = csv_files["persona_activities"]

        if self.audit_logger.tool_usages:
            self.export_tool_usages_to_csv(csv_files["tool_usages"])
            export_files["tool_usages_csv"] = csv_files["tool_usages"]

        if self.audit_logger.file_operations:
            self.export_file_operations_to_csv(csv_files["file_operations"])
            export_files["file_operations_csv"] = csv_files["file_operations"]

        if self.audit_logger.performance_metrics:
            self.export_performance_metrics_to_csv(csv_files["performance_metrics"])
            export_files["performance_metrics_csv"] = csv_files["performance_metrics"]

        if self.audit_logger.errors:
            self.export_errors_to_csv(csv_files["errors"])
            export_files["errors_csv"] = csv_files["errors"]

        # Create export summary
        summary_file = output_dir / f"export_summary_{session_id}.txt"
        with open(summary_file, "w") as f:
            f.write(f"Audit Export Summary\n")
            f.write(f"==================\n\n")
            f.write(f"Session ID: {session_id}\n")
            f.write(f"Export Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Include Full Content: {include_full_content}\n\n")

            f.write(f"Exported Files:\n")
            for export_type, file_path in export_files.items():
                f.write(f"  - {export_type}: {file_path.name}\n")

            f.write(f"\nData Summary:\n")
            f.write(f"  - Chat Interactions: {len(self.audit_logger.chat_interactions)}\n")
            f.write(f"  - Persona Activities: {len(self.audit_logger.persona_activities)}\n")
            f.write(f"  - Tool Usages: {len(self.audit_logger.tool_usages)}\n")
            f.write(f"  - File Operations: {len(self.audit_logger.file_operations)}\n")
            f.write(f"  - Performance Metrics: {len(self.audit_logger.performance_metrics)}\n")
            f.write(f"  - Errors: {len(self.audit_logger.errors)}\n")

        export_files["summary"] = summary_file

        return export_files

    def _create_full_content_index(self) -> Dict[str, Any]:
        """Create an index of full content files for chat interactions"""

        full_content_index = {"interactions": []}

        for interaction in self.audit_logger.chat_interactions:
            if interaction.store_full_content:
                interaction_id = interaction.interaction_id
                index_entry = {
                    "interaction_id": interaction_id,
                    "timestamp": interaction.timestamp,
                    "type": interaction.interaction_type,
                    "prompt_file": f"prompt_{interaction_id}.txt",
                    "response_file": f"response_{interaction_id}.txt",
                    "manifest_file": f"manifest_{interaction_id}.json",
                    "prompt_length": interaction.prompt_length,
                    "response_length": interaction.response_length,
                }
                full_content_index["interactions"].append(index_entry)

        return full_content_index
