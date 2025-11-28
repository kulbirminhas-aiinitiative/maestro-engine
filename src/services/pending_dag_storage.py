#!/usr/bin/env python3
"""
Pending DAG Storage

Manages temporary storage of generated DAGs awaiting user approval.
Uses Redis with TTL for automatic cleanup.
"""

import logging
import json
import uuid
from typing import Optional, Dict
from datetime import datetime, timedelta

from utils.redis_manager import RedisManager
from services.ai_dag_generator import GeneratedDAG
from workflow.dag import DAG

logger = logging.getLogger(__name__)


class PendingDAGStorage:
    """
    Manages pending DAG storage in Redis.

    Features:
    - Store generated DAGs temporarily
    - Automatic expiration (24 hour TTL)
    - Retrieve for approval/modification
    - Clean up after approval/rejection
    """

    # Redis key prefixes
    PREFIX_PENDING = "pending_dag:"
    PREFIX_USER_PENDING = "user_pending_dags:"

    # TTL for pending DAGs (24 hours)
    PENDING_TTL = 86400  # seconds

    def __init__(self, redis_manager: Optional[RedisManager] = None):
        """Initialize pending DAG storage"""
        self.redis = redis_manager or RedisManager()
        logger.info("✅ PendingDAGStorage initialized")

    async def store_pending_dag(
        self,
        generated_dag: GeneratedDAG,
        user_id: str,
        room_id: str
    ) -> str:
        """
        Store a generated DAG pending user approval.

        Args:
            generated_dag: Generated DAG to store
            user_id: User ID
            room_id: Collaboration room ID

        Returns:
            pending_dag_id for tracking
        """
        # Generate unique pending ID
        pending_id = f"pending_{uuid.uuid4().hex[:16]}"

        # Serialize DAG and metadata
        dag_data = self._serialize_generated_dag(generated_dag)

        # Add tracking info
        dag_data['pending_id'] = pending_id
        dag_data['user_id'] = user_id
        dag_data['room_id'] = room_id
        dag_data['created_at'] = datetime.utcnow().isoformat()
        dag_data['status'] = 'pending'

        # Store in Redis with TTL
        key = f"{self.PREFIX_PENDING}{pending_id}"
        await self.redis.set(
            key,
            json.dumps(dag_data),
            ex=self.PENDING_TTL
        )

        # Add to user's pending list
        user_key = f"{self.PREFIX_USER_PENDING}{user_id}"
        await self.redis.sadd(user_key, pending_id)
        await self.redis.expire(user_key, self.PENDING_TTL)

        logger.info(f"✅ Stored pending DAG: {pending_id} for user {user_id}")

        return pending_id

    async def get_pending_dag(self, pending_id: str) -> Optional[Dict]:
        """
        Retrieve a pending DAG by ID.

        Args:
            pending_id: Pending DAG ID

        Returns:
            Dict with DAG data or None if not found/expired
        """
        key = f"{self.PREFIX_PENDING}{pending_id}"
        data = await self.redis.get(key)

        if not data:
            logger.warning(f"⚠️  Pending DAG not found: {pending_id}")
            return None

        try:
            dag_data = json.loads(data)
            logger.info(f"✅ Retrieved pending DAG: {pending_id}")
            return dag_data
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error decoding pending DAG {pending_id}: {e}")
            return None

    async def update_pending_dag(
        self,
        pending_id: str,
        modified_dag_data: Dict
    ) -> bool:
        """
        Update a pending DAG with modifications.

        Args:
            pending_id: Pending DAG ID
            modified_dag_data: Updated DAG data

        Returns:
            True if successful
        """
        # Get existing data
        existing = await self.get_pending_dag(pending_id)
        if not existing:
            return False

        # Update DAG data while preserving metadata
        existing['dag'] = modified_dag_data.get('dag', existing.get('dag'))
        existing['metadata'] = modified_dag_data.get('metadata', existing.get('metadata'))
        existing['updated_at'] = datetime.utcnow().isoformat()

        # Store updated data
        key = f"{self.PREFIX_PENDING}{pending_id}"
        await self.redis.set(
            key,
            json.dumps(existing),
            ex=self.PENDING_TTL
        )

        logger.info(f"✅ Updated pending DAG: {pending_id}")
        return True

    async def approve_pending_dag(
        self,
        pending_id: str
    ) -> Optional[Dict]:
        """
        Mark pending DAG as approved and return data.

        Args:
            pending_id: Pending DAG ID

        Returns:
            DAG data if found, None otherwise
        """
        dag_data = await self.get_pending_dag(pending_id)

        if not dag_data:
            return None

        # Update status
        dag_data['status'] = 'approved'
        dag_data['approved_at'] = datetime.utcnow().isoformat()

        # Keep for a bit longer (1 hour) for reference
        key = f"{self.PREFIX_PENDING}{pending_id}"
        await self.redis.set(
            key,
            json.dumps(dag_data),
            ex=3600  # 1 hour
        )

        logger.info(f"✅ Approved pending DAG: {pending_id}")
        return dag_data

    async def reject_pending_dag(
        self,
        pending_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Mark pending DAG as rejected and clean up.

        Args:
            pending_id: Pending DAG ID
            reason: Optional rejection reason

        Returns:
            True if successful
        """
        dag_data = await self.get_pending_dag(pending_id)

        if not dag_data:
            return False

        # Update status and store rejection info briefly
        dag_data['status'] = 'rejected'
        dag_data['rejected_at'] = datetime.utcnow().isoformat()
        dag_data['rejection_reason'] = reason

        # Store for short time (10 minutes) for logging
        key = f"{self.PREFIX_PENDING}{pending_id}"
        await self.redis.set(
            key,
            json.dumps(dag_data),
            ex=600  # 10 minutes
        )

        # Remove from user's pending list
        user_id = dag_data.get('user_id')
        if user_id:
            user_key = f"{self.PREFIX_USER_PENDING}{user_id}"
            await self.redis.srem(user_key, pending_id)

        logger.info(f"✅ Rejected pending DAG: {pending_id}")
        return True

    async def get_user_pending_dags(self, user_id: str) -> list[str]:
        """
        Get list of pending DAG IDs for a user.

        Args:
            user_id: User ID

        Returns:
            List of pending DAG IDs
        """
        user_key = f"{self.PREFIX_USER_PENDING}{user_id}"
        pending_ids = await self.redis.smembers(user_key)

        if not pending_ids:
            return []

        # Filter out expired ones
        valid_pending = []
        for pending_id in pending_ids:
            if await self.get_pending_dag(pending_id):
                valid_pending.append(pending_id)
            else:
                # Clean up stale reference
                await self.redis.srem(user_key, pending_id)

        return valid_pending

    async def cleanup_expired(self) -> int:
        """
        Clean up expired pending DAGs.

        Returns:
            Number of DAGs cleaned up
        """
        # Redis TTL handles automatic expiration
        # This method is for manual cleanup if needed

        pattern = f"{self.PREFIX_PENDING}*"
        keys = await self.redis.scan_keys(pattern)

        cleaned = 0
        for key in keys:
            ttl = await self.redis.ttl(key)
            if ttl == -1:  # No expiration set
                await self.redis.expire(key, self.PENDING_TTL)
                cleaned += 1
            elif ttl == -2:  # Key doesn't exist
                cleaned += 1

        if cleaned > 0:
            logger.info(f"✅ Cleaned up {cleaned} expired pending DAGs")

        return cleaned

    def _serialize_generated_dag(self, generated_dag: GeneratedDAG) -> Dict:
        """Serialize GeneratedDAG for storage"""
        return {
            'dag': {
                'dag_id': generated_dag.dag.dag_id,
                'name': generated_dag.dag.name,
                'description': generated_dag.dag.description,
                'nodes': {
                    node_id: {
                        'name': node.name,
                        'description': node.description,
                        'task_type': node.task_type.value,
                        'depends_on': node.depends_on,
                        'priority': node.priority,
                        'estimated_duration': getattr(node, 'estimated_duration', None),
                        'agent_persona': getattr(node, 'agent_persona', None)
                    }
                    for node_id, node in generated_dag.dag.nodes.items()
                }
            },
            'metadata': generated_dag.metadata,
            'reasoning': generated_dag.reasoning,
            'estimated_timeline': generated_dag.estimated_timeline,
            'risk_factors': generated_dag.risk_factors,
            'parallel_opportunities': generated_dag.parallel_opportunities,
            'validation_passed': generated_dag.validation_passed
        }


# Standalone test
async def test_pending_dag_storage():
    """Test pending DAG storage"""
    from workflow.dag import WorkflowBuilder, TaskType
    from services.ai_dag_generator import GeneratedDAG

    storage = PendingDAGStorage()

    # Create a sample DAG
    dag = (
        WorkflowBuilder("test_dag_123", "Test Workflow")
        .add_task("phase1", "Phase 1", "First phase", TaskType.RESEARCH)
        .add_task("phase2", "Phase 2", "Second phase", TaskType.CODE, depends_on=["phase1"])
        .build()
    )

    generated_dag = GeneratedDAG(
        dag=dag,
        metadata={'complexity': 'simple'},
        reasoning="Test workflow",
        estimated_timeline="2 weeks",
        risk_factors=[],
        parallel_opportunities=[],
        validation_passed=True
    )

    print("="*80)
    print("TEST: Pending DAG Storage")
    print("="*80)

    # Store pending DAG
    print("\n1. Storing pending DAG...")
    pending_id = await storage.store_pending_dag(
        generated_dag,
        user_id="test_user_123",
        room_id="room_abc"
    )
    print(f"   Pending ID: {pending_id}")

    # Retrieve pending DAG
    print("\n2. Retrieving pending DAG...")
    retrieved = await storage.get_pending_dag(pending_id)
    print(f"   Retrieved: {retrieved is not None}")
    print(f"   Status: {retrieved.get('status')}")

    # Get user's pending DAGs
    print("\n3. Getting user's pending DAGs...")
    user_pending = await storage.get_user_pending_dags("test_user_123")
    print(f"   User has {len(user_pending)} pending DAG(s)")

    # Approve DAG
    print("\n4. Approving DAG...")
    approved = await storage.approve_pending_dag(pending_id)
    print(f"   Approved: {approved is not None}")
    print(f"   Status: {approved.get('status')}")

    # Clean up
    print("\n5. Cleanup...")
    cleaned = await storage.cleanup_expired()
    print(f"   Cleaned {cleaned} expired DAGs")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_pending_dag_storage())
