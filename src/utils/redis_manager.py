"""
Redis Manager for Workflow State Management

Provides async Redis operations for:
- Workflow state persistence
- Active workflow tracking
- WebSocket connection management
- Checkpoint metadata storage
- Progress tracking
"""

import json
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class WorkflowStateManager:
    """
    Manages workflow state in Redis for persistence and real-time updates.

    Schema:
        workflow:{id} → Hash of workflow metadata
        workflow:{id}:phase:{phase} → Hash of phase results
        active_workflows → Set of active workflow IDs
        ws:connections:{workflow_id} → Set of WebSocket connection IDs
        workflow:{id}:checkpoints → List of checkpoint metadata
    """

    def __init__(self, redis_url: str = "redis://localhost:6380", db: int = 0):
        """
        Initialize Redis connection.

        Args:
            redis_url: Redis connection URL
            db: Redis database number
        """
        self.redis_url = redis_url
        self.db = db
        self.client: Optional[redis.Redis] = None
        logger.info(f"Redis Manager initialized: {redis_url} (DB {db})")

    async def connect(self):
        """Establish Redis connection"""
        if self.client is None:
            self.client = await redis.from_url(
                self.redis_url,
                db=self.db,
                decode_responses=True,
                encoding="utf-8"
            )
            logger.info("✅ Connected to Redis")

    async def disconnect(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            self.client = None
            logger.info("Disconnected from Redis")

    # ========================================================================
    # WORKFLOW OPERATIONS
    # ========================================================================

    async def create_workflow(
        self,
        workflow_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Create a new workflow in Redis.

        Args:
            workflow_id: Unique workflow identifier
            data: Workflow metadata (requirement, mode, project_name, etc.)

        Returns:
            bool: Success status
        """
        await self.connect()

        # Add timestamps
        data["started_at"] = data.get("started_at", datetime.now().isoformat())
        data["updated_at"] = datetime.now().isoformat()
        data["status"] = data.get("status", "starting")

        # Store workflow data
        await self.client.hset(
            f"workflow:{workflow_id}",
            mapping={k: str(v) for k, v in data.items()}
        )

        # Add to active workflows set
        await self.client.sadd("active_workflows", workflow_id)

        # Set TTL (7 days)
        await self.client.expire(f"workflow:{workflow_id}", 604800)

        logger.info(f"📝 Created workflow: {workflow_id} (mode: {data.get('mode')})")
        return True

    async def update_workflow(
        self,
        workflow_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update workflow metadata.

        Args:
            workflow_id: Workflow identifier
            updates: Fields to update

        Returns:
            bool: Success status
        """
        await self.connect()

        # Add update timestamp
        updates["updated_at"] = datetime.now().isoformat()

        # Update fields
        await self.client.hset(
            f"workflow:{workflow_id}",
            mapping={k: str(v) for k, v in updates.items()}
        )

        logger.debug(f"Updated workflow {workflow_id}: {list(updates.keys())}")
        return True

    async def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Get workflow metadata.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Dict with workflow data or None if not found
        """
        await self.connect()

        data = await self.client.hgetall(f"workflow:{workflow_id}")

        if not data:
            return None

        # Parse JSON fields
        if "checkpoint_phases" in data:
            try:
                data["checkpoint_phases"] = json.loads(data["checkpoint_phases"])
            except:
                pass

        return data

    async def complete_workflow(self, workflow_id: str) -> bool:
        """
        Mark workflow as completed.

        Args:
            workflow_id: Workflow identifier

        Returns:
            bool: Success status
        """
        await self.connect()

        # Update status
        await self.update_workflow(workflow_id, {
            "status": "completed",
            "completed_at": datetime.now().isoformat()
        })

        # Remove from active set
        await self.client.srem("active_workflows", workflow_id)

        # Extend TTL for completed workflows (24 hours)
        await self.client.expire(f"workflow:{workflow_id}", 86400)

        logger.info(f"✅ Completed workflow: {workflow_id}")
        return True

    async def fail_workflow(self, workflow_id: str, error: str) -> bool:
        """
        Mark workflow as failed.

        Args:
            workflow_id: Workflow identifier
            error: Error message

        Returns:
            bool: Success status
        """
        await self.connect()

        # Update status
        await self.update_workflow(workflow_id, {
            "status": "error",
            "error": error,
            "failed_at": datetime.now().isoformat()
        })

        # Remove from active set
        await self.client.srem("active_workflows", workflow_id)

        logger.error(f"❌ Failed workflow: {workflow_id} - {error}")
        return True

    async def get_active_workflows(self) -> List[str]:
        """
        Get list of currently active workflows.

        Returns:
            List of workflow IDs
        """
        await self.connect()

        workflows = await self.client.smembers("active_workflows")
        return list(workflows)

    # ========================================================================
    # PHASE OPERATIONS
    # ========================================================================

    async def create_phase(
        self,
        workflow_id: str,
        phase_name: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Create phase result entry.

        Args:
            workflow_id: Workflow identifier
            phase_name: Phase name (requirements, design, etc.)
            data: Phase metadata

        Returns:
            bool: Success status
        """
        await self.connect()

        data["started_at"] = data.get("started_at", datetime.now().isoformat())
        data["status"] = data.get("status", "running")

        await self.client.hset(
            f"workflow:{workflow_id}:phase:{phase_name}",
            mapping={k: str(v) for k, v in data.items()}
        )

        # Set TTL
        await self.client.expire(f"workflow:{workflow_id}:phase:{phase_name}", 604800)

        logger.info(f"📍 Created phase: {workflow_id} → {phase_name}")
        return True

    async def update_phase(
        self,
        workflow_id: str,
        phase_name: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update phase metadata.

        Args:
            workflow_id: Workflow identifier
            phase_name: Phase name
            updates: Fields to update

        Returns:
            bool: Success status
        """
        await self.connect()

        updates["updated_at"] = datetime.now().isoformat()

        await self.client.hset(
            f"workflow:{workflow_id}:phase:{phase_name}",
            mapping={k: str(v) for k, v in updates.items()}
        )

        return True

    async def complete_phase(
        self,
        workflow_id: str,
        phase_name: str,
        quality_score: float,
        artifacts: List[str]
    ) -> bool:
        """
        Mark phase as completed.

        Args:
            workflow_id: Workflow identifier
            phase_name: Phase name
            quality_score: Quality score (0.0-1.0)
            artifacts: List of created artifacts

        Returns:
            bool: Success status
        """
        await self.connect()

        await self.update_phase(workflow_id, phase_name, {
            "status": "completed",
            "quality_score": quality_score,
            "artifacts": json.dumps(artifacts),
            "completed_at": datetime.now().isoformat()
        })

        logger.info(f"✅ Completed phase: {workflow_id} → {phase_name} (quality: {quality_score:.0%})")
        return True

    async def get_phase(
        self,
        workflow_id: str,
        phase_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get phase metadata.

        Args:
            workflow_id: Workflow identifier
            phase_name: Phase name

        Returns:
            Dict with phase data or None
        """
        await self.connect()

        data = await self.client.hgetall(f"workflow:{workflow_id}:phase:{phase_name}")

        if not data:
            return None

        # Parse JSON fields
        if "artifacts" in data:
            try:
                data["artifacts"] = json.loads(data["artifacts"])
            except:
                pass

        return data

    # ========================================================================
    # WEBSOCKET CONNECTION MANAGEMENT
    # ========================================================================

    async def add_ws_connection(
        self,
        workflow_id: str,
        connection_id: str
    ) -> bool:
        """
        Register WebSocket connection for workflow.

        Args:
            workflow_id: Workflow identifier
            connection_id: WebSocket connection ID

        Returns:
            bool: Success status
        """
        await self.connect()

        await self.client.sadd(f"ws:connections:{workflow_id}", connection_id)

        # Set TTL
        await self.client.expire(f"ws:connections:{workflow_id}", 86400)

        logger.debug(f"🔌 Added WebSocket connection: {connection_id} → {workflow_id}")
        return True

    async def remove_ws_connection(
        self,
        workflow_id: str,
        connection_id: str
    ) -> bool:
        """
        Unregister WebSocket connection.

        Args:
            workflow_id: Workflow identifier
            connection_id: WebSocket connection ID

        Returns:
            bool: Success status
        """
        await self.connect()

        await self.client.srem(f"ws:connections:{workflow_id}", connection_id)

        logger.debug(f"🔌 Removed WebSocket connection: {connection_id}")
        return True

    async def get_ws_connections(self, workflow_id: str) -> Set[str]:
        """
        Get all WebSocket connections for workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Set of connection IDs
        """
        await self.connect()

        connections = await self.client.smembers(f"ws:connections:{workflow_id}")
        return connections

    # ========================================================================
    # CHECKPOINT OPERATIONS
    # ========================================================================

    async def add_checkpoint(
        self,
        workflow_id: str,
        checkpoint_data: Dict[str, Any]
    ) -> bool:
        """
        Add checkpoint metadata.

        Args:
            workflow_id: Workflow identifier
            checkpoint_data: Checkpoint info {checkpoint_id, phase, quality_score, file_path}

        Returns:
            bool: Success status
        """
        await self.connect()

        checkpoint_data["timestamp"] = checkpoint_data.get("timestamp", datetime.now().isoformat())

        # Add to list
        await self.client.rpush(
            f"workflow:{workflow_id}:checkpoints",
            json.dumps(checkpoint_data)
        )

        # Set TTL
        await self.client.expire(f"workflow:{workflow_id}:checkpoints", 604800)

        logger.info(f"💾 Added checkpoint: {checkpoint_data.get('checkpoint_id')}")
        return True

    async def get_checkpoints(self, workflow_id: str) -> List[Dict[str, Any]]:
        """
        Get all checkpoints for workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            List of checkpoint metadata
        """
        await self.connect()

        checkpoints_raw = await self.client.lrange(
            f"workflow:{workflow_id}:checkpoints",
            0,
            -1
        )

        checkpoints = []
        for checkpoint_str in checkpoints_raw:
            try:
                checkpoints.append(json.loads(checkpoint_str))
            except:
                pass

        return checkpoints

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    async def cleanup_stale_workflows(self, hours: int = 24) -> int:
        """
        Clean up workflows that haven't been updated recently.

        Args:
            hours: Hours of inactivity before cleanup

        Returns:
            int: Number of workflows cleaned up
        """
        await self.connect()

        active = await self.get_active_workflows()
        cleaned = 0
        cutoff = datetime.now() - timedelta(hours=hours)

        for workflow_id in active:
            workflow = await self.get_workflow(workflow_id)
            if workflow:
                updated_at = datetime.fromisoformat(workflow.get("updated_at", ""))
                if updated_at < cutoff:
                    await self.fail_workflow(
                        workflow_id,
                        f"Stale workflow (inactive for {hours}h)"
                    )
                    cleaned += 1

        logger.info(f"🧹 Cleaned up {cleaned} stale workflows")
        return cleaned

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get Redis statistics.

        Returns:
            Dict with statistics
        """
        await self.connect()

        active_count = len(await self.get_active_workflows())

        # Get workflow counts by status
        status_counts = {"starting": 0, "running": 0, "paused": 0, "completed": 0, "error": 0}

        for workflow_id in await self.get_active_workflows():
            workflow = await self.get_workflow(workflow_id)
            if workflow:
                status = workflow.get("status", "unknown")
                if status in status_counts:
                    status_counts[status] += 1

        return {
            "active_workflows": active_count,
            "status_counts": status_counts,
            "redis_url": self.redis_url,
            "db": self.db
        }
