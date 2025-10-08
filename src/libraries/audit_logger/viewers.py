"""
Audit data viewing and analysis functionality
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .core import AuditLogger
from .models import ChatInteraction


class AuditViewer:
    """View and analyze audit data"""

    def __init__(self, audit_logger: AuditLogger = None, audit_path: Path = None):
        """Initialize viewer with either active logger or path to audit files"""
        self.audit_logger = audit_logger
        self.audit_path = audit_path

        if audit_logger:
            self.audit_path = audit_logger.audit_path

    def get_session_summary(self) -> Dict[str, Any]:
        """Get comprehensive session summary"""

        if self.audit_logger:
            return self._get_active_session_summary()
        else:
            return self._load_session_summary_from_files()

    def _get_active_session_summary(self) -> Dict[str, Any]:
        """Get summary from active audit logger"""

        return {
            "session_id": self.audit_logger.session.session_id,
            "start_time": self.audit_logger.session.start_time,
            "status": "active",
            "chat_interactions": len(self.audit_logger.chat_interactions),
            "persona_activities": len(self.audit_logger.persona_activities),
            "tool_usages": len(self.audit_logger.tool_usages),
            "file_operations": len(self.audit_logger.file_operations),
            "performance_metrics": len(self.audit_logger.performance_metrics),
            "errors": len(self.audit_logger.errors),
            "full_content_logging": self.audit_logger.config.full_content_logging,
        }

    def _load_session_summary_from_files(self) -> Dict[str, Any]:
        """Load session summary from audit files"""

        if not self.audit_path or not self.audit_path.exists():
            return {"error": "Audit path not found"}

        # Find session files
        session_files = list(self.audit_path.glob("session_*.json"))
        if not session_files:
            return {"error": "No session files found"}

        # Load the most recent session file
        latest_session_file = max(session_files, key=lambda f: f.stat().st_mtime)

        with open(latest_session_file, "r") as f:
            session_data = json.load(f)

        return session_data

    def get_chat_interactions(
        self, limit: int = None, interaction_type: str = None
    ) -> List[Dict[str, Any]]:
        """Get chat interactions with optional filtering"""

        if self.audit_logger:
            interactions = self.audit_logger.chat_interactions
        else:
            interactions = self._load_chat_interactions_from_files()

        # Filter by interaction type if specified
        if interaction_type:
            interactions = [i for i in interactions if i.interaction_type == interaction_type]

        # Convert to dict format
        interaction_dicts = [i.to_dict() if hasattr(i, "to_dict") else i for i in interactions]

        # Apply limit if specified
        if limit:
            interaction_dicts = interaction_dicts[-limit:]

        return interaction_dicts

    def _load_chat_interactions_from_files(self) -> List[ChatInteraction]:
        """Load chat interactions from JSONL files"""

        interactions = []
        chat_files = list(self.audit_path.glob("chat_interactions_*.jsonl"))

        for chat_file in chat_files:
            with open(chat_file, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        interaction = ChatInteraction(**data)
                        interactions.append(interaction)

        return interactions

    def get_full_interaction_content(self, interaction_id: str) -> Dict[str, Any]:
        """Get full content for a specific interaction"""

        if not self.audit_path:
            return {"error": "Audit path not available"}

        full_interactions_path = self.audit_path / "full_interactions"
        if not full_interactions_path.exists():
            return {"error": "Full content logging not enabled"}

        # Load manifest
        manifest_file = full_interactions_path / f"manifest_{interaction_id}.json"
        if not manifest_file.exists():
            return {"error": f"Manifest file not found for interaction {interaction_id}"}

        with open(manifest_file, "r") as f:
            manifest = json.load(f)

        result = {
            "interaction_id": interaction_id,
            "manifest": manifest,
            "prompt_content": None,
            "response_content": None,
        }

        # Load prompt content if available
        if manifest.get("prompt_file"):
            prompt_file = full_interactions_path / manifest["prompt_file"]
            if prompt_file.exists():
                with open(prompt_file, "r", encoding="utf-8") as f:
                    result["prompt_content"] = f.read()

        # Load response content if available
        if manifest.get("response_file"):
            response_file = full_interactions_path / manifest["response_file"]
            if response_file.exists():
                with open(response_file, "r", encoding="utf-8") as f:
                    result["response_content"] = f.read()

        return result

    def get_persona_activities(
        self, persona: str = None, limit: int = None
    ) -> List[Dict[str, Any]]:
        """Get persona activities with optional filtering"""

        if self.audit_logger:
            activities = self.audit_logger.persona_activities
        else:
            activities = self._load_persona_activities_from_files()

        # Filter by persona if specified
        if persona:
            activities = [a for a in activities if a.persona == persona]

        # Convert to dict format
        activity_dicts = [a.to_dict() if hasattr(a, "to_dict") else a for a in activities]

        # Apply limit if specified
        if limit:
            activity_dicts = activity_dicts[-limit:]

        return activity_dicts

    def _load_persona_activities_from_files(self) -> List[Dict[str, Any]]:
        """Load persona activities from JSONL files"""

        activities = []
        activity_files = list(self.audit_path.glob("persona_activities_*.jsonl"))

        for activity_file in activity_files:
            with open(activity_file, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        activities.append(data)

        return activities

    def get_tool_usages(
        self, tool_name: str = None, success_only: bool = False, limit: int = None
    ) -> List[Dict[str, Any]]:
        """Get tool usages with optional filtering"""

        if self.audit_logger:
            usages = self.audit_logger.tool_usages
        else:
            usages = self._load_tool_usages_from_files()

        # Filter by tool name if specified
        if tool_name:
            usages = [u for u in usages if u.tool_name == tool_name]

        # Filter by success if specified
        if success_only:
            usages = [u for u in usages if u.success]

        # Convert to dict format
        usage_dicts = [u.to_dict() if hasattr(u, "to_dict") else u for u in usages]

        # Apply limit if specified
        if limit:
            usage_dicts = usage_dicts[-limit:]

        return usage_dicts

    def _load_tool_usages_from_files(self) -> List[Dict[str, Any]]:
        """Load tool usages from JSONL files"""

        usages = []
        usage_files = list(self.audit_path.glob("tool_usage_*.jsonl"))

        for usage_file in usage_files:
            with open(usage_file, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        usages.append(data)

        return usages

    def get_file_operations(
        self, operation: str = None, success_only: bool = False, limit: int = None
    ) -> List[Dict[str, Any]]:
        """Get file operations with optional filtering"""

        if self.audit_logger:
            operations = self.audit_logger.file_operations
        else:
            operations = self._load_file_operations_from_files()

        # Filter by operation type if specified
        if operation:
            operations = [o for o in operations if o.operation == operation]

        # Filter by success if specified
        if success_only:
            operations = [o for o in operations if o.success]

        # Convert to dict format
        operation_dicts = [o.to_dict() if hasattr(o, "to_dict") else o for o in operations]

        # Apply limit if specified
        if limit:
            operation_dicts = operation_dicts[-limit:]

        return operation_dicts

    def _load_file_operations_from_files(self) -> List[Dict[str, Any]]:
        """Load file operations from JSONL files"""

        operations = []
        operation_files = list(self.audit_path.glob("file_operations_*.jsonl"))

        for operation_file in operation_files:
            with open(operation_file, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        operations.append(data)

        return operations

    def get_performance_metrics(
        self, metric_name: str = None, limit: int = None
    ) -> List[Dict[str, Any]]:
        """Get performance metrics with optional filtering"""

        if self.audit_logger:
            metrics = self.audit_logger.performance_metrics
        else:
            metrics = self._load_performance_metrics_from_files()

        # Filter by metric name if specified
        if metric_name:
            metrics = [m for m in metrics if m.metric_name == metric_name]

        # Convert to dict format
        metric_dicts = [m.to_dict() if hasattr(m, "to_dict") else m for m in metrics]

        # Apply limit if specified
        if limit:
            metric_dicts = metric_dicts[-limit:]

        return metric_dicts

    def _load_performance_metrics_from_files(self) -> List[Dict[str, Any]]:
        """Load performance metrics from JSONL files"""

        metrics = []
        metric_files = list(self.audit_path.glob("performance_metrics_*.jsonl"))

        for metric_file in metric_files:
            with open(metric_file, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        metrics.append(data)

        return metrics

    def get_errors(self, error_type: str = None, limit: int = None) -> List[Dict[str, Any]]:
        """Get errors with optional filtering"""

        if self.audit_logger:
            errors = self.audit_logger.errors
        else:
            errors = self._load_errors_from_files()

        # Filter by error type if specified
        if error_type:
            errors = [e for e in errors if e.error_type == error_type]

        # Convert to dict format
        error_dicts = [e.to_dict() if hasattr(e, "to_dict") else e for e in errors]

        # Apply limit if specified
        if limit:
            error_dicts = error_dicts[-limit:]

        return error_dicts

    def _load_errors_from_files(self) -> List[Dict[str, Any]]:
        """Load errors from JSONL files"""

        errors = []
        error_files = list(self.audit_path.glob("errors_*.jsonl"))

        for error_file in error_files:
            with open(error_file, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        errors.append(data)

        return errors

    def generate_analytics_report(self) -> Dict[str, Any]:
        """Generate comprehensive analytics report"""

        session_summary = self.get_session_summary()
        chat_interactions = self.get_chat_interactions()
        persona_activities = self.get_persona_activities()
        tool_usages = self.get_tool_usages()
        file_operations = self.get_file_operations()
        performance_metrics = self.get_performance_metrics()
        errors = self.get_errors()

        # Calculate analytics
        analytics = {
            "session_overview": session_summary,
            "interaction_analytics": self._analyze_chat_interactions(chat_interactions),
            "persona_analytics": self._analyze_persona_activities(persona_activities),
            "tool_analytics": self._analyze_tool_usages(tool_usages),
            "file_analytics": self._analyze_file_operations(file_operations),
            "performance_analytics": self._analyze_performance_metrics(performance_metrics),
            "error_analytics": self._analyze_errors(errors),
            "report_generated": datetime.now().isoformat(),
        }

        return analytics

    def _analyze_chat_interactions(self, interactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze chat interactions for patterns and metrics"""

        if not interactions:
            return {"total": 0}

        total_prompt_chars = sum(i.get("prompt_length", 0) for i in interactions)
        total_response_chars = sum(i.get("response_length", 0) for i in interactions)
        total_tokens = sum(i.get("tokens_used", 0) for i in interactions)
        total_duration = sum(i.get("duration_seconds", 0) for i in interactions)

        interaction_types = {}
        for i in interactions:
            itype = i.get("interaction_type", "unknown")
            interaction_types[itype] = interaction_types.get(itype, 0) + 1

        return {
            "total": len(interactions),
            "total_prompt_characters": total_prompt_chars,
            "total_response_characters": total_response_chars,
            "total_tokens": total_tokens,
            "total_duration_seconds": total_duration,
            "average_prompt_length": total_prompt_chars / len(interactions),
            "average_response_length": total_response_chars / len(interactions),
            "average_response_time": total_duration / len(interactions),
            "interaction_types": interaction_types,
        }

    def _analyze_persona_activities(self, activities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze persona activities for patterns and metrics"""

        if not activities:
            return {"total": 0}

        personas = {}
        activity_types = {}

        for activity in activities:
            persona = activity.get("persona", "unknown")
            activity_type = activity.get("activity", "unknown")

            personas[persona] = personas.get(persona, 0) + 1
            activity_types[activity_type] = activity_types.get(activity_type, 0) + 1

        return {
            "total": len(activities),
            "unique_personas": len(personas),
            "personas": personas,
            "activity_types": activity_types,
            "most_active_persona": (
                max(personas.items(), key=lambda x: x[1])[0] if personas else None
            ),
        }

    def _analyze_tool_usages(self, usages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze tool usages for patterns and metrics"""

        if not usages:
            return {"total": 0}

        tools = {}
        operations = {}
        successes = 0
        failures = 0

        for usage in usages:
            tool = usage.get("tool_name", "unknown")
            operation = usage.get("operation", "unknown")
            success = usage.get("success", False)

            tools[tool] = tools.get(tool, 0) + 1
            operations[operation] = operations.get(operation, 0) + 1

            if success:
                successes += 1
            else:
                failures += 1

        return {
            "total": len(usages),
            "unique_tools": len(tools),
            "tools": tools,
            "operations": operations,
            "success_rate": successes / len(usages),
            "successes": successes,
            "failures": failures,
            "most_used_tool": max(tools.items(), key=lambda x: x[1])[0] if tools else None,
        }

    def _analyze_file_operations(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze file operations for patterns and metrics"""

        if not operations:
            return {"total": 0}

        operation_types = {}
        successes = 0
        failures = 0
        total_size = 0

        for operation in operations:
            op_type = operation.get("operation", "unknown")
            success = operation.get("success", False)
            file_size = operation.get("file_size", 0)

            operation_types[op_type] = operation_types.get(op_type, 0) + 1

            if success:
                successes += 1
            else:
                failures += 1

            if file_size:
                total_size += file_size

        return {
            "total": len(operations),
            "operation_types": operation_types,
            "success_rate": successes / len(operations),
            "successes": successes,
            "failures": failures,
            "total_file_size_bytes": total_size,
        }

    def _analyze_performance_metrics(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance metrics for patterns and insights"""

        if not metrics:
            return {"total": 0}

        metric_names = {}
        total_value = 0

        for metric in metrics:
            name = metric.get("metric_name", "unknown")
            value = metric.get("value", 0)

            metric_names[name] = metric_names.get(name, [])
            metric_names[name].append(value)
            total_value += value

        # Calculate statistics for each metric
        metric_stats = {}
        for name, values in metric_names.items():
            metric_stats[name] = {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "average": sum(values) / len(values),
                "total": sum(values),
            }

        return {
            "total": len(metrics),
            "unique_metrics": len(metric_names),
            "metric_statistics": metric_stats,
            "total_value": total_value,
        }

    def _analyze_errors(self, errors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze errors for patterns and types"""

        if not errors:
            return {"total": 0}

        error_types = {}

        for error in errors:
            error_type = error.get("error_type", "unknown")
            error_types[error_type] = error_types.get(error_type, 0) + 1

        return {
            "total": len(errors),
            "unique_error_types": len(error_types),
            "error_types": error_types,
            "most_common_error": (
                max(error_types.items(), key=lambda x: x[1])[0] if error_types else None
            ),
        }
