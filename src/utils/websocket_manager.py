"""
WebSocket Manager for Workflow Real-Time Updates

Manages WebSocket connections, message broadcasting, and connection health.
"""

import json
import logging
import asyncio
from typing import Dict, Set, Any, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """
    Manages WebSocket connections for workflow updates.

    Features:
    - Connection pooling by workflow_id
    - Broadcast to all workflow subscribers
    - Connection health monitoring
    - Automatic cleanup of stale connections
    - Message queuing for reliability
    """

    def __init__(self, redis_manager=None):
        """
        Initialize WebSocket manager.

        Args:
            redis_manager: Optional Redis manager for persistence
        """
        # Active connections: workflow_id -> Set[WebSocket]
        self.active_connections: Dict[str, Set[WebSocket]] = {}

        # Connection metadata: WebSocket -> connection_info
        self.connection_info: Dict[WebSocket, Dict[str, Any]] = {}

        # Redis manager for persistence
        self.redis = redis_manager

        # Message queue for offline delivery (workflow_id -> List[message])
        self.message_queue: Dict[str, list] = {}

        # Connection counter for IDs
        self.connection_counter = 0

        logger.info("🔌 WebSocket Manager initialized")

    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================

    async def connect(
        self,
        websocket: WebSocket,
        workflow_id: str,
        client_id: Optional[str] = None
    ):
        """
        Accept and register new WebSocket connection.

        Args:
            websocket: WebSocket connection
            workflow_id: Workflow to subscribe to
            client_id: Optional client identifier
        """
        await websocket.accept()

        # Generate connection ID
        self.connection_counter += 1
        connection_id = client_id or f"ws-{self.connection_counter}"

        # Add to active connections
        if workflow_id not in self.active_connections:
            self.active_connections[workflow_id] = set()

        self.active_connections[workflow_id].add(websocket)

        # Store connection metadata
        self.connection_info[websocket] = {
            "connection_id": connection_id,
            "workflow_id": workflow_id,
            "connected_at": datetime.now().isoformat(),
            "last_ping": datetime.now().isoformat(),
            "messages_sent": 0
        }

        # Register in Redis if available
        if self.redis:
            await self.redis.add_ws_connection(workflow_id, connection_id)

        # Send queued messages if any
        await self._send_queued_messages(websocket, workflow_id)

        logger.info(f"🔌 WebSocket connected: {connection_id} → {workflow_id}")
        logger.debug(f"   Active connections for {workflow_id}: {len(self.active_connections[workflow_id])}")

        # Send connection acknowledgment
        await self._send_to_connection(websocket, {
            "type": "connection_established",
            "connection_id": connection_id,
            "workflow_id": workflow_id,
            "timestamp": datetime.now().isoformat()
        })

    async def disconnect(self, websocket: WebSocket):
        """
        Handle WebSocket disconnection.

        Args:
            websocket: WebSocket connection to disconnect
        """
        if websocket not in self.connection_info:
            return

        # Get connection info
        info = self.connection_info[websocket]
        connection_id = info["connection_id"]
        workflow_id = info["workflow_id"]

        # Remove from active connections
        if workflow_id in self.active_connections:
            self.active_connections[workflow_id].discard(websocket)

            # Clean up empty sets
            if len(self.active_connections[workflow_id]) == 0:
                del self.active_connections[workflow_id]

        # Remove connection info
        del self.connection_info[websocket]

        # Unregister from Redis
        if self.redis:
            await self.redis.remove_ws_connection(workflow_id, connection_id)

        logger.info(f"🔌 WebSocket disconnected: {connection_id}")
        logger.debug(f"   Remaining connections for {workflow_id}: {len(self.active_connections.get(workflow_id, set()))}")

    # ========================================================================
    # MESSAGE BROADCASTING
    # ========================================================================

    async def broadcast_to_workflow(
        self,
        workflow_id: str,
        message: Dict[str, Any]
    ):
        """
        Broadcast message to all connections subscribed to a workflow.

        Args:
            workflow_id: Workflow identifier
            message: Message data to broadcast
        """
        if workflow_id not in self.active_connections:
            # No active connections - queue message
            await self._queue_message(workflow_id, message)
            logger.debug(f"📦 Queued message for {workflow_id} (no active connections)")
            return

        connections = list(self.active_connections[workflow_id])
        successful = 0
        failed = 0

        for websocket in connections:
            try:
                await self._send_to_connection(websocket, message)
                successful += 1
            except Exception as e:
                logger.warning(f"Failed to send to connection: {e}")
                await self.disconnect(websocket)
                failed += 1

        logger.debug(f"📡 Broadcast to {workflow_id}: {successful} sent, {failed} failed")

    async def _send_to_connection(
        self,
        websocket: WebSocket,
        message: Dict[str, Any]
    ):
        """
        Send message to specific WebSocket connection.

        Args:
            websocket: WebSocket connection
            message: Message data
        """
        try:
            await websocket.send_json(message)

            # Update connection metadata
            if websocket in self.connection_info:
                self.connection_info[websocket]["messages_sent"] += 1
                self.connection_info[websocket]["last_message_at"] = datetime.now().isoformat()

        except WebSocketDisconnect:
            await self.disconnect(websocket)
            raise
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
            await self.disconnect(websocket)
            raise

    # ========================================================================
    # MESSAGE QUEUING
    # ========================================================================

    async def _queue_message(
        self,
        workflow_id: str,
        message: Dict[str, Any]
    ):
        """
        Queue message for offline delivery.

        Args:
            workflow_id: Workflow identifier
            message: Message to queue
        """
        if workflow_id not in self.message_queue:
            self.message_queue[workflow_id] = []

        # Add timestamp
        message["queued_at"] = datetime.now().isoformat()

        self.message_queue[workflow_id].append(message)

        # Limit queue size
        max_queue_size = 100
        if len(self.message_queue[workflow_id]) > max_queue_size:
            self.message_queue[workflow_id] = self.message_queue[workflow_id][-max_queue_size:]

    async def _send_queued_messages(
        self,
        websocket: WebSocket,
        workflow_id: str
    ):
        """
        Send queued messages to newly connected client.

        Args:
            websocket: WebSocket connection
            workflow_id: Workflow identifier
        """
        if workflow_id not in self.message_queue:
            return

        queued_messages = self.message_queue[workflow_id]
        if not queued_messages:
            return

        logger.info(f"📦 Sending {len(queued_messages)} queued messages to new connection")

        for message in queued_messages:
            try:
                await self._send_to_connection(websocket, message)
            except Exception as e:
                logger.warning(f"Failed to send queued message: {e}")
                break

        # Clear queue after successful delivery
        self.message_queue[workflow_id] = []

    # ========================================================================
    # HEALTH MONITORING
    # ========================================================================

    async def handle_ping(self, websocket: WebSocket):
        """
        Handle ping from client (keep-alive).

        Args:
            websocket: WebSocket connection
        """
        if websocket not in self.connection_info:
            return

        # Update last ping time
        self.connection_info[websocket]["last_ping"] = datetime.now().isoformat()

        # Send pong
        await self._send_to_connection(websocket, {
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        })

    async def cleanup_stale_connections(self, timeout_minutes: int = 30):
        """
        Remove connections that haven't pinged recently.

        Args:
            timeout_minutes: Minutes of inactivity before cleanup

        Returns:
            int: Number of connections cleaned up
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(minutes=timeout_minutes)
        stale_connections = []

        for websocket, info in self.connection_info.items():
            last_ping = datetime.fromisoformat(info["last_ping"])
            if last_ping < cutoff:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            connection_id = self.connection_info[websocket]["connection_id"]
            logger.warning(f"🧹 Cleaning up stale connection: {connection_id}")
            await self.disconnect(websocket)

        return len(stale_connections)

    # ========================================================================
    # CONNECTION LISTENER
    # ========================================================================

    async def listen(
        self,
        websocket: WebSocket,
        workflow_id: str
    ):
        """
        Listen for messages from WebSocket client.

        Args:
            websocket: WebSocket connection
            workflow_id: Workflow identifier
        """
        try:
            while True:
                # Receive message from client
                data = await websocket.receive_text()

                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from client: {data}")
                    continue

                # Handle message types
                message_type = message.get("type")

                if message_type == "ping":
                    await self.handle_ping(websocket)

                elif message_type == "subscribe":
                    # Client wants to subscribe to additional workflows
                    new_workflow_id = message.get("workflow_id")
                    if new_workflow_id:
                        logger.info(f"Client subscribing to additional workflow: {new_workflow_id}")
                        # Note: Current implementation supports one workflow per connection
                        # This would require refactoring to support multiple

                else:
                    logger.debug(f"Received message type: {message_type}")

        except WebSocketDisconnect:
            await self.disconnect(websocket)
        except Exception as e:
            logger.error(f"Error in WebSocket listener: {e}", exc_info=True)
            await self.disconnect(websocket)

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """
        Get WebSocket manager statistics.

        Returns:
            Dict with statistics
        """
        total_connections = sum(len(conns) for conns in self.active_connections.values())
        workflows_with_connections = len(self.active_connections)
        total_queued_messages = sum(len(msgs) for msgs in self.message_queue.values())

        # Connection breakdown by workflow
        workflow_stats = {}
        for workflow_id, connections in self.active_connections.items():
            workflow_stats[workflow_id] = len(connections)

        return {
            "total_connections": total_connections,
            "workflows_with_connections": workflows_with_connections,
            "total_queued_messages": total_queued_messages,
            "workflow_breakdown": workflow_stats,
            "connection_details": {
                conn_info["connection_id"]: {
                    "workflow_id": conn_info["workflow_id"],
                    "messages_sent": conn_info["messages_sent"],
                    "connected_duration": self._calculate_duration(conn_info["connected_at"])
                }
                for conn_info in self.connection_info.values()
            }
        }

    def _calculate_duration(self, start_time_iso: str) -> str:
        """Calculate duration since start time"""
        try:
            start = datetime.fromisoformat(start_time_iso)
            duration = datetime.now() - start
            return str(duration).split('.')[0]  # Remove microseconds
        except:
            return "unknown"

    # ========================================================================
    # ADMIN OPERATIONS
    # ========================================================================

    async def broadcast_to_all(self, message: Dict[str, Any]):
        """
        Broadcast message to all active connections.

        Args:
            message: Message to broadcast
        """
        for workflow_id in list(self.active_connections.keys()):
            await self.broadcast_to_workflow(workflow_id, message)

    async def close_workflow_connections(self, workflow_id: str):
        """
        Close all connections for a workflow.

        Args:
            workflow_id: Workflow identifier
        """
        if workflow_id not in self.active_connections:
            return

        connections = list(self.active_connections[workflow_id])

        for websocket in connections:
            await self._send_to_connection(websocket, {
                "type": "connection_closing",
                "reason": "Workflow ended",
                "timestamp": datetime.now().isoformat()
            })
            await websocket.close()
            await self.disconnect(websocket)

        logger.info(f"🔌 Closed {len(connections)} connections for workflow {workflow_id}")

    async def shutdown(self):
        """Gracefully shutdown all connections"""
        logger.info("🔌 Shutting down WebSocket manager...")

        # Send shutdown notice to all clients
        await self.broadcast_to_all({
            "type": "server_shutdown",
            "message": "Server is shutting down",
            "timestamp": datetime.now().isoformat()
        })

        # Close all connections
        all_websockets = list(self.connection_info.keys())
        for websocket in all_websockets:
            try:
                await websocket.close()
            except:
                pass
            await self.disconnect(websocket)

        self.active_connections.clear()
        self.connection_info.clear()
        self.message_queue.clear()

        logger.info("✅ WebSocket manager shutdown complete")
