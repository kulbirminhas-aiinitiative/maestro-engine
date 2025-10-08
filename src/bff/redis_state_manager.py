#!/usr/bin/env python3
"""
Redis State Manager for Unified BFF
Manages session state, conversation history, and generated artifacts
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import redis
from redis import asyncio as aioredis

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import configuration
from config import get_settings


class RedisStateManager:
    """
    Centralized state management using Redis
    Ensures consistency across multiple BFF instances
    """

    def __init__(self, redis_url: Optional[str] = None):
        settings = get_settings()
        self.redis_url = redis_url or settings.redis_url
        self.redis_client: Optional[aioredis.Redis] = None
        self.redis_sync: Optional[redis.Redis] = None
        self.pubsub = None

    async def connect(self):
        """Initialize Redis connection"""
        self.redis_client = await aioredis.from_url(
            self.redis_url, encoding="utf-8", decode_responses=True
        )
        # Also keep sync client for blocking operations
        self.redis_sync = redis.from_url(self.redis_url, decode_responses=True)
        print(f"✅ Redis State Manager connected to {self.redis_url}")

    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
        if self.redis_sync:
            self.redis_sync.close()

    # Session State Management

    async def create_session(
        self, session_id: str, user_id: Optional[str] = None, ttl: int = 3600
    ) -> Dict[str, Any]:
        """
        Create new session with initial state
        TTL default: 1 hour
        """
        initial_state = {
            "session_id": session_id,
            "user_id": user_id or "anonymous",
            "workflow_state": "idle",
            "current_persona": None,
            "conversation": [],
            "current_preview": None,
            "generated_files": [],
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "total_messages": 0,
                "generation_count": 0,
            },
        }

        await self.set_session_state(session_id, initial_state, ttl=ttl)
        return initial_state

    async def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve current session state"""
        state_key = f"session:{session_id}:state"
        state_json = await self.redis_client.get(state_key)

        if state_json:
            return json.loads(state_json)
        return None

    async def set_session_state(self, session_id: str, state: Dict[str, Any], ttl: int = 3600):
        """
        Update session state atomically
        Also publishes update notification for other BFF instances
        """
        state_key = f"session:{session_id}:state"
        state["metadata"]["updated_at"] = datetime.now().isoformat()

        # Atomic update with TTL
        pipeline = self.redis_client.pipeline()
        pipeline.set(state_key, json.dumps(state))
        pipeline.expire(state_key, ttl)
        await pipeline.execute()

        # Notify other BFF instances
        await self.redis_client.publish(
            "session:updates",
            json.dumps(
                {
                    "session_id": session_id,
                    "type": "state_change",
                    "timestamp": datetime.now().isoformat(),
                }
            ),
        )

    async def update_workflow_state(self, session_id: str, new_state: str):
        """
        Update workflow state: idle, generating, rendering, complete, error
        """
        state = await self.get_session_state(session_id)
        if state:
            state["workflow_state"] = new_state
            await self.set_session_state(session_id, state)

    # Conversation Management

    async def add_message(self, session_id: str, role: str, content: str) -> Dict[str, Any]:
        """Add message to conversation history"""
        message = {"role": role, "content": content, "timestamp": datetime.now().isoformat()}

        # Add to session state
        state = await self.get_session_state(session_id)
        if state:
            state["conversation"].append(message)
            state["metadata"]["total_messages"] = len(state["conversation"])
            await self.set_session_state(session_id, state)

        return message

    async def get_conversation(self, session_id: str) -> List[Dict[str, Any]]:
        """Get full conversation history"""
        state = await self.get_session_state(session_id)
        return state["conversation"] if state else []

    async def get_last_message(
        self, session_id: str, role: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get last message, optionally filtered by role"""
        conversation = await self.get_conversation(session_id)

        if not conversation:
            return None

        if role:
            for msg in reversed(conversation):
                if msg["role"] == role:
                    return msg
            return None
        else:
            return conversation[-1]

    # Preview Management

    async def update_preview(self, session_id: str, preview_data: Dict[str, Any]):
        """Update current preview content"""
        state = await self.get_session_state(session_id)
        if state:
            state["current_preview"] = {**preview_data, "last_updated": datetime.now().isoformat()}
            await self.set_session_state(session_id, state)

    async def get_preview(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current preview"""
        state = await self.get_session_state(session_id)
        return state["current_preview"] if state else None

    # Artifact Management

    async def add_generated_file(self, session_id: str, file_info: Dict[str, Any]):
        """Add generated file to artifacts"""
        state = await self.get_session_state(session_id)
        if state:
            state["generated_files"].append({**file_info, "created_at": datetime.now().isoformat()})
            state["metadata"]["generation_count"] += 1
            await self.set_session_state(session_id, state)

    async def get_generated_files(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all generated files"""
        state = await self.get_session_state(session_id)
        return state["generated_files"] if state else []

    async def store_artifact_content(
        self, session_id: str, artifact_id: str, content: str, ttl: int = 3600
    ):
        """Store artifact content separately (for large files)"""
        artifact_key = f"session:{session_id}:artifact:{artifact_id}"
        await self.redis_client.set(artifact_key, content)
        await self.redis_client.expire(artifact_key, ttl)

    async def get_artifact_content(self, session_id: str, artifact_id: str) -> Optional[str]:
        """Retrieve artifact content"""
        artifact_key = f"session:{session_id}:artifact:{artifact_id}"
        return await self.redis_client.get(artifact_key)

    # Session Lifecycle

    async def session_exists(self, session_id: str) -> bool:
        """Check if session exists"""
        state_key = f"session:{session_id}:state"
        return await self.redis_client.exists(state_key) > 0

    async def extend_session(self, session_id: str, ttl: int = 3600):
        """Extend session TTL"""
        state_key = f"session:{session_id}:state"
        await self.redis_client.expire(state_key, ttl)

    async def export_session_context(self, session_id: str) -> Dict[str, Any]:
        """
        Export full session context for Guardian workflow
        Includes conversation, preview, and generated files
        This allows maestro-engine to build on existing Accelerator work
        """
        state = await self.get_session_state(session_id)

        if not state:
            return {
                "session_id": session_id,
                "conversation": [],
                "preview": None,
                "generated_files": [],
                "metadata": {},
            }

        return {
            "session_id": session_id,
            "conversation": state.get("conversation", []),
            "preview": state.get("current_preview"),
            "generated_files": state.get("generated_files", []),
            "workflow_state": state.get("workflow_state", "idle"),
            "metadata": {
                **state.get("metadata", {}),
                "exported_at": datetime.now().isoformat(),
                "total_messages": len(state.get("conversation", [])),
                "has_preview": state.get("current_preview") is not None,
                "file_count": len(state.get("generated_files", [])),
            },
        }

    async def delete_session(self, session_id: str):
        """Delete session and all related data"""
        # Get all keys for this session
        pattern = f"session:{session_id}:*"
        keys = []
        async for key in self.redis_client.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            await self.redis_client.delete(*keys)

    # Pub/Sub for Multi-Instance Coordination

    async def subscribe_to_updates(self, callback):
        """
        Subscribe to session updates from other BFF instances
        Callback receives: {"session_id": str, "type": str, "timestamp": str}
        """
        self.pubsub = self.redis_client.pubsub()
        await self.pubsub.subscribe("session:updates")

        async for message in self.pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await callback(data)
                except Exception as e:
                    print(f"Error processing pubsub message: {e}")

    async def unsubscribe_from_updates(self):
        """Unsubscribe from session updates"""
        if self.pubsub:
            await self.pubsub.unsubscribe("session:updates")
            await self.pubsub.close()

    # Statistics and Monitoring

    async def get_active_sessions_count(self) -> int:
        """Count active sessions"""
        count = 0
        async for _ in self.redis_client.scan_iter(match="session:*:state"):
            count += 1
        return count

    async def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session statistics"""
        state = await self.get_session_state(session_id)
        if not state:
            return None

        return {
            "session_id": session_id,
            "workflow_state": state["workflow_state"],
            "message_count": state["metadata"]["total_messages"],
            "generation_count": state["metadata"]["generation_count"],
            "file_count": len(state["generated_files"]),
            "has_preview": state["current_preview"] is not None,
            "created_at": state["metadata"]["created_at"],
            "updated_at": state["metadata"]["updated_at"],
        }

    # Background Task Management

    async def get_active_build_task(self, session_id: str) -> Optional[str]:
        """Get active build task ID"""
        task_key = f"session:{session_id}:build_task"
        return await self.redis_client.get(task_key)

    async def set_active_build_task(self, session_id: str, task_id: str, ttl: int = 3600):
        """Set active build task"""
        task_key = f"session:{session_id}:build_task"
        await self.redis_client.set(task_key, task_id)
        await self.redis_client.expire(task_key, ttl)

    async def clear_active_build_task(self, session_id: str):
        """Clear active build task"""
        task_key = f"session:{session_id}:build_task"
        await self.redis_client.delete(task_key)

    async def add_build_requirement(self, session_id: str, requirement: str):
        """Add new requirement to queue"""
        req_key = f"session:{session_id}:requirements"
        await self.redis_client.rpush(
            req_key, json.dumps({"text": requirement, "timestamp": datetime.now().isoformat()})
        )
        await self.redis_client.expire(req_key, 3600)

    async def pop_build_requirements(self, session_id: str) -> List[str]:
        """Pop all pending requirements"""
        req_key = f"session:{session_id}:requirements"
        reqs = []
        while True:
            req_json = await self.redis_client.lpop(req_key)
            if not req_json:
                break
            req_data = json.loads(req_json)
            reqs.append(req_data["text"])
        return reqs

    async def should_stop_build(self, session_id: str, task_id: str) -> bool:
        """Check if build should stop"""
        current_task = await self.get_active_build_task(session_id)
        return current_task != task_id  # Stop if task was replaced


# Singleton instance
_redis_state_manager: Optional[RedisStateManager] = None


def get_redis_state_manager() -> RedisStateManager:
    """Get or create singleton Redis State Manager"""
    global _redis_state_manager
    if _redis_state_manager is None:
        _redis_state_manager = RedisStateManager()
    return _redis_state_manager


# Example Usage
if __name__ == "__main__":
    import asyncio

    async def test_redis_state():
        """Test Redis State Manager"""
        manager = RedisStateManager()
        await manager.connect()

        # Create session
        session_id = f"test_session_{int(time.time())}"
        state = await manager.create_session(session_id, user_id="test_user")
        print(f"✅ Created session: {session_id}")
        print(f"   State: {json.dumps(state, indent=2)}")

        # Add messages
        await manager.add_message(session_id, "user", "Build a todo app")
        await manager.add_message(session_id, "assistant", "Creating todo app...")
        print(f"✅ Added 2 messages")

        # Update preview
        await manager.update_preview(
            session_id, {"type": "web", "html_content": "<!DOCTYPE html><html>...</html>"}
        )
        print(f"✅ Updated preview")

        # Add artifact
        await manager.add_generated_file(
            session_id, {"path": "index.html", "size": 1234, "url": "/artifacts/index.html"}
        )
        print(f"✅ Added generated file")

        # Get final state
        final_state = await manager.get_session_state(session_id)
        print(f"\n✅ Final State:")
        print(f"   Messages: {final_state['metadata']['total_messages']}")
        print(f"   Files: {len(final_state['generated_files'])}")
        print(f"   Preview: {final_state['current_preview'] is not None}")

        # Get stats
        stats = await manager.get_session_stats(session_id)
        print(f"\n✅ Session Stats:")
        print(json.dumps(stats, indent=2))

        # Cleanup
        await manager.delete_session(session_id)
        print(f"\n✅ Cleaned up session")

        await manager.disconnect()

    asyncio.run(test_redis_state())
