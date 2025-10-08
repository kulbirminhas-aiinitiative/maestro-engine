#!/usr/bin/env python3
"""
Enhanced MCP Audit Observer - Integrated with Audit Logger Library
Monitors MCP cache and generates comprehensive audit using Audit Logger Library
Runs independently from core workflow for complete audit detail
"""

import asyncio
import json
import logging
import hashlib
import time
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from collections import defaultdict

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_cache_config import get_mcp_cache

# Import Audit Logger Library
try:
    from libraries.audit_logger import AuditLogger, AuditExporter, AuditViewer
    from libraries.audit_logger.config import PresetConfigs
    AUDIT_LIBRARY_AVAILABLE = True
except ImportError:
    AUDIT_LIBRARY_AVAILABLE = False
    logging.warning("⚠️ Audit Logger Library not available - using basic logging")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedMCPAuditObserver:
    """
    Enhanced MCP Audit Observer with Audit Logger Library integration
    """

    def __init__(self, audit_base_path: str = "audit_exports"):
        self.audit_base_path = Path(audit_base_path)
        self.audit_base_path.mkdir(parents=True, exist_ok=True)

        self.mcp_cache = get_mcp_cache()

        self.observed_sessions = {}
        self.session_audit_loggers = {}  # AuditLogger per session
        self.session_audit_data = defaultdict(lambda: {
            "events": [],
            "chat_interactions": [],
            "file_operations": [],
            "performance_metrics": [],
            "errors": [],
            "metadata": {}
        })

        logger.info("🔍 Enhanced MCP Audit Observer Initialized")
        logger.info(f"📁 Audit Path: {self.audit_base_path}")
        logger.info(f"📋 Audit Library: {'ENABLED' if AUDIT_LIBRARY_AVAILABLE else 'DISABLED'}")

    async def observe_sessions(self, poll_interval: int = 5, max_runtime: int = 300):
        """Observe all active sessions"""

        logger.info("👀 Starting MCP cache observation...")
        logger.info(f"🔄 Poll interval: {poll_interval}s")
        logger.info(f"⏱️  Max runtime: {max_runtime}s")

        start_time = time.time()

        try:
            while (time.time() - start_time) < max_runtime:
                active_sessions = await self._discover_active_sessions()

                for session_id in active_sessions:
                    await self._process_session_events(session_id)

                await asyncio.sleep(poll_interval)

        except KeyboardInterrupt:
            logger.info("\n🛑 Observation stopped by user")

        finally:
            await self._finalize_all_audits()

    async def observe_single_session(self, session_id: str, poll_interval: int = 2, max_polls: int = 60):
        """Observe a specific session until completion"""

        logger.info(f"🎯 Observing session: {session_id}")

        # Initialize session in observed_sessions
        self.observed_sessions[session_id] = {
            "discovered_at": datetime.now().isoformat(),
            "status": "active"
        }

        for poll_count in range(max_polls):
            await self._process_session_events(session_id)
            await asyncio.sleep(poll_interval)

            # Check if session is complete
            events = await self._get_session_events(session_id)
            if any(e.get("type") == "workflow_complete" for e in events):
                logger.info(f"✅ Session {session_id} completed")
                break

        await self._finalize_session_audit(session_id)

    async def _discover_active_sessions(self) -> List[str]:
        """Discover active sessions from MCP cache"""

        try:
            # Get all events from cache
            all_events = []
            cache_entries = self.mcp_cache.session_cache.values()

            for entry in cache_entries:
                if entry.get("metadata", {}).get("observable"):
                    all_events.append(entry)

            # Extract unique session IDs
            session_ids = set()
            for entry in all_events:
                session_id = entry.get("session_id")
                if session_id and session_id not in self.observed_sessions:
                    session_ids.add(session_id)
                    self.observed_sessions[session_id] = {
                        "discovered_at": datetime.now().isoformat(),
                        "status": "active"
                    }

            return list(session_ids)

        except Exception as e:
            logger.error(f"Session discovery error: {e}")
            return []

    async def _get_session_events(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all events for a session"""

        try:
            return self.mcp_cache.get_all_workflow_events(session_id)
        except Exception as e:
            logger.error(f"Failed to get events for {session_id}: {e}")
            return []

    async def _process_session_events(self, session_id: str):
        """Process all events for a session"""

        events = await self._get_session_events(session_id)

        # Find new events
        existing_events = self.session_audit_data[session_id]["events"]
        existing_ids = {e.get("timestamp") + e.get("type", "") for e in existing_events}
        new_events = [e for e in events if (e.get("timestamp", "") + e.get("type", "")) not in existing_ids]

        for event in new_events:
            await self._process_event(session_id, event)

        if new_events:
            logger.info(f"📡 Processed {len(new_events)} event(s) for {session_id}")

    def _get_or_create_audit_logger(self, session_id: str) -> Optional[Any]:
        """Get or create AuditLogger for session"""
        if not AUDIT_LIBRARY_AVAILABLE:
            return None

        if session_id in self.session_audit_loggers:
            return self.session_audit_loggers[session_id]

        try:
            session_path = self.audit_base_path / session_id
            session_path.mkdir(parents=True, exist_ok=True)

            config = PresetConfigs.development(
                session_id=session_id,
                project_path=session_path
            )
            config.full_content_logging = True
            config.custom_metadata = {
                "component": "enhanced_mcp_audit_observer",
                "observer_type": "external_process",
                "audit_library_version": "1.0"
            }

            audit_logger = AuditLogger(config)
            self.session_audit_loggers[session_id] = audit_logger
            logger.info(f"📋 Created Audit Logger for session: {session_id}")
            return audit_logger

        except Exception as e:
            logger.error(f"Failed to create Audit Logger for {session_id}: {e}")
            return None

    async def _process_event(self, session_id: str, event: Dict[str, Any]):
        """Process individual event with Audit Logger Library"""

        event_type = event.get("type", "unknown")
        self.session_audit_data[session_id]["events"].append(event)

        # Use Audit Logger Library
        audit_logger = self._get_or_create_audit_logger(session_id)

        if audit_logger:
            self._log_event_to_audit_library(audit_logger, event)

        # Also categorize for basic audit data
        try:
            if event_type in ["workflow_start", "workflow_complete", "team_initialization"]:
                self.session_audit_data[session_id]["chat_interactions"].append(event)

            elif event_type in ["file_created", "file_operation"]:
                self.session_audit_data[session_id]["file_operations"].append(event)

            elif "error" in event_type:
                self.session_audit_data[session_id]["errors"].append(event)

            elif "execution_time" in event or "performance" in event_type:
                self.session_audit_data[session_id]["performance_metrics"].append(event)

        except Exception as e:
            logger.error(f"Event processing error: {e}")
            if audit_logger:
                audit_logger.log_error(
                    error_type="event_processing_error",
                    error_message=str(e),
                    context={"event_type": event_type}
                )

    def _log_event_to_audit_library(self, audit_logger: Any, event: Dict[str, Any]):
        """Map MCP event to Audit Logger methods"""
        event_type = event.get("type", "unknown")

        try:
            if event_type == "team_initialization":
                audit_logger.log_persona_activity(
                    persona="orchestrator",
                    activity="initialization",
                    details={
                        "team_members": event.get("team_members", []),
                        "team_size": event.get("team_size", 0),
                        "features": event.get("features", {})
                    }
                )

            elif event_type in ["workflow_start", "workflow_complete"]:
                audit_logger.log_persona_activity(
                    persona="orchestrator",
                    activity=event_type,
                    details={
                        "requirement": event.get("requirement", ""),
                        "success": event.get("success"),
                        "execution_time": event.get("execution_time")
                    }
                )

            elif event_type in ["tool_execution_start", "tool_execution_error"]:
                audit_logger.log_tool_usage(
                    tool_name=event.get("tool", "unknown"),
                    operation=event_type,
                    parameters=event,
                    success="start" in event_type,
                    error=event.get("error") if "error" in event_type else None
                )

            elif event_type == "file_created":
                audit_logger.log_file_operation(
                    operation="create",
                    file_path=event.get("file_path", ""),
                    success=True
                )

            elif event_type in ["execution_error", "tool_execution_exception"]:
                audit_logger.log_error(
                    error_type=event.get("error_type", "unknown"),
                    error_message=event.get("error", ""),
                    context=event
                )

            elif "performance" in event_type or "execution_time" in event:
                audit_logger.log_performance_metric(
                    metric_name=event_type,
                    value=event.get("execution_time", 0),
                    context=event
                )

        except Exception as e:
            logger.error(f"Audit library logging error: {e}")

    async def _finalize_session_audit(self, session_id: str) -> Dict[str, Any]:
        """Finalize audit for session"""

        logger.info(f"🏁 Finalizing audit for session: {session_id}")

        audit_data = self.session_audit_data[session_id]
        audit_data["session_id"] = session_id
        audit_data["finalized_at"] = datetime.now(timezone.utc).isoformat()

        # Save basic audit data
        session_path = self.audit_base_path / session_id
        session_path.mkdir(parents=True, exist_ok=True)

        audit_file = session_path / "mcp_audit.json"
        with open(audit_file, 'w') as f:
            json.dump(audit_data, f, indent=2)

        logger.info(f"📄 Saved audit report: {audit_file}")

        # Finalize Audit Logger and export
        if session_id in self.session_audit_loggers:
            try:
                audit_logger = self.session_audit_loggers[session_id]
                audit_logger.finalize_session()

                # Export to multiple formats
                if AUDIT_LIBRARY_AVAILABLE:
                    try:
                        exporter = AuditExporter(audit_logger)

                        export_base = session_path / "exports"
                        export_base.mkdir(parents=True, exist_ok=True)

                        # Export complete audit to directory (includes all CSVs and JSON)
                        exported_files = exporter.export_complete_audit_to_directory(
                            export_base,
                            include_full_content=True
                        )

                        logger.info(f"📊 Exported complete audit:")
                        for file_type, file_path in exported_files.items():
                            logger.info(f"   - {file_type}: {file_path}")

                    except Exception as e:
                        logger.error(f"Export error: {e}")

                del self.session_audit_loggers[session_id]

            except Exception as e:
                logger.error(f"Audit logger finalization error: {e}")

        self.observed_sessions[session_id]["status"] = "finalized"

        return audit_data

    async def _finalize_all_audits(self):
        """Finalize all observed session audits"""

        logger.info("🏁 Finalizing all session audits...")

        for session_id in list(self.observed_sessions.keys()):
            if self.observed_sessions[session_id]["status"] != "finalized":
                await self._finalize_session_audit(session_id)

        logger.info(f"✅ Finalized {len(self.observed_sessions)} session audit(s)")


async def main():
    """Main entry point for observer"""
    import sys

    observer = EnhancedMCPAuditObserver()

    if len(sys.argv) > 1:
        session_id = sys.argv[1]
        logger.info(f"🎯 Observing specific session: {session_id}")
        await observer.observe_single_session(session_id)
    else:
        logger.info("👀 Observing all active sessions")
        await observer.observe_sessions(poll_interval=5, max_runtime=300)


if __name__ == "__main__":
    asyncio.run(main())