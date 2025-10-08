#!/usr/bin/env python3
"""
MCP-Driven Enhanced Lean Ultimate Mega Team
This version reads the initial requirement directly from the MCP cache.
Lean core workflow with MCP event emission for external audit observation.
"""

import asyncio
import hashlib
import logging
import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import contextlib
import sys

# Dependency Imports
try:
    from unified_claude_tools import generate_with_unified_tools
    CLAUDE_TOOLS_AVAILABLE = True
except ImportError:
    CLAUDE_TOOLS_AVAILABLE = False
    logging.warning("⚠️ unified_claude_tools not available - some features disabled")

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logging.warning("⚠️ ChromaDB not available - RAG features disabled")

try:
    from mcp_cache_config import get_mcp_cache
    MCP_CACHE_AVAILABLE = True
except ImportError:
    MCP_CACHE_AVAILABLE = False
    logging.warning("⚠️ MCP cache not available - event emission disabled")

logger = logging.getLogger(__name__)

# --- Data Classes ---

@dataclass
class EnhancedTeamConfig:
    """Configuration for the lean team"""
    selected_personas: Optional[List[str]] = None
    enable_rag: bool = True
    enable_mcp: bool = True
    enable_event_emission: bool = True
    session_id: str = ""
    project_path: str = ""
    max_execution_time: int = 3600
    cache_enabled: bool = True

    def __post_init__(self):
        if self.selected_personas is None:
            self.selected_personas = [
                "requirement_analyst", "solution_architect", "frontend_developer",
                "backend_developer", "devops_engineer", "qa_engineer"
            ]
        if not self.session_id:
            self.session_id = f"mcp_enhanced_lean_{int(time.time())}"

# --- Core Classes ---

class EnhancedMCPContext:
    """Handles reading and writing to the MCP shared context directory"""
    def __init__(self, session_id: str, cache_dir: Optional[Path] = None):
        self.session_id = session_id
        self.mcp_dir = cache_dir or Path("/tmp/mcp_shared_context")
        self.mcp_dir.mkdir(parents=True, exist_ok=True)

    def get_context(self) -> Optional[Dict[str, Any]]:
        """Reads the full MCP context file for the session."""
        context_file = self.mcp_dir / f"{self.session_id}.json"
        if not context_file.exists():
            logging.warning(f"MCP context file not found for session {self.session_id} at {context_file}")
            return None
        try:
            with open(context_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Failed to read or parse MCP context file {context_file}: {e}")
            return None

    def get_requirement_from_context(self) -> Optional[str]:
        """Extracts the latest user message from the MCP context."""
        context = self.get_context()
        if context and "latest_user_message" in context:
            return context["latest_user_message"]
        logging.warning(f"Could not find 'latest_user_message' in MCP context for session {self.session_id}")
        return None


class EnhancedLeanTeam:
    """Lean team that executes workflows based on MCP-driven requirements."""

    def __init__(self, config: EnhancedTeamConfig = None):
        self.config = config or EnhancedTeamConfig()
        self.start_time = time.time()
        self.session_id = self.config.session_id
        self.project_path = Path(self.config.project_path or
                               f"/home/ec2-user/projects/maestro-v2/mcp_enhanced_lean_output/{self.session_id}")
        self.project_path.mkdir(parents=True, exist_ok=True)

        self.team_members = self.config.selected_personas
        self.mcp_cache = get_mcp_cache() if MCP_CACHE_AVAILABLE and self.config.enable_event_emission else None
        self.mcp_context_reader = EnhancedMCPContext(self.session_id) if self.config.enable_mcp else None

        self._log_initialization()

    def _emit_event(self, event: Dict[str, Any]):
        """Emits an event to the MCP cache for external observation."""
        if not self.mcp_cache:
            return
        try:
            event["session_id"] = self.session_id
            event["timestamp"] = datetime.now().isoformat()
            self.mcp_cache.store_workflow_event(event, self.session_id)
        except Exception as e:
            logging.error(f"Event emission failed: {e}")

    def _log_initialization(self):
        logging.info("🚀 MCP-DRIVEN ENHANCED LEAN TEAM INITIALIZED")
        logging.info(f"📁 Path: {self.project_path}")
        logging.info(f"🔍 Session: {self.session_id}")
        self._emit_event({
            "type": "team_initialization",
            "team_members": self.team_members,
            "project_path": str(self.project_path),
        })

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._emit_event({
            "type": "cleanup_complete",
            "duration": time.time() - self.start_time
        })

    async def execute_workflow_from_mcp(self) -> Dict[str, Any]:
        """Fetches requirement from MCP and executes the workflow."""
        start_time = time.time()
        
        if not self.mcp_context_reader:
            return {"success": False, "error": "MCP context reader is not enabled."}

        requirement = self.mcp_context_reader.get_requirement_from_context()
        if not requirement:
            return {"success": False, "error": f"Could not retrieve requirement from MCP for session {self.session_id}."}

        self._emit_event({"type": "workflow_start", "requirement": requirement})

        result = {
            "success": False,
            "requirement": requirement,
            "session_id": self.session_id,
        }

        try:
            if CLAUDE_TOOLS_AVAILABLE:
                persona_config = {"selected_personas": self.team_members, "session_id": self.session_id}
                prompt = f"Team Members: {', '.join(self.team_members)}\n\nRequirement: {requirement}"
                
                self._emit_event({"type": "tool_execution_start", "tool": "unified_claude_tools"})
                
                tool_result = await generate_with_unified_tools(
                    requirement=prompt,
                    persona_config=persona_config,
                    project_path=str(self.project_path),
                    session_id=self.session_id,
                    enable_audit_logging=False
                )
                result.update(tool_result)
            else:
                result["error"] = "unified_claude_tools not available."

        except Exception as e:
            result["error"] = f"Workflow exception: {str(e)}"
            self._emit_event({"type": "execution_error", "error": str(e)})

        result["total_execution_time"] = time.time() - start_time
        self._emit_event({
            "type": "workflow_complete",
            "success": result["success"],
            "execution_time": result["total_execution_time"],
        })
        return result

# --- Main Execution ---

async def execute_mcp_workflow(session_id: str) -> Dict[str, Any]:
    """Main function to execute the MCP-driven workflow for a given session."""
    config = EnhancedTeamConfig(session_id=session_id)
    async with EnhancedLeanTeam(config) as team:
        return await team.execute_workflow_from_mcp()

async def main():
    """Main entry point for command-line execution."""
    if len(sys.argv) < 2:
        print("Usage: ./mcp_enhanced_lean_ultimate_mega_team.py <session_id>")
        sys.exit(1)
    
    session_id = sys.argv[1]
    print(f"📋 Starting MCP-driven workflow for session: {session_id}")

    result = await execute_mcp_workflow(session_id)

    print(f"\n--- Workflow Complete ---")
    print(f"✅ Success: {result.get('success')}")
    print(f"📁 Files Generated: {len(result.get('generated_files', []))}")
    print(f"⏱️  Total Time: {result.get('total_execution_time', 0):.2f}s")
    if result.get('error'):
        print(f"❌ Error: {result.get('error')}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    asyncio.run(main())
