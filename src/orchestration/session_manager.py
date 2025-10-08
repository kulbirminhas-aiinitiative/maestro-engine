"""
Session Manager for Autonomous SDLC Engine
Enables incremental, resumable workflow execution across multiple sessions
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SDLCSession:
    """Represents a persistent SDLC session"""

    def __init__(
        self,
        session_id: str,
        requirement: str,
        output_dir: Path,
        mcp_cache_dir: Optional[Path] = None,
    ):
        self.session_id = session_id
        self.requirement = requirement
        self.output_dir = Path(output_dir)
        self.mcp_cache_dir = mcp_cache_dir or Path("/tmp/mcp_shared_context")

        # Session state
        self.created_at = datetime.now()
        self.last_updated = datetime.now()
        self.completed_personas: List[str] = []
        self.files_registry: Dict[str, Dict[str, Any]] = {}
        self.persona_outputs: Dict[str, Dict[str, Any]] = {}

    def add_persona_execution(
        self,
        persona_id: str,
        files_created: List[str],
        deliverables: Dict[str, Any],
        duration: float,
        success: bool,
    ):
        """Record a persona's execution"""
        self.completed_personas.append(persona_id)
        self.persona_outputs[persona_id] = {
            "files_created": files_created,
            "deliverables": deliverables,
            "duration": duration,
            "success": success,
            "executed_at": datetime.now().isoformat(),
        }

        # Register files
        for file_path in files_created:
            self.files_registry[file_path] = {
                "created_by": persona_id,
                "created_at": datetime.now().isoformat(),
            }

        self.last_updated = datetime.now()

    def get_completed_personas(self) -> List[str]:
        """Get list of personas that have already executed"""
        return self.completed_personas.copy()

    def get_pending_personas(self, requested_personas: List[str]) -> List[str]:
        """Get list of personas that still need to execute"""
        return [p for p in requested_personas if p not in self.completed_personas]

    def get_all_files(self) -> List[str]:
        """Get all files created in this session"""
        return list(self.files_registry.keys())

    def get_files_by_persona(self, persona_id: str) -> List[str]:
        """Get files created by a specific persona"""
        return [
            path for path, info in self.files_registry.items() if info["created_by"] == persona_id
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dictionary"""
        return {
            "session_id": self.session_id,
            "requirement": self.requirement,
            "output_dir": str(self.output_dir),
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "completed_personas": self.completed_personas,
            "files_registry": self.files_registry,
            "persona_outputs": self.persona_outputs,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SDLCSession":
        """Deserialize session from dictionary"""
        session = cls(
            session_id=data["session_id"],
            requirement=data["requirement"],
            output_dir=Path(data["output_dir"]),
        )

        session.created_at = datetime.fromisoformat(data["created_at"])
        session.last_updated = datetime.fromisoformat(data["last_updated"])
        session.completed_personas = data["completed_personas"]
        session.files_registry = data["files_registry"]
        session.persona_outputs = data["persona_outputs"]

        return session


class SessionManager:
    """Manages persistent sessions for incremental SDLC execution"""

    def __init__(self, session_dir: Optional[Path] = None, mcp_cache_dir: Optional[Path] = None):
        self.session_dir = session_dir or Path("./sdlc_sessions")
        self.mcp_cache_dir = mcp_cache_dir or Path("/tmp/mcp_shared_context")
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.mcp_cache_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self, session: SDLCSession) -> bool:
        """Save session to disk and MCP cache"""
        try:
            # Save to session directory
            session_file = self.session_dir / f"{session.session_id}.json"
            with open(session_file, "w") as f:
                json.dump(session.to_dict(), f, indent=2)

            # Also save to MCP cache for cross-process access
            mcp_file = self.mcp_cache_dir / f"{session.session_id}_session.json"
            with open(mcp_file, "w") as f:
                json.dump(session.to_dict(), f, indent=2)

            logger.info(f"💾 Session saved: {session.session_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to save session: {e}")
            return False

    def load_session(self, session_id: str) -> Optional[SDLCSession]:
        """Load session from disk or MCP cache"""
        try:
            # Try session directory first
            session_file = self.session_dir / f"{session_id}.json"
            if session_file.exists():
                with open(session_file, "r") as f:
                    data = json.load(f)
                session = SDLCSession.from_dict(data)
                logger.info(f"📂 Session loaded from disk: {session_id}")
                return session

            # Try MCP cache
            mcp_file = self.mcp_cache_dir / f"{session_id}_session.json"
            if mcp_file.exists():
                with open(mcp_file, "r") as f:
                    data = json.load(f)
                session = SDLCSession.from_dict(data)
                logger.info(f"📂 Session loaded from MCP cache: {session_id}")
                return session

            logger.warning(f"⚠️ Session not found: {session_id}")
            return None

        except Exception as e:
            logger.error(f"❌ Failed to load session: {e}")
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all available sessions"""
        sessions = []

        for session_file in self.session_dir.glob("*.json"):
            try:
                with open(session_file, "r") as f:
                    data = json.load(f)
                    sessions.append(
                        {
                            "session_id": data["session_id"],
                            "requirement": data["requirement"][:100],
                            "created_at": data["created_at"],
                            "last_updated": data["last_updated"],
                            "completed_personas": len(data["completed_personas"]),
                            "files_count": len(data["files_registry"]),
                        }
                    )
            except Exception as e:
                logger.warning(f"⚠️ Failed to read session {session_file}: {e}")

        return sorted(sessions, key=lambda x: x["last_updated"], reverse=True)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        try:
            session_file = self.session_dir / f"{session_id}.json"
            mcp_file = self.mcp_cache_dir / f"{session_id}_session.json"

            deleted = False
            if session_file.exists():
                session_file.unlink()
                deleted = True

            if mcp_file.exists():
                mcp_file.unlink()
                deleted = True

            if deleted:
                logger.info(f"🗑️ Session deleted: {session_id}")
            else:
                logger.warning(f"⚠️ Session not found: {session_id}")

            return deleted

        except Exception as e:
            logger.error(f"❌ Failed to delete session: {e}")
            return False

    def create_session(
        self, requirement: str, output_dir: Path, session_id: Optional[str] = None
    ) -> SDLCSession:
        """Create a new session"""
        if not session_id:
            # Generate session ID from requirement hash + timestamp
            import hashlib

            req_hash = hashlib.md5(requirement.encode()).hexdigest()[:8]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"sdlc_{req_hash}_{timestamp}"

        session = SDLCSession(
            session_id=session_id,
            requirement=requirement,
            output_dir=output_dir,
            mcp_cache_dir=self.mcp_cache_dir,
        )

        self.save_session(session)
        return session

    def get_session_context(self, session: SDLCSession) -> str:
        """Build context string from session history"""
        context_parts = [
            f"Session ID: {session.session_id}",
            f"Requirement: {session.requirement}",
            f"\nCompleted Personas: {', '.join(session.completed_personas)}",
            f"Total Files: {len(session.files_registry)}\n",
        ]

        # Add outputs from completed personas
        for persona_id in session.completed_personas:
            output = session.persona_outputs.get(persona_id)
            if output:
                files = output.get("files_created", [])
                context_parts.append(f"\n{persona_id} created {len(files)} files:")
                for file_path in files[:5]:  # Limit to avoid huge context
                    context_parts.append(f"  - {file_path}")
                if len(files) > 5:
                    context_parts.append(f"  ... and {len(files) - 5} more")

        return "\n".join(context_parts)
